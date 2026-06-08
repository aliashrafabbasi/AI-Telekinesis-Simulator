from typing import Literal

from pydantic import BaseModel, Field


class HandFramePayload(BaseModel):
    x: float = -1.0
    y: float = -1.0
    gesture: Literal["open", "punch", "none"] = "none"
    clap: bool = False
    hands: int = 0
    palm_dist: float = -1.0
    frame_w: int | None = None
    frame_h: int | None = None
    ts: int | None = None
    frame: str | None = None
    tracking: bool = False
    speed: float = Field(default=0.0, ge=0.0)
