from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlalchemy import select

from backend.app.core.config import AppSettings
from backend.app.main import create_app
from backend.app.services.inference import InferenceError, InferenceRequest, InferenceResult
from backend.app.services.storage import (
    DecisionRepository,
    ErrorRecord,
    FrameRepository,
    clear_cached_db_handles,
    session_scope,
)


class StubStopAdapter:
    async def infer(self, request: InferenceRequest) -> InferenceResult:
        _ = request
        return InferenceResult(
            raw_output='{"left_zone":"CLEAR","center_zone":"BLOCKED","right_zone":"CLEAR","heading_deg":0,"throttle":0.0,"confidence":0.9}',
            model_latency_ms=12,
            provider_payload={"provider": "stub-stop"},
        )


class StubForwardAdapter:
    async def infer(self, request: InferenceRequest) -> InferenceResult:
        _ = request
        return InferenceResult(
            raw_output='{"left_zone":"CLEAR","center_zone":"CLEAR","right_zone":"CLEAR","heading_deg":0,"throttle":0.8,"confidence":0.92}',
            model_latency_ms=15,
            provider_payload={"provider": "stub-forward"},
        )


class StubParseErrorAdapter:
    async def infer(self, request: InferenceRequest) -> InferenceResult:
        _ = request
        return InferenceResult(
            raw_output="not-json",
            model_latency_ms=10,
            provider_payload={"provider": "stub-bad"},
        )


class StubInferenceErrorAdapter:
    async def infer(self, request: InferenceRequest) -> InferenceResult:
        _ = request
        raise InferenceError("simulated adapter failure")


def build_test_settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        app_env="test",
        log_level="INFO",
        ollama_model="llava-test",
        artifacts_dir=tmp_path / "artifacts",
        database_url=f"sqlite:///{tmp_path / 'control_route_test.db'}",
        prompt_version="v5",
        quality_min_score=0.0,
        quality_min_blur_score=0.0,
    )


def build_test_app(tmp_path: Path, adapter: Any) -> tuple[Any, AppSettings]:
    clear_cached_db_handles()
    settings = build_test_settings(tmp_path=tmp_path)
    app = create_app(settings=settings)
    app.state.inference_adapter = adapter
    return app, settings


def make_jpeg_bytes() -> bytes:
    image = Image.new("RGB", (32, 32), color=(120, 120, 120))
    draw = ImageDraw.Draw(image)
    draw.rectangle((2, 2, 14, 14), fill=(255, 0, 0))
    draw.rectangle((18, 2, 30, 14), fill=(0, 255, 0))
    draw.rectangle((2, 18, 14, 30), fill=(0, 0, 255))
    draw.rectangle((18, 18, 30, 30), fill=(255, 255, 0))
    draw.line((0, 0, 31, 31), fill=(255, 255, 255), width=2)

    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def make_dark_jpeg_bytes() -> bytes:
    image = Image.new("RGB", (32, 32), color=(1, 1, 1))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def post_frame(client: TestClient, image_bytes: bytes) -> Any:
    return client.post(
        "/api/v1/control/frame",
        data={
            "device_id": "rc-car-01",
            "seq": "12",
            "timestamp_ms": "1710000000000",
            "frame_width": "320",
            "frame_height": "240",
            "jpeg_quality": "12",
            "mode": "AUTO",
        },
        files={"image": ("frame.jpg", image_bytes, "image/jpeg")},
    )


def test_control_frame_accepts_valid_multipart_upload(tmp_path: Path) -> None:
    app, _settings = build_test_app(tmp_path=tmp_path, adapter=StubStopAdapter())
    with TestClient(app) as client:
        response = post_frame(client, make_jpeg_bytes())

    assert response.status_code == 200
    payload = response.json()
    assert payload["throttle"] == 0.0
    assert payload["heading_deg"] == 0


def test_control_frame_uses_inference_pipeline_for_forward(tmp_path: Path) -> None:
    app, _settings = build_test_app(tmp_path=tmp_path, adapter=StubForwardAdapter())
    with TestClient(app) as client:
        response = post_frame(client, make_jpeg_bytes())

    assert response.status_code == 200
    payload = response.json()
    assert payload["throttle"] > 0
    assert payload["left_pwm"] > 0
    assert payload["duration_ms"] > 0


def test_control_frame_rejects_invalid_content_type(tmp_path: Path) -> None:
    app, _settings = build_test_app(tmp_path=tmp_path, adapter=StubStopAdapter())
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/control/frame",
            data={
                "device_id": "rc-car-01",
                "seq": "12",
                "timestamp_ms": "1710000000000",
                "frame_width": "320",
                "frame_height": "240",
                "jpeg_quality": "12",
                "mode": "AUTO",
            },
            files={"image": ("frame.png", b"not-jpeg", "image/png")},
        )

    assert response.status_code == 415


def test_control_frame_rejects_missing_required_fields(tmp_path: Path) -> None:
    app, _settings = build_test_app(tmp_path=tmp_path, adapter=StubStopAdapter())
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/control/frame",
            data={
                "device_id": "rc-car-01",
                "timestamp_ms": "1710000000000",
                "frame_width": "320",
                "frame_height": "240",
                "jpeg_quality": "12",
                "mode": "AUTO",
            },
            files={"image": ("frame.jpg", make_jpeg_bytes(), "image/jpeg")},
        )

    assert response.status_code == 422


def test_control_frame_persists_frame_and_decision_records(tmp_path: Path) -> None:
    app, settings = build_test_app(tmp_path=tmp_path, adapter=StubStopAdapter())

    with TestClient(app) as client:
        response = post_frame(client, make_jpeg_bytes())

    assert response.status_code == 200
    payload = response.json()
    with session_scope(settings.database_url) as db:
        frames = FrameRepository(db).list_by_session(payload["session_id"])
        decisions = DecisionRepository(db).list_by_session(payload["session_id"])

    assert len(frames) == 1
    assert Path(frames[0].file_path).exists()
    assert len(decisions) == 1


def test_control_frame_returns_early_stop_for_dark_frame(tmp_path: Path) -> None:
    app, _settings = build_test_app(tmp_path=tmp_path, adapter=StubForwardAdapter())

    with TestClient(app) as client:
        response = post_frame(client, make_dark_jpeg_bytes())

    assert response.status_code == 200
    payload = response.json()
    assert payload["throttle"] == 0.0
    assert payload["reason_code"] == "FRAME_TOO_DARK"


def test_control_frame_returns_parse_error_stop_and_logs_error(tmp_path: Path) -> None:
    app, settings = build_test_app(tmp_path=tmp_path, adapter=StubParseErrorAdapter())

    with TestClient(app) as client:
        response = post_frame(client, make_jpeg_bytes())

    assert response.status_code == 200
    payload = response.json()
    assert payload["reason_code"] == "PARSE_ERROR"

    with session_scope(settings.database_url) as db:
        errors = list(db.scalars(select(ErrorRecord)))
    assert len(errors) == 1
    assert errors[0].error_code == "PARSE_ERROR"


def test_control_frame_returns_inference_error_stop_and_logs_error(tmp_path: Path) -> None:
    app, settings = build_test_app(tmp_path=tmp_path, adapter=StubInferenceErrorAdapter())

    with TestClient(app) as client:
        response = post_frame(client, make_jpeg_bytes())

    assert response.status_code == 200
    payload = response.json()
    assert payload["reason_code"] == "INFERENCE_ERROR"

    with session_scope(settings.database_url) as db:
        errors = list(db.scalars(select(ErrorRecord)))
    assert len(errors) == 1
    assert errors[0].error_code == "INFERENCE_ERROR"
