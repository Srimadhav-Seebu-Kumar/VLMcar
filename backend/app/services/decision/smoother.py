from __future__ import annotations

from dataclasses import dataclass

from backend.app.schemas.enums import Action


@dataclass(frozen=True)
class PulseShape:
    """Bounded low-level motion pulse output."""

    left_pwm: int
    right_pwm: int
    duration_ms: int


def clamp_pwm(value: int) -> int:
    """Clamp PWM to valid 8-bit motor controller range."""

    return max(0, min(255, value))


class PulseSmoother:
    """Convert high-level action and confidence into short safe pulses."""

    def __init__(
        self,
        max_pulse_ms: int,
        min_pulse_ms: int,
        forward_pwm_base: int,
        turn_pwm_base: int,
    ) -> None:
        self._max_pulse_ms = max_pulse_ms
        self._min_pulse_ms = min_pulse_ms
        self._forward_pwm_base = forward_pwm_base
        self._turn_pwm_base = turn_pwm_base

    def shape(self, action: Action, confidence: float) -> PulseShape:
        if action is Action.STOP:
            return PulseShape(left_pwm=0, right_pwm=0, duration_ms=0)

        bounded_confidence = max(0.0, min(1.0, confidence))
        pulse_span = max(self._max_pulse_ms - self._min_pulse_ms, 0)
        duration_ms = self._min_pulse_ms + int(pulse_span * bounded_confidence)

        if action is Action.FORWARD:
            pwm = clamp_pwm(self._forward_pwm_base + int(20 * bounded_confidence))
            return PulseShape(left_pwm=pwm, right_pwm=pwm, duration_ms=duration_ms)

        if action is Action.LEFT:
            return PulseShape(
                left_pwm=clamp_pwm(self._turn_pwm_base - 25),
                right_pwm=clamp_pwm(self._turn_pwm_base + 20),
                duration_ms=duration_ms,
            )

        return PulseShape(
            left_pwm=clamp_pwm(self._turn_pwm_base + 20),
            right_pwm=clamp_pwm(self._turn_pwm_base - 25),
            duration_ms=duration_ms,
        )
