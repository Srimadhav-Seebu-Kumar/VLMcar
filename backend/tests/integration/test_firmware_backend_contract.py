from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient
from jsonschema import validate
from PIL import Image

from backend.app.core.config import AppSettings
from backend.app.main import create_app
from backend.app.services.inference import InferenceRequest, InferenceResult


class ForwardAdapter:
    async def infer(self, request: InferenceRequest) -> InferenceResult:
        _ = request
        return InferenceResult(
            raw_output='{"left_zone":"CLEAR","center_zone":"CLEAR","right_zone":"CLEAR","heading_deg":0,"throttle":0.8,"confidence":0.93}',
            model_latency_ms=22,
            provider_payload={"provider": "integration-stub"},
        )


def make_jpeg() -> bytes:
    image = Image.new("RGB", (32, 32), color=(140, 140, 140))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def command_schema() -> dict[str, object]:
    schema_path = Path(__file__).resolve().parents[3] / "contracts" / "command_response.schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


def test_backend_response_matches_firmware_contract(tmp_path: Path) -> None:
    settings = AppSettings(
        app_env="test",
        log_level="INFO",
        database_url=f"sqlite:///{tmp_path / 'integration_contract.db'}",
        artifacts_dir=tmp_path / "artifacts",
        prompt_version="v5",
        quality_min_score=0.0,
        quality_min_blur_score=0.0,
    )
    app = create_app(settings=settings)
    app.state.inference_adapter = ForwardAdapter()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/control/frame",
            data={
                "device_id": "rc-car-01",
                "seq": "50",
                "timestamp_ms": "1710000000000",
                "frame_width": "320",
                "frame_height": "240",
                "jpeg_quality": "12",
                "mode": "AUTO",
                "firmware_version": "0.1.0",
            },
            files={"image": ("frame.jpg", make_jpeg(), "image/jpeg")},
        )

    assert response.status_code == 200
    payload = response.json()
    validate(instance=payload, schema=command_schema())

    assert payload["heading_deg"] == 0
    assert payload["throttle"] > 0
    UUID(payload["trace_id"])
    UUID(payload["session_id"])
    assert payload["duration_ms"] <= settings.max_pulse_ms
