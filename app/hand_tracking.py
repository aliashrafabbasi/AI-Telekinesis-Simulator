import logging
import threading
import time
from collections import deque

import cv2
import mediapipe as mp
from mediapipe.python.solutions import drawing_utils as mp_drawing

from app.config import TRACKING
from app.schemas import HandFramePayload

logger = logging.getLogger(__name__)

mp_hands = mp.solutions.hands

WRIST = 0
INDEX_TIP = 8
MIDDLE_MCP = 9

GREEN_BGR = (0, 255, 0)
RED_BGR = (0, 0, 255)
CLAP_BGR = (0, 255, 255)


class HandTracker:
    def __init__(self, config=TRACKING):
        self.config = config
        self._hands = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=config.max_num_hands,
            min_detection_confidence=config.min_detection_confidence,
            min_tracking_confidence=config.min_tracking_confidence,
        )
        self._cap: cv2.VideoCapture | None = None
        self._last_gesture: str = "open"
        self._smooth_x: float | None = None
        self._smooth_y: float | None = None
        self._last_smooth_time: float | None = None
        self._hand_speed = 0.0
        self._dist_history: deque[float] = deque(maxlen=14)
        self._prev_pair_distance: float | None = None
        self._prev_hand_count = 0
        self._last_clap_time = 0.0
        self._clap_armed = False
        self._frames_processed = 0
        self._preview_counter = 0
        self._camera_lock = threading.Lock()
        self._read_failures = 0
        self._last_fail_log = 0.0

    @property
    def frames_processed(self) -> int:
        return self._frames_processed

    @property
    def camera_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    @property
    def read_failure_count(self) -> int:
        return self._read_failures

    def _release_camera(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except cv2.error:
                pass
            self._cap = None

    def _open_camera(self) -> cv2.VideoCapture | None:
        self._release_camera()

        cap = cv2.VideoCapture(self.config.camera_index, cv2.CAP_V4L2)
        if not cap.isOpened():
            cap = cv2.VideoCapture(self.config.camera_index)

        if not cap.isOpened():
            logger.error("Unable to open webcam index %s", self.config.camera_index)
            return None

        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.camera_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.camera_height)
        cap.set(cv2.CAP_PROP_FPS, self.config.camera_fps)

        self._cap = cap
        self._read_failures = 0
        logger.info("Webcam opened (%dx%d)", self.config.camera_width, self.config.camera_height)
        return cap

    def _get_camera(self) -> cv2.VideoCapture | None:
        if self._cap is None or not self._cap.isOpened():
            return self._open_camera()
        return self._cap

    def _read_frame(self):
        cap = self._get_camera()
        if cap is None:
            return None

        cap.grab()
        success, frame = cap.read()
        if success:
            self._read_failures = 0
            return frame

        self._read_failures += 1
        now = time.monotonic()
        if now - self._last_fail_log > 2.0:
            logger.warning(
                "Camera frame read failed (%s/%s) — recovering",
                self._read_failures,
                self.config.camera_fail_before_reset,
            )
            self._last_fail_log = now

        if self._read_failures >= self.config.camera_fail_before_reset:
            logger.warning("Resetting webcam after repeated read failures")
            self._release_camera()
            time.sleep(0.25)

        return None

    @staticmethod
    def _landmark_dist(landmarks, a: int, b: int) -> float:
        la, lb = landmarks[a], landmarks[b]
        return ((la.x - lb.x) ** 2 + (la.y - lb.y) ** 2) ** 0.5

    @staticmethod
    def _stable_hand_anchor(hand_landmarks) -> tuple[float, float]:
        lm = hand_landmarks.landmark
        x = lm[WRIST].x * 0.65 + lm[MIDDLE_MCP].x * 0.35
        y = lm[WRIST].y * 0.65 + lm[MIDDLE_MCP].y * 0.35
        return x, y

    def _smooth_position(self, x: float, y: float, timestamp: float) -> tuple[float, float]:
        if self._smooth_x is None or self._smooth_y is None or self._last_smooth_time is None:
            self._smooth_x, self._smooth_y = x, y
            self._last_smooth_time = timestamp
            self._hand_speed = 0.0
            return x, y

        dt = max(timestamp - self._last_smooth_time, 1 / 120)
        self._last_smooth_time = timestamp

        dx = x - self._smooth_x
        dy = y - self._smooth_y
        distance = (dx * dx + dy * dy) ** 0.5

        if distance < self.config.dead_zone:
            self._hand_speed *= 0.85
            return self._smooth_x, self._smooth_y

        if distance > self.config.max_jump:
            scale = self.config.max_jump / distance
            x = self._smooth_x + dx * scale
            y = self._smooth_y + dy * scale
            dx = x - self._smooth_x
            dy = y - self._smooth_y
            distance = self.config.max_jump

        raw_speed = distance / dt
        speed_t = min(raw_speed / self.config.reference_hand_speed, 1.0)
        alpha = self.config.smooth_alpha_idle + (
            self.config.smooth_alpha_active - self.config.smooth_alpha_idle
        ) * speed_t

        self._smooth_x += alpha * (x - self._smooth_x)
        self._smooth_y += alpha * (y - self._smooth_y)
        self._hand_speed = self._hand_speed * 0.72 + raw_speed * 0.28
        return self._smooth_x, self._smooth_y

    def _reset_smoothing(self) -> None:
        self._smooth_x = None
        self._smooth_y = None
        self._last_smooth_time = None
        self._hand_speed = 0.0
        self._prev_pair_distance = None
        self._prev_hand_count = 0
        self._clap_armed = False
        self._dist_history.clear()

    @staticmethod
    def _pair_distance(hand_a, hand_b) -> float:
        la, lb = hand_a.landmark, hand_b.landmark
        samples = [
            ((la[WRIST].x - lb[WRIST].x) ** 2 + (la[WRIST].y - lb[WRIST].y) ** 2) ** 0.5,
            ((la[MIDDLE_MCP].x - lb[MIDDLE_MCP].x) ** 2 + (la[MIDDLE_MCP].y - lb[MIDDLE_MCP].y) ** 2) ** 0.5,
            ((la[INDEX_TIP].x - lb[INDEX_TIP].x) ** 2 + (la[INDEX_TIP].y - lb[INDEX_TIP].y) ** 2) ** 0.5,
        ]
        return min(samples)

    def _detect_clap(self, multi_hand_landmarks, now: float) -> bool:
        hand_count = len(multi_hand_landmarks)

        if now - self._last_clap_time <= self.config.clap_cooldown_sec:
            self._prev_hand_count = hand_count
            return False

        clap = False

        if hand_count >= 2:
            dist = self._pair_distance(multi_hand_landmarks[0], multi_hand_landmarks[1])
            self._dist_history.append(dist)

            if self._prev_pair_distance is not None:
                closing = self._prev_pair_distance - dist
                if dist <= self.config.clap_touch_distance and closing >= self.config.clap_close_delta:
                    clap = True
                elif (
                    dist <= self.config.clap_touch_distance
                    and self._prev_pair_distance >= self.config.clap_spread_distance
                ):
                    clap = True

            if len(self._dist_history) >= 2:
                recent = list(self._dist_history)
                spread = max(recent[-8:])
                if dist <= self.config.clap_touch_distance and spread >= self.config.clap_spread_distance:
                    clap = True

            self._clap_armed = dist <= self.config.clap_touch_distance + 0.06
            self._prev_pair_distance = dist

        elif hand_count == 1 and self._prev_hand_count >= 2:
            if self._clap_armed:
                clap = True
            elif self._prev_pair_distance is not None and self._prev_pair_distance <= self.config.clap_touch_distance:
                clap = True
            elif self._dist_history and min(self._dist_history) <= self.config.clap_touch_distance:
                clap = True

        elif hand_count == 0:
            self._prev_pair_distance = None
            self._clap_armed = False

        self._prev_hand_count = hand_count

        if clap:
            self._last_clap_time = now
            self._dist_history.clear()
            self._clap_armed = False
            self._prev_pair_distance = None

        return clap

    @staticmethod
    def _control_anchor(multi_hand_landmarks) -> tuple[float, float]:
        if len(multi_hand_landmarks) == 1:
            return HandTracker._stable_hand_anchor(multi_hand_landmarks[0])

        a1 = HandTracker._stable_hand_anchor(multi_hand_landmarks[0])
        a2 = HandTracker._stable_hand_anchor(multi_hand_landmarks[1])
        return (a1[0] + a2[0]) / 2, (a1[1] + a2[1]) / 2

    def _count_extended_fingers(self, hand_landmarks) -> int:
        lm = hand_landmarks.landmark
        count = 0

        if self._landmark_dist(lm, 4, 0) > self._landmark_dist(lm, 3, 0) * 1.08:
            count += 1

        for tip, pip in [(8, 6), (12, 10), (16, 14), (20, 18)]:
            if self._landmark_dist(lm, tip, 0) > self._landmark_dist(lm, pip, 0) * 1.05:
                count += 1

        return count

    def _detect_gesture(self, hand_landmarks) -> str:
        extended = self._count_extended_fingers(hand_landmarks)

        if extended <= 1:
            self._last_gesture = "punch"
        elif extended >= 4:
            self._last_gesture = "open"

        return self._last_gesture

    @staticmethod
    def _gesture_colors(gesture: str) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        color = RED_BGR if gesture == "punch" else GREEN_BGR
        return color, color

    @staticmethod
    def _palm_center_px(hand_landmarks, width: int, height: int) -> tuple[int, int]:
        lm = hand_landmarks.landmark
        x = int((lm[WRIST].x * 0.35 + lm[MIDDLE_MCP].x * 0.65) * width)
        y = int((lm[WRIST].y * 0.35 + lm[MIDDLE_MCP].y * 0.65) * height)
        return x, y

    def capture_frame(self) -> tuple[HandFramePayload, bytes | None]:
        with self._camera_lock:
            return self._capture_frame_unlocked()

    def _capture_frame_unlocked(self) -> tuple[HandFramePayload, bytes | None]:
        frame = self._read_frame()
        payload = HandFramePayload()

        if frame is None:
            return payload, None

        self._frames_processed += 1
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape
        process = cv2.resize(frame, (self.config.process_width, self.config.process_height))
        rgb = cv2.cvtColor(process, cv2.COLOR_BGR2RGB)
        results = self._hands.process(rgb)

        if results.multi_hand_landmarks:
            hand_list = results.multi_hand_landmarks
            payload.hands = len(hand_list)
            payload.tracking = True

            if len(hand_list) >= 2:
                dist = self._pair_distance(hand_list[0], hand_list[1])
                payload.palm_dist = round(dist, 4)

            primary = hand_list[0]
            gesture = self._detect_gesture(primary)
            now = time.perf_counter()
            payload.clap = self._detect_clap(hand_list, now)

            raw_x, raw_y = self._control_anchor(hand_list)
            smooth_x, smooth_y = self._smooth_position(raw_x, raw_y, now)
            payload.x = round(smooth_x, 4)
            payload.y = round(smooth_y, 4)
            payload.frame_w = w
            payload.frame_h = h
            payload.gesture = gesture  # type: ignore[assignment]
            payload.ts = round(now * 1000)
            payload.speed = round(self._hand_speed, 4)
        else:
            self._reset_smoothing()

        preview_bytes = self._maybe_encode_preview(process, results)

        return payload, preview_bytes

    def _maybe_encode_preview(self, process, results) -> bytes | None:
        self._preview_counter += 1
        if self._preview_counter < self.config.preview_every_n_frames:
            return None

        self._preview_counter = 0
        ph, pw = process.shape[:2]
        preview_source = process

        if results.multi_hand_landmarks:
            preview_source = process.copy()
            for hand in results.multi_hand_landmarks:
                gesture = self._detect_gesture(hand)
                line_color, dot_color = self._gesture_colors(gesture)
                mp_drawing.draw_landmarks(
                    preview_source,
                    hand,
                    mp_hands.HAND_CONNECTIONS,
                    mp_drawing.DrawingSpec(color=line_color, thickness=1, circle_radius=1),
                    mp_drawing.DrawingSpec(color=dot_color, thickness=1, circle_radius=1),
                )
            if len(results.multi_hand_landmarks) >= 2:
                p1 = self._palm_center_px(results.multi_hand_landmarks[0], pw, ph)
                p2 = self._palm_center_px(results.multi_hand_landmarks[1], pw, ph)
                cv2.line(preview_source, p1, p2, CLAP_BGR, 1)

        ph, pw = preview_source.shape[:2]
        if pw == self.config.preview_width and ph == self.config.preview_height:
            preview = preview_source
        else:
            preview = cv2.resize(
                preview_source,
                (self.config.preview_width, self.config.preview_height),
                interpolation=cv2.INTER_AREA,
            )

        ok, buffer = cv2.imencode(
            ".jpg",
            preview,
            [
                cv2.IMWRITE_JPEG_QUALITY,
                self.config.preview_jpeg_quality,
                cv2.IMWRITE_JPEG_OPTIMIZE,
                1,
            ],
        )
        return buffer.tobytes() if ok else None


