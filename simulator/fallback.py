from __future__ import annotations

from uuid import UUID, uuid4

from backend.app.schemas.command import CommandResponse
from backend.app.schemas.enums import Action


def build_stop_command(
    *,
    seq: int,
    session_id: UUID,
    reason_code: str,
    message: str,
    safe_to_execute: bool,
) -> CommandResponse:
    """Build a local STOP fallback command for simulator-side failures."""

    return CommandResponse(
        trace_id=uuid4(),
        session_id=session_id,
        seq=seq,
        action=Action.STOP,
        left_pwm=0,
        right_pwm=0,
        duration_ms=0,
        confidence=1.0,
        reason_code=reason_code,
        message=message[:256],
        backend_latency_ms=0,
        model_latency_ms=0,
        safe_to_execute=safe_to_execute,
    )
