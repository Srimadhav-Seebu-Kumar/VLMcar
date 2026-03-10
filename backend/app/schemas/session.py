from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.enums import SessionStatus


class SessionMetadata(BaseModel):
    """Session lifecycle record used for traceability and replay."""

    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    device_id: str = Field(min_length=1, max_length=64)
    prompt_version: str = Field(min_length=1, max_length=64)
    model_name: str = Field(min_length=1, max_length=128)
    operator_notes: str | None = Field(default=None, max_length=512)
    started_at_ms: int = Field(ge=0)
    ended_at_ms: int | None = Field(default=None, ge=0)
    status: SessionStatus
