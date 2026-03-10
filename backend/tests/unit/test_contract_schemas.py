from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from jsonschema import ValidationError, validate

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACTS_DIR = REPO_ROOT / "contracts"


@pytest.mark.parametrize(
    ("schema_name", "payload"),
    [
        (
            "frame_request.schema.json",
            {
                "device_id": "rc-car-01",
                "session_id": str(uuid4()),
                "seq": 1,
                "timestamp_ms": 1710000000000,
                "frame_width": 320,
                "frame_height": 240,
                "jpeg_quality": 12,
                "battery_mv": 7420,
                "mode": "AUTO",
                "firmware_version": "0.1.0",
                "ir_left": None,
                "ir_right": None,
                "gps": None,
            },
        ),
        (
            "command_response.schema.json",
            {
                "trace_id": str(uuid4()),
                "session_id": str(uuid4()),
                "seq": 1,
                "action": "STOP",
                "left_pwm": 0,
                "right_pwm": 0,
                "duration_ms": 0,
                "confidence": 1.0,
                "reason_code": "SAFE_DEFAULT",
                "message": "default stop",
                "backend_latency_ms": 10,
                "model_latency_ms": 0,
                "safe_to_execute": True,
            },
        ),
        (
            "telemetry.schema.json",
            {
                "device_id": "rc-car-01",
                "session_id": str(uuid4()),
                "timestamp_ms": 1710000000000,
                "uptime_ms": 5000,
                "free_heap_bytes": 204800,
                "wifi_rssi_dbm": -50,
                "battery_mv": 7380,
                "frame_counter": 17,
                "avg_loop_latency_ms": 250.5,
                "last_action": "FORWARD",
                "last_error": None,
                "mode": "AUTO",
            },
        ),
        (
            "session.schema.json",
            {
                "session_id": str(uuid4()),
                "device_id": "rc-car-01",
                "prompt_version": "v1",
                "model_name": "llava",
                "operator_notes": "lab run",
                "started_at_ms": 1710000000000,
                "ended_at_ms": None,
                "status": "ACTIVE",
            },
        ),
    ],
)
def test_schema_accepts_valid_payload(schema_name: str, payload: dict[str, object]) -> None:
    schema = json.loads((CONTRACTS_DIR / schema_name).read_text(encoding="utf-8"))
    validate(instance=payload, schema=schema)


def test_command_schema_rejects_invalid_action_enum() -> None:
    schema = json.loads((CONTRACTS_DIR / "command_response.schema.json").read_text(encoding="utf-8"))
    payload = {
        "trace_id": str(uuid4()),
        "session_id": str(uuid4()),
        "seq": 2,
        "action": "REVERSE",
        "left_pwm": 0,
        "right_pwm": 0,
        "duration_ms": 0,
        "confidence": 0.5,
        "reason_code": "INVALID_ACTION",
        "message": "bad action",
        "backend_latency_ms": 20,
        "model_latency_ms": 10,
        "safe_to_execute": False,
    }
    with pytest.raises(ValidationError):
        validate(instance=payload, schema=schema)
