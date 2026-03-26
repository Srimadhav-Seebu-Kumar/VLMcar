from __future__ import annotations

from dataclasses import dataclass

from backend.app.schemas.enums import Action
from backend.app.services.inference.parser import ParsedDecision


@dataclass(frozen=True)
class SafetyOutcome:
    """Safety override output for downstream policy shaping."""

    action: Action
    reason_code: str
    message: str
    safe_to_execute: bool


def apply_safety_overrides(
    decision: ParsedDecision,
    min_confidence: float,
    estop_active: bool,
) -> SafetyOutcome:
    """Apply deterministic safety rules before command shaping."""

    if estop_active:
        return SafetyOutcome(
            action=Action.STOP,
            reason_code="ESTOP_ACTIVE",
            message="emergency stop mode is active",
            safe_to_execute=False,
        )

    if decision.confidence < min_confidence:
        return SafetyOutcome(
            action=Action.STOP,
            reason_code="LOW_CONFIDENCE",
            message="model confidence below threshold",
            safe_to_execute=False,
        )

    if decision.action is Action.STOP:
        return SafetyOutcome(
            action=Action.STOP,
            reason_code=decision.reason_code,
            message=decision.scene_summary or "model chose STOP",
            safe_to_execute=True,
        )

    return SafetyOutcome(
        action=decision.action,
        reason_code=decision.reason_code,
        message=decision.scene_summary or decision.action.value,
        safe_to_execute=True,
    )
