from __future__ import annotations

from uuid import UUID

from backend.app.schemas.command import CommandResponse
from backend.app.services.decision.safety import apply_safety_overrides
from backend.app.services.decision.smoother import PulseSmoother
from backend.app.services.inference.parser import ParsedDecision


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
    ) -> CommandResponse:
        """Return final command after safety overrides and pulse shaping."""

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