_tracker = HandTracker()
_latest_control: dict = {"x": -1, "y": -1, "gesture": "none", "tracking": False}
_control_version = 0
_latest_preview: bytes | None = None
_preview_version = 0
_frame_lock = threading.Lock()
_capture_thread: threading.Thread | None = None
_capture_running = False
_ws_client_count = 0
_ws_client_lock = threading.Lock()


def is_capture_active() -> bool:
    return _capture_running


def acquire_capture() -> None:
    global _ws_client_count

    with _ws_client_lock:
        _ws_client_count += 1
        if _ws_client_count == 1:
            start_capture_loop()


def release_capture() -> None:
    global _ws_client_count

    with _ws_client_lock:
        _ws_client_count = max(0, _ws_client_count - 1)
        if _ws_client_count == 0:
            stop_capture_loop()


def _capture_loop() -> None:
    global _latest_control, _control_version, _latest_preview, _preview_version
    interval = TRACKING.capture_interval_sec

    while _capture_running:
        started = time.perf_counter()
        payload, preview_bytes = _tracker.capture_frame()
        control = payload.model_dump(exclude_none=True)

        with _frame_lock:
            _latest_control = control
            _control_version += 1
            if preview_bytes is not None:
                _latest_preview = preview_bytes
                _preview_version += 1

        elapsed = time.perf_counter() - started
        time.sleep(max(0.0, interval - elapsed))


def start_capture_loop() -> None:
    global _capture_thread, _capture_running

    if _capture_running:
        return

    _capture_running = True
    _capture_thread = threading.Thread(target=_capture_loop, name="hand-capture", daemon=True)
    _capture_thread.start()
    logger.info("Hand capture loop started")


def stop_capture_loop() -> None:
    global _capture_running, _capture_thread

    _capture_running = False
    if _capture_thread is not None:
        _capture_thread.join(timeout=2.0)
        _capture_thread = None

    _tracker._release_camera()
    logger.info("Hand capture loop stopped")


def get_control_data() -> tuple[int, dict]:
    with _frame_lock:
        return _control_version, dict(_latest_control)


def get_preview_frame() -> tuple[int, bytes | None]:
    with _frame_lock:
        return _preview_version, _latest_preview


def get_tracker() -> HandTracker:
    return _tracker
