"""Tests for zone-based validation logic in DecisionPolicy."""
from __future__ import annotations

from uuid import uuid4

import pytest

from backend.app.services.decision import DecisionPolicy
from backend.app.services.inference.parser import ParsedDecision


def _make_decision(
    heading_deg: int = 0,
    throttle: float = 0.0,
    confidence: float = 0.7,
    left_zone: str = "CLEAR",
    center_zone: str = "CLEAR",
    right_zone: str = "CLEAR",
) -> ParsedDecision:
    return ParsedDecision(
        heading_deg=heading_deg,
        throttle=throttle,
        confidence=confidence,
        reason_code="MODEL_DECISION",
        scene_summary="",
        hazards=[],
        raw_json={
            "left_zone": left_zone,
            "center_zone": center_zone,
            "right_zone": right_zone,
            "heading_deg": heading_deg,
            "throttle": throttle,
            "confidence": confidence,
        },
    )


def _make_policy() -> DecisionPolicy:
    return DecisionPolicy(
        min_confidence=0.3,
        max_pulse_ms=400,
        min_pulse_ms=120,
        forward_pwm_base=120,
        turn_pwm_base=105,
    )


def _to_command(policy, decision):
    return policy.to_command(
        decision=decision,
        trace_id=uuid4(),
        session_id=uuid4(),
        seq=1,
        backend_latency_ms=0,
        model_latency_ms=100,
        estop_active=False,
    )


# --- Zone correction: model heading contradicts its own zones ---


def test_zones_clear_but_model_turns_left_corrected_to_straight() -> None:
    """All zones CLEAR but model says heading=-30 → corrected to straight."""
    policy = _make_policy()
    decision = _make_decision(
        heading_deg=-30, throttle=0.5,
        left_zone="CLEAR", center_zone="CLEAR", right_zone="CLEAR",
    )

    cmd = _to_command(policy, decision)

    assert cmd.heading_deg == 0, "All CLEAR → should go straight"
    assert cmd.throttle == pytest.approx(0.8)
    assert cmd.reason_code == "ZONE_CORRECTED"


def test_center_blocked_left_clear_model_goes_straight_corrected_to_left() -> None:
    """Center BLOCKED, left CLEAR, but model says heading=0 → corrected to left."""
    policy = _make_policy()
    decision = _make_decision(
        heading_deg=0, throttle=0.8,
        left_zone="CLEAR", center_zone="BLOCKED", right_zone="BLOCKED",
    )

    cmd = _to_command(policy, decision)

    assert cmd.heading_deg == -45, "Left clear → should turn left"
    assert cmd.throttle == pytest.approx(0.5)
    assert cmd.reason_code == "ZONE_CORRECTED"


def test_center_blocked_right_clear_model_turns_left_corrected_to_right() -> None:
    """Center BLOCKED, right CLEAR, but model says heading=-30 → corrected to RIGHT."""
    policy = _make_policy()
    decision = _make_decision(
        heading_deg=-30, throttle=0.5,
        left_zone="BLOCKED", center_zone="BLOCKED", right_zone="CLEAR",
    )

    cmd = _to_command(policy, decision)

    assert cmd.heading_deg == 45, "Right clear → should turn right"
    assert cmd.throttle == pytest.approx(0.5)
    assert cmd.left_pwm > cmd.right_pwm, "RIGHT turn: left motor faster"
    assert cmd.reason_code == "ZONE_CORRECTED"


def test_all_blocked_model_drives_corrected_to_stop() -> None:
    """All BLOCKED but model says throttle=0.5 → corrected to stop."""
    policy = _make_policy()
    decision = _make_decision(
        heading_deg=-30, throttle=0.5,
        left_zone="BLOCKED", center_zone="BLOCKED", right_zone="BLOCKED",
    )

    cmd = _to_command(policy, decision)

    assert cmd.throttle == 0.0, "All blocked → must stop"
    assert cmd.heading_deg == 0


# --- Consistent model output: no correction needed ---


def test_consistent_forward_no_correction() -> None:
    """All CLEAR, model says heading=0 throttle=0.9 → no correction."""
    policy = _make_policy()
    decision = _make_decision(
        heading_deg=0, throttle=0.9,
        left_zone="CLEAR", center_zone="CLEAR", right_zone="CLEAR",
    )

    cmd = _to_command(policy, decision)

    assert cmd.heading_deg == 0
    assert cmd.throttle == pytest.approx(0.9)
    assert cmd.reason_code == "MODEL_DECISION"


def test_consistent_left_turn_no_correction() -> None:
    """Center BLOCKED + left CLEAR, model says heading=-40 → consistent, no correction."""
    policy = _make_policy()
    decision = _make_decision(
        heading_deg=-40, throttle=0.6,
        left_zone="CLEAR", center_zone="BLOCKED", right_zone="CLEAR",
    )

    cmd = _to_command(policy, decision)

    assert cmd.heading_deg == -40, "Model heading is consistent with zones"
    assert cmd.throttle == pytest.approx(0.6)
    assert cmd.reason_code == "MODEL_DECISION"


def test_consistent_right_turn_no_correction() -> None:
    """Center BLOCKED + right CLEAR, model says heading=+50 → consistent, no correction."""
    policy = _make_policy()
    decision = _make_decision(
        heading_deg=50, throttle=0.4,
        left_zone="BLOCKED", center_zone="BLOCKED", right_zone="CLEAR",
    )

    cmd = _to_command(policy, decision)

    assert cmd.heading_deg == 50
    assert cmd.throttle == pytest.approx(0.4)
    assert cmd.reason_code == "MODEL_DECISION"


def test_consistent_stop_no_correction() -> None:
    """All BLOCKED, model says stop → consistent, no correction."""
    policy = _make_policy()
    decision = _make_decision(
        heading_deg=0, throttle=0.0,
        left_zone="BLOCKED", center_zone="BLOCKED", right_zone="BLOCKED",
    )

    cmd = _to_command(policy, decision)

    assert cmd.throttle == 0.0


# --- Edge: no zone data in raw_json → no correction ---


def test_no_zone_data_uses_model_output() -> None:
    """Missing zones in raw_json → model output unchanged."""
    policy = _make_policy()
    decision = ParsedDecision(
        heading_deg=-30, throttle=0.5, confidence=0.8,
        reason_code="MODEL_DECISION", scene_summary="", hazards=[],
        raw_json={"heading_deg": -30, "throttle": 0.5, "confidence": 0.8},
    )

    cmd = _to_command(policy, decision)

    assert cmd.heading_deg == -30
    assert cmd.throttle == pytest.approx(0.5)
