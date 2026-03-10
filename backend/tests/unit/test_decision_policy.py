from __future__ import annotations

from uuid import uuid4

from backend.app.schemas.enums import Action
from backend.app.services.decision import DecisionPolicy
from backend.app.services.inference.parser import ParsedDecision


def make_decision(action: Action, confidence: float) -> ParsedDecision:
    return ParsedDecision(
        action=action,
        confidence=confidence,
        reason_code="TEST_REASON",
        scene_summary="test scene",
        hazards=[],
        raw_json={},
    )


def test_decision_policy_overrides_to_stop_for_low_confidence() -> None:
    policy = DecisionPolicy(
        min_confidence=0.6,
        max_pulse_ms=400,
        min_pulse_ms=120,
        forward_pwm_base=120,
        turn_pwm_base=105,
    )
    command = policy.to_command(
        decision=make_decision(Action.FORWARD, confidence=0.4),
        trace_id=uuid4(),
        session_id=uuid4(),
        seq=1,
        backend_latency_ms=50,
        model_latency_ms=30,
        estop_active=False,
    )

    assert command.action is Action.STOP
    assert command.reason_code == "LOW_CONFIDENCE"
    assert command.safe_to_execute is False


def test_decision_policy_applies_estop_override() -> None:
    policy = DecisionPolicy(
        min_confidence=0.2,
        max_pulse_ms=400,
        min_pulse_ms=120,
        forward_pwm_base=120,
        turn_pwm_base=105,
    )
    command = policy.to_command(
        decision=make_decision(Action.RIGHT, confidence=0.9),
        trace_id=uuid4(),
        session_id=uuid4(),
        seq=2,
        backend_latency_ms=40,
        model_latency_ms=25,
        estop_active=True,
    )

    assert command.action is Action.STOP
    assert command.reason_code == "ESTOP_ACTIVE"
    assert command.safe_to_execute is False


def test_decision_policy_shapes_forward_pulse_within_bounds() -> None:
    policy = DecisionPolicy(
        min_confidence=0.2,
        max_pulse_ms=350,
        min_pulse_ms=100,
        forward_pwm_base=110,
        turn_pwm_base=100,
    )
    command = policy.to_command(
        decision=make_decision(Action.FORWARD, confidence=0.8),
        trace_id=uuid4(),
        session_id=uuid4(),
        seq=3,
        backend_latency_ms=60,
        model_latency_ms=35,
        estop_active=False,
    )

    assert command.action is Action.FORWARD
    assert 0 < command.left_pwm <= 255
    assert command.left_pwm == command.right_pwm
    assert 100 <= command.duration_ms <= 350
