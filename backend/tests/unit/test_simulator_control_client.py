from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from simulator.control_client import BackendControlClient, BackendControlError, ControlFrameRequest


def _valid_command_payload(action: str = "STOP") -> dict[str, object]:
    return {
        "trace_id": str(uuid4()),
        "session_id": str(uuid4()),
        "seq": 1,
        "action": action,
        "left_pwm": 0,
        "right_pwm": 0,
        "duration_ms": 0,
        "confidence": 1.0,
        "reason_code": "TEST",
        "message": "ok",
        "backend_latency_ms": 2,
        "model_latency_ms": 1,
        "safe_to_execute": True,
    }


def test_control_client_sends_frame_and_parses_command() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/control/frame"
        assert request.headers["content-type"].startswith("multipart/form-data")
        return httpx.Response(status_code=200, json=_valid_command_payload(action="FORWARD"))

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = BackendControlClient(
            frame_url="http://test/api/v1/control/frame",
            http_client=http_client,
        )
        command = client.send_frame(
            ControlFrameRequest(
                image_jpeg=b"fake-jpeg",
                device_id="sim-device",
                seq=1,
                timestamp_ms=1710000000000,
                frame_width=320,
                frame_height=240,
                jpeg_quality=80,
            )
        )

    assert command.action.value == "FORWARD"
    assert command.seq == 1


def test_control_client_raises_on_non_200() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=500, text="boom")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = BackendControlClient(
            frame_url="http://test/api/v1/control/frame",
            http_client=http_client,
        )
        with pytest.raises(BackendControlError):
            client.send_frame(
                ControlFrameRequest(
                    image_jpeg=b"fake-jpeg",
                    device_id="sim-device",
                    seq=1,
                    timestamp_ms=1710000000000,
                    frame_width=320,
                    frame_height=240,
                    jpeg_quality=80,
                )
            )
