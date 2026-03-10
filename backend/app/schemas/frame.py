from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.enums import DeviceMode


class GpsData(BaseModel):
    """Optional location payload for future sensor extension."""

    model_config = ConfigDict(extra="forbid")

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class FrameRequest(BaseModel):
    """Metadata contract accompanying an uploaded frame."""

    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(min_length=1, max_length=64)
    session_id: UUID | None = None
    seq: int = Field(ge=0)
    timestamp_ms: int = Field(ge=0)
    frame_width: int = Field(ge=1, le=4096)
    frame_height: int = Field(ge=1, le=4096)
    jpeg_quality: int = Field(ge=1, le=63)
    battery_mv: int | None = Field(default=None, ge=0)
    mode: DeviceMode
    firmware_version: str | None = Field(default=None, max_length=64)
    ir_left: float | None = None
    ir_right: float | None = None
    gps: GpsData | None = None
