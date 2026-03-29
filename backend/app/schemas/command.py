from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CommandResponse(BaseModel):
    """Action command returned to firmware for next motion pulse.

    Uses continuous heading + throttle instead of discrete actions:
    - heading_deg: steering angle from -90 (full left) to +90 (full right), 0 = straight
    - throttle: speed from 0.0 (stop) to 1.0 (full speed)
    """

    model_config = ConfigDict(extra="forbid")

    trace_id: UUID
    session_id: UUID
    seq: int = Field(ge=0)
    heading_deg: int = Field(ge=-90, le=90)
    throttle: float = Field(ge=0.0, le=1.0)
    left_pwm: int = Field(ge=0, le=255)
    right_pwm: int = Field(ge=0, le=255)
    duration_ms: int = Field(ge=0, le=500)
    confidence: float = Field(ge=0.0, le=1.0)
    reason_code: str = Field(min_length=1, max_length=64)
    message: str = Field(max_length=256)
    backend_latency_ms: int = Field(ge=0)
    model_latency_ms: int = Field(ge=0)
    safe_to_execute: bool
