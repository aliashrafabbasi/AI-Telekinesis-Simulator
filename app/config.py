from dataclasses import dataclass


@dataclass(frozen=True)
class TrackingConfig:
    max_num_hands: int = 2
    min_detection_confidence: float = 0.6
    min_tracking_confidence: float = 0.65
    camera_index: int = 0
    camera_width: int = 640
    camera_height: int = 480
    camera_fps: int = 30
    process_width: int = 320
    process_height: int = 240
    preview_width: int = 320
    preview_height: int = 240
    preview_jpeg_quality: int = 62
    preview_every_n_frames: int = 1
    capture_interval_sec: float = 0.016
    preview_interval_sec: float = 0.002
    camera_fail_before_reset: int = 8
    smooth_alpha_idle: float = 0.84
    smooth_alpha_active: float = 0.96
    reference_hand_speed: float = 1.55
    max_jump: float = 0.22
    dead_zone: float = 0.0006
    clap_touch_distance: float = 0.26
    clap_spread_distance: float = 0.12
    clap_close_delta: float = 0.028
    clap_cooldown_sec: float = 0.85


TRACKING = TrackingConfig()
