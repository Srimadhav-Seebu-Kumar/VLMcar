from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.app.schemas import Action, CommandResponse, DeviceMode, FrameRequest


def test_pydantic_frame_request_accepts_valid_mode() -> None:
    frame = FrameRequest(
        device_id="rc-car-01",
        session_id=uuid4(),
        seq=10,
        timestamp_ms=1710000000000,
        frame_width=320,
        frame_height=240,
        jpeg_quality=12,
        battery_mv=7420,
        mode=DeviceMode.AUTO,
    )
    assert frame.mode is DeviceMode.AUTO


def test_pydantic_command_rejects_invalid_action() -> None:
    with pytest.raises(ValidationError):
        CommandResponse.model_validate(
            {
                "trace_id": str(uuid4()),
                "session_id": str(uuid4()),
                "seq": 1,
                "action": "REVERSE",
                "left_pwm": 0,
                "right_pwm": 0,
                "duration_ms": 0,
                "confidence": 1.0,
                "reason_code": "SAFE_DEFAULT",
                "message": "invalid",
                "backend_latency_ms": 10,
                "model_latency_ms": 0,
                "safe_to_execute": False,
            }
        )


def test_pydantic_command_accepts_enum_action() -> None:
    response = CommandResponse(
        trace_id=uuid4(),
        session_id=uuid4(),
        seq=2,
        action=Action.STOP,
        left_pwm=0,
        right_pwm=0,
        duration_ms=0,
        confidence=1.0,
        reason_code="SAFE_DEFAULT",
        message="stop",
        backend_latency_ms=11,
        model_latency_ms=3,
        safe_to_execute=True,
    )
    assert response.action is Action.STOP
