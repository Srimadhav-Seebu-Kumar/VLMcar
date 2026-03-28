from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.enums import DeviceMode


class TelemetryPayload(BaseModel):
    """Periodic telemetry message from firmware to backend."""

    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(min_length=1, max_length=64)
    session_id: UUID | None = None
    timestamp_ms: int = Field(ge=0)
    uptime_ms: int = Field(ge=0)
    free_heap_bytes: int = Field(ge=0)
    wifi_rssi_dbm: int = Field(ge=-120, le=0)
    battery_mv: int = Field(ge=0)
    frame_counter: int = Field(ge=0)
    avg_loop_latency_ms: float = Field(ge=0)
    last_heading_deg: int | None = Field(default=None, ge=-90, le=90)
    last_throttle: float | None = Field(default=None, ge=0.0, le=1.0)
    last_error: str | None = Field(default=None, max_length=256)
    mode: DeviceMode
