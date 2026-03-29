from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any
from uuid import UUID

from backend.app.schemas.command import CommandResponse
from backend.app.services.decision.safety import apply_safety_overrides
from backend.app.services.decision.smoother import PulseSmoother
from backend.app.services.inference.parser import ParsedDecision

logger = logging.getLogger(__name__)

# Zone classification → heading/throttle when model's continuous values are unreliable
_ZONE_DECISION: dict[tuple[str, str, str], tuple[int, float]] = {
    # (left, center, right) → (heading_deg, throttle)
    ("CLEAR", "CLEAR", "CLEAR"): (0, 0.8),
    ("CLEAR", "CLEAR", "BLOCKED"): (-20, 0.7),
    ("BLOCKED", "CLEAR", "CLEAR"): (20, 0.7),
    ("BLOCKED", "CLEAR", "BLOCKED"): (0, 0.5),
    ("CLEAR", "BLOCKED", "CLEAR"): (-45, 0.5),  # prefer left when both open
    ("CLEAR", "BLOCKED", "BLOCKED"): (-45, 0.5),
    ("BLOCKED", "BLOCKED", "CLEAR"): (45, 0.5),
    ("BLOCKED", "BLOCKED", "BLOCKED"): (0, 0.0),
}


class DecisionPolicy:
    """Safety-first policy that maps parsed model decisions to command responses."""

    def __init__(
        self,
        min_confidence: float,
        max_pulse_ms: int,
        min_pulse_ms: int,
        forward_pwm_base: int,
        turn_pwm_base: int,
    ) -> None:
        self._min_confidence = min_confidence
        self._smoother = PulseSmoother(
            max_pulse_ms=max_pulse_ms,
            min_pulse_ms=min_pulse_ms,
            forward_pwm_base=forward_pwm_base,
            turn_pwm_base=turn_pwm_base,
        )

    def to_command(
        self,
        decision: ParsedDecision,
        trace_id: UUID,
        session_id: UUID,
        seq: int,
        backend_latency_ms: int,
        model_latency_ms: int,
        estop_active: bool = False,
        cv_data: dict[str, Any] | None = None,
    ) -> CommandResponse:
        """Return final command after zone validation, safety overrides, and pulse shaping."""

        decision = self._apply_zone_validation(decision)

        safety = apply_safety_overrides(
            decision=decision,
            min_confidence=self._min_confidence,
            estop_active=estop_active,
        )
        pulse = self._smoother.shape(safety.heading_deg, safety.throttle, decision.confidence)

        return CommandResponse(
            trace_id=trace_id,
            session_id=session_id,
            seq=seq,
            heading_deg=safety.heading_deg,
            throttle=safety.throttle,
            left_pwm=pulse.left_pwm,
            right_pwm=pulse.right_pwm,
            duration_ms=pulse.duration_ms,
            confidence=decision.confidence,
            reason_code=safety.reason_code,
            message=safety.message,
            backend_latency_ms=backend_latency_ms,
            model_latency_ms=model_latency_ms,
            safe_to_execute=safety.safe_to_execute,
        )

    @staticmethod
    def _apply_zone_validation(decision: ParsedDecision) -> ParsedDecision:
        """Derive heading/throttle from the model's own zone classifications.

        VLMs are good at classifying zones (CLEAR/BLOCKED) but bad at producing
        consistent continuous heading_deg/throttle values — they memorize prompt
        examples instead of reasoning about each frame.

        This trusts the model's zone analysis (classification task) and derives
        heading/throttle deterministically from it, keeping the VLM as the
        primary decision-maker for what it sees in the image.
        """
        raw = decision.raw_json
        left = raw.get("left_zone", "").upper()
        center = raw.get("center_zone", "").upper()
        right = raw.get("right_zone", "").upper()

        zone_key = (left, center, right)
        if zone_key not in _ZONE_DECISION:
            # Zones not recognized — trust model's raw output as-is
            return decision

        zone_heading, zone_throttle = _ZONE_DECISION[zone_key]

        # Check if model's heading/throttle is consistent with its own zones
        heading_consistent = _is_direction_consistent(decision.heading_deg, zone_heading)
        throttle_consistent = (
            (zone_throttle == 0.0 and decision.throttle <= 0.0)
            or (zone_throttle > 0.0 and decision.throttle > 0.0)
        )

        if heading_consistent and throttle_consistent:
            # Model is consistent with its own zone analysis — use model values
            return decision

        # Model's continuous values contradict its zone analysis — use zone-derived values
        logger.info(
            "zone_correction",
            extra={
                "zones": f"L={left} C={center} R={right}",
                "zone_heading": zone_heading,
                "zone_throttle": zone_throttle,
                "model_heading": decision.heading_deg,
                "model_throttle": decision.throttle,
            },
        )
        return replace(
            decision,
            heading_deg=zone_heading,
            throttle=zone_throttle,
            reason_code="ZONE_CORRECTED",
        )


def _is_direction_consistent(model_heading: int, zone_heading: int) -> bool:
    """Check if model heading agrees directionally with zone-derived heading."""
    if zone_heading == 0:
        # Zone says straight — model should be roughly straight (within ±20)
        return abs(model_heading) <= 20
    if zone_heading < 0:
        # Zone says turn left — model should also be negative
        return model_heading < 0
    # Zone says turn right — model should also be positive
    return model_heading > 0
