from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.enums import AckStatus


class AckRequest(BaseModel):
    """Bot acknowledgment sent after executing a command, signaling readiness."""

    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(min_length=1, max_length=64)
    session_id: UUID
    seq: int = Field(ge=0)
    status: AckStatus


class AckResponse(BaseModel):
    """Backend response to bot ack, telling it whether to send the next frame."""

    model_config = ConfigDict(extra="forbid")

    status: str
    request_frame: bool
    session_id: UUID
