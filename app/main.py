import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.auth.router import router as auth_router
from app.db.session import check_database_connection, engine
from app.exceptions import AuthError
from app.hand_tracking import get_tracker, is_capture_active, stop_capture_loop
from app.logging_config import configure_logging
from app.settings import settings
from app.websocket import control_websocket, preview_websocket

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_runtime()
    await check_database_connection()
    logger.info("Database connection verified (%s)", settings.environment)
    yield
    stop_capture_loop()
    await engine.dispose()


app = FastAPI(title="Gotham Telekinesis", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


@app.exception_handler(AuthError)
async def auth_error_handler(_request: Request, exc: AuthError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation failed", "code": "validation_error", "errors": exc.errors()},
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(_request: Request, exc: StarletteHTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail, "code": "http_error"},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(_request: Request, exc: Exception):
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "code": "internal_error"},
    )


@app.get("/")
def root():
    return {
        "service": "Gotham Telekinesis",
        "version": "1.0.0",
        "environment": settings.environment,
        "status": "running",
        "auth": {
            "register": "/auth/register",
            "login": "/auth/login",
            "me": "/auth/me",
            "logout": "/auth/logout",
        },
        "websocket": "/ws?token=<jwt>",
        "preview": "/ws/preview?token=<jwt>",
        "health": {
            "live": "/health/live",
            "ready": "/health/ready",
            "legacy": "/health",
        },
    }


@app.get("/health/live")
def health_live():
    return {"status": "alive"}


@app.get("/health/ready")
async def health_ready():
    tracker = get_tracker()
    try:
        await check_database_connection()
        db_ok = True
    except Exception:
        logger.warning("Readiness check: database unavailable")
        db_ok = False

    capture_active = is_capture_active()
    camera_ok = tracker.camera_open if capture_active else True

    ready = db_ok and camera_ok
    body = {
        "status": "ready" if ready else "not_ready",
        "database": db_ok,
        "capture_active": capture_active,
        "camera": camera_ok,
        "frames_processed": tracker.frames_processed,
        "read_failures": tracker.read_failure_count,
    }

    if not ready:
        return JSONResponse(status_code=503, content=body)
    return body


@app.get("/health")
def health():
    """Legacy health endpoint for simple uptime checks."""
    tracker = get_tracker()
    capture_active = is_capture_active()
    return {
        "status": "ok",
        "capture_active": capture_active,
        "camera": tracker.camera_open if capture_active else None,
        "frames_processed": tracker.frames_processed,
        "read_failures": tracker.read_failure_count,
    }


@app.websocket("/ws")
async def ws_route(websocket: WebSocket):
    await control_websocket(websocket)


@app.websocket("/ws/preview")
async def ws_preview_route(websocket: WebSocket):
    await preview_websocket(websocket)
