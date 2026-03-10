from __future__ import annotations

import time
from io import BytesIO
from typing import cast

from fastapi.testclient import TestClient
from PIL import Image

from simulator.mock_backend import MockBackendConfig, create_mock_app


def make_jpeg() -> bytes:
    image = Image.new("RGB", (20, 20), color=(10, 200, 10))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def post_frame(client: TestClient, seq: int = 1) -> dict[str, object]:
    response = client.post(
        "/api/v1/control/frame",
        data={
            "device_id": "rc-car-01",
            "seq": str(seq),
            "timestamp_ms": "1710000000000",
            "frame_width": "320",
            "frame_height": "240",
            "jpeg_quality": "12",
            "mode": "AUTO",
        },
        files={"image": ("frame.jpg", make_jpeg(), "image/jpeg")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, dict)
    return cast(dict[str, object], payload)


def test_mock_backend_always_stop_scenario() -> None:
    app = create_mock_app(MockBackendConfig(scenario="always_stop"))
    with TestClient(app) as client:
        payload = post_frame(client)
    assert payload["action"] == "STOP"


def test_mock_backend_always_forward_scenario() -> None:
    app = create_mock_app(MockBackendConfig(scenario="always_forward"))
    with TestClient(app) as client:
        payload = post_frame(client)
    assert payload["action"] == "FORWARD"


def test_mock_backend_alternating_turn_scenario() -> None:
    app = create_mock_app(MockBackendConfig(scenario="alternating_turns"))
    with TestClient(app) as client:
        first = post_frame(client, seq=1)
        second = post_frame(client, seq=2)
    assert first["action"] == "LEFT"
    assert second["action"] == "RIGHT"


def test_mock_backend_timeout_scenario_delays_response() -> None:
    app = create_mock_app(MockBackendConfig(scenario="timeout", timeout_seconds=0.05))
    with TestClient(app) as client:
        start = time.perf_counter()
        payload = post_frame(client)
        elapsed = time.perf_counter() - start

    assert payload["action"] == "STOP"
    assert elapsed >= 0.05
