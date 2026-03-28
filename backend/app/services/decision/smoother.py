from __future__ import annotations

from dataclasses import dataclass


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
    """Convert continuous heading + throttle into short safe motor pulses.

    Differential steering model:
    - heading_deg=0 → equal PWM on both motors (straight)
    - heading_deg>0 → left motor faster (turn right)
    - heading_deg<0 → right motor faster (turn left)
    """

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

    def shape(self, heading_deg: int, throttle: float, confidence: float) -> PulseShape:
        if throttle <= 0.0:
            return PulseShape(left_pwm=0, right_pwm=0, duration_ms=0)

        bounded_throttle = max(0.0, min(1.0, throttle))
        bounded_confidence = max(0.0, min(1.0, confidence))

        # Duration from confidence
        pulse_span = max(self._max_pulse_ms - self._min_pulse_ms, 0)
        duration_ms = self._min_pulse_ms + int(pulse_span * bounded_confidence)

        # Base PWM scaled by throttle
        base_pwm = self._forward_pwm_base * bounded_throttle

        # Differential steering from heading
        clamped_heading = max(-90, min(90, heading_deg))
        turn_ratio = clamped_heading / 90.0

        left_pwm = clamp_pwm(int(base_pwm * (1.0 + turn_ratio)))
        right_pwm = clamp_pwm(int(base_pwm * (1.0 - turn_ratio)))

        return PulseShape(left_pwm=left_pwm, right_pwm=right_pwm, duration_ms=duration_ms)
