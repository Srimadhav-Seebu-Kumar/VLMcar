from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from backend.app.services.inference import ParseError, StructuredOutputParser
from backend.app.services.decision import DecisionPolicy


def prompts_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "prompts"


def v4_schema_path() -> Path:
    return prompts_dir() / "json_schema_decision_v4.json"


def v5_schema_path() -> Path:
    return prompts_dir() / "json_schema_decision_v5.json"


def _v4_json(action: str, confidence: float = 0.9) -> str:
    return json.dumps({
        "left_zone": "CLEAR",
        "center_zone": "CLEAR",
        "right_zone": "CLEAR",
        "action": action,
        "confidence": confidence,
    })


# --- v4 action → continuous conversion tests ---


def test_v4_forward_converts_to_heading_0_throttle_08() -> None:
    parser = StructuredOutputParser(schema_path=v4_schema_path())
    parsed = parser.parse(_v4_json("FORWARD"))

    assert parsed.heading_deg == 0
    assert parsed.throttle == pytest.approx(0.8)


def test_v4_left_converts_to_heading_neg45_throttle_05() -> None:
    parser = StructuredOutputParser(schema_path=v4_schema_path())
    parsed = parser.parse(_v4_json("LEFT"))

    assert parsed.heading_deg == -45
    assert parsed.throttle == pytest.approx(0.5)


def test_v4_right_converts_to_heading_pos45_throttle_05() -> None:
    parser = StructuredOutputParser(schema_path=v4_schema_path())
    parsed = parser.parse(_v4_json("RIGHT"))

    assert parsed.heading_deg == 45
    assert parsed.throttle == pytest.approx(0.5)


def test_v4_stop_converts_to_heading_0_throttle_0() -> None:
    parser = StructuredOutputParser(schema_path=v4_schema_path())
    parsed = parser.parse(_v4_json("STOP"))

    assert parsed.heading_deg == 0
    assert parsed.throttle == pytest.approx(0.0)


def test_v4_unknown_action_defaults_to_stop() -> None:
    """Unknown action values should safely default to stop."""
    schema = json.loads(v4_schema_path().read_text(encoding="utf-8"))
    # Temporarily allow extra action value for this test
    schema["properties"]["action"]["enum"].append("REVERSE")
    tmp_schema = v4_schema_path().parent / "_tmp_test_schema.json"
    tmp_schema.write_text(json.dumps(schema), encoding="utf-8")
    try:
        parser = StructuredOutputParser(schema_path=tmp_schema)
        raw = json.dumps({
            "left_zone": "CLEAR",
            "center_zone": "CLEAR",
            "right_zone": "CLEAR",
            "action": "REVERSE",
            "confidence": 0.8,
        })
        parsed = parser.parse(raw)
        assert parsed.heading_deg == 0
        assert parsed.throttle == pytest.approx(0.0)
    finally:
        tmp_schema.unlink(missing_ok=True)


# --- v5 passthrough test ---


def test_v5_heading_throttle_passthrough_unchanged() -> None:
    """v5 output with explicit heading_deg/throttle should not be converted."""
    parser = StructuredOutputParser(schema_path=v5_schema_path())
    parsed = parser.parse(json.dumps({
        "left_zone": "CLEAR",
        "center_zone": "BLOCKED",
        "right_zone": "CLEAR",
        "heading_deg": -30,
        "throttle": 0.6,
        "confidence": 0.85,
    }))

    assert parsed.heading_deg == -30
    assert parsed.throttle == pytest.approx(0.6)
    assert parsed.confidence == pytest.approx(0.85)


# --- Regression test: v4 FORWARD through full pipeline produces nonzero PWM ---


def test_v4_forward_through_full_pipeline_produces_nonzero_pwm() -> None:
    """Regression: v4 FORWARD must produce left_pwm > 0, right_pwm > 0.

    This is the exact bug that caused the car to always stop.
    """
    parser = StructuredOutputParser(schema_path=v4_schema_path())
    parsed = parser.parse(_v4_json("FORWARD", confidence=0.9))

    policy = DecisionPolicy(
        min_confidence=0.3,
        max_pulse_ms=400,
        min_pulse_ms=120,
        forward_pwm_base=120,
        turn_pwm_base=105,
    )
    command = policy.to_command(
        decision=parsed,
        trace_id=uuid4(),
        session_id=uuid4(),
        seq=1,
        backend_latency_ms=0,
        model_latency_ms=100,
        estop_active=False,
    )

    assert command.throttle > 0, "FORWARD must produce nonzero throttle"
    assert command.left_pwm > 0, "FORWARD must produce nonzero left_pwm"
    assert command.right_pwm > 0, "FORWARD must produce nonzero right_pwm"
    assert command.duration_ms > 0, "FORWARD must produce nonzero duration"
    assert command.safe_to_execute is True


def test_v4_left_through_full_pipeline_produces_differential_pwm() -> None:
    """LEFT action with center blocked should produce turn-left PWM."""
    parser = StructuredOutputParser(schema_path=v4_schema_path())
    # Zones consistent with LEFT action: center blocked, left clear
    raw = json.dumps({
        "left_zone": "CLEAR",
        "center_zone": "BLOCKED",
        "right_zone": "BLOCKED",
        "action": "LEFT",
        "confidence": 0.8,
    })
    parsed = parser.parse(raw)

    policy = DecisionPolicy(
        min_confidence=0.3,
        max_pulse_ms=400,
        min_pulse_ms=120,
        forward_pwm_base=120,
        turn_pwm_base=105,
    )
    command = policy.to_command(
        decision=parsed,
        trace_id=uuid4(),
        session_id=uuid4(),
        seq=2,
        backend_latency_ms=0,
        model_latency_ms=100,
        estop_active=False,
    )

    assert command.throttle > 0
    assert command.right_pwm > command.left_pwm, "LEFT should turn left (right motor faster)"
    assert command.safe_to_execute is True
