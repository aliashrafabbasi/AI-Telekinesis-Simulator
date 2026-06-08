import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from app.auth.dependencies import validate_websocket_token
from app.db.session import async_session
from app.hand_tracking import acquire_capture, get_control_data, get_preview_frame, release_capture

logger = logging.getLogger(__name__)

WS_UNAUTHORIZED_CODE = 4401
StreamFn = Callable[[], tuple[int, Any]]
SendFn = Callable[[WebSocket, Any], Awaitable[None]]


async def _authenticate_websocket(websocket: WebSocket) -> bool:
    token = websocket.query_params.get("token")
    async with async_session() as db:
        user_id = await validate_websocket_token(token, db)

    if user_id is None:
        logger.warning("WebSocket auth rejected from %s", websocket.client)
        await websocket.close(code=WS_UNAUTHORIZED_CODE, reason="Unauthorized")
        return False

    return True


async def _run_streaming_websocket(
    websocket: WebSocket,
    *,
    label: str,
    stream_fn: StreamFn,
    send_fn: SendFn,
    manages_capture: bool,
    poll_interval: float = 0.002,
) -> None:
    if not await _authenticate_websocket(websocket):
        return

    await websocket.accept()
    if manages_capture:
        acquire_capture()
    logger.info("%s client connected", label)
    last_version = -1

    try:
        while True:
            version, payload = stream_fn()
            if payload is not None and version != last_version:
                last_version = version
                await send_fn(websocket, payload)
            await asyncio.sleep(poll_interval)

    except WebSocketDisconnect:
        logger.info("%s client disconnected", label)
    finally:
        if manages_capture:
            release_capture()


async def control_websocket(websocket: WebSocket) -> None:
    await _run_streaming_websocket(
        websocket,
        label="Control",
        stream_fn=get_control_data,
        send_fn=lambda ws, data: ws.send_json(data),
        manages_capture=True,
    )


async def preview_websocket(websocket: WebSocket) -> None:
    await _run_streaming_websocket(
        websocket,
        label="Preview",
        stream_fn=get_preview_frame,
        send_fn=lambda ws, data: ws.send_bytes(data),
        manages_capture=False,
    )
