from __future__ import annotations

from dataclasses import dataclass

from backend.app.services.inference.parser import ParsedDecision


@dataclass(frozen=True)
class SafetyOutcome:
    """Safety override output for downstream policy shaping."""

    heading_deg: int
    throttle: float
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
            heading_deg=0,
            throttle=0.0,
            reason_code="ESTOP_ACTIVE",
            message="emergency stop mode is active",
            safe_to_execute=False,
        )

    if decision.confidence < min_confidence:
        return SafetyOutcome(
            heading_deg=0,
            throttle=0.0,
            reason_code="LOW_CONFIDENCE",
            message="model confidence below threshold",
            safe_to_execute=False,
        )

    if decision.throttle <= 0.0:
        return SafetyOutcome(
            heading_deg=0,
            throttle=0.0,
            reason_code=decision.reason_code,
            message=decision.scene_summary or "model chose stop",
            safe_to_execute=True,
        )

    return SafetyOutcome(
        heading_deg=decision.heading_deg,
        throttle=decision.throttle,
        reason_code=decision.reason_code,
        message=decision.scene_summary or f"heading={decision.heading_deg} throttle={decision.throttle}",
        safe_to_execute=True,
    )
