from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from backend.app.core.config import AppSettings
from backend.app.main import create_app
from backend.app.services.storage import (
    DecisionRepository,
    FrameRepository,
    clear_cached_db_handles,
    session_scope,
)


def build_test_settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        app_env="test",
        log_level="INFO",
        ollama_model="llava-test",
        artifacts_dir=tmp_path / "artifacts",
        database_url=f"sqlite:///{tmp_path / 'control_route_test.db'}",
    )


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


def test_control_frame_accepts_valid_multipart_upload(tmp_path: Path) -> None:
    clear_cached_db_handles()
    app = create_app(settings=build_test_settings(tmp_path=tmp_path))
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
            files={"image": ("frame.jpg", make_jpeg_bytes(), "image/jpeg")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "STOP"
    assert payload["reason_code"] == "PLACEHOLDER_STOP"
    assert payload["seq"] == 12


def test_control_frame_rejects_invalid_content_type(tmp_path: Path) -> None:
    clear_cached_db_handles()
    app = create_app(settings=build_test_settings(tmp_path=tmp_path))
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
    clear_cached_db_handles()
    app = create_app(settings=build_test_settings(tmp_path=tmp_path))
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


def test_control_frame_persists_frame_record_and_file(tmp_path: Path) -> None:
    clear_cached_db_handles()
    settings = build_test_settings(tmp_path=tmp_path)
    app = create_app(settings=settings)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/control/frame",
            data={
                "device_id": "rc-car-01",
                "seq": "101",
                "timestamp_ms": "1710000001234",
                "frame_width": "320",
                "frame_height": "240",
                "jpeg_quality": "12",
                "mode": "AUTO",
            },
            files={"image": ("frame.jpg", make_jpeg_bytes(), "image/jpeg")},
        )

    assert response.status_code == 200
    payload = response.json()
    with session_scope(settings.database_url) as db:
        frames = FrameRepository(db).list_by_session(payload["session_id"])
        decisions = DecisionRepository(db).list_by_session(payload["session_id"])

    assert len(frames) == 1
    frame = frames[0]
    assert frame.quality_score is not None
    assert Path(frame.file_path).exists()
    assert len(decisions) == 1


def test_control_frame_returns_early_stop_for_dark_frame(tmp_path: Path) -> None:
    clear_cached_db_handles()
    app = create_app(settings=build_test_settings(tmp_path=tmp_path))

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/control/frame",
            data={
                "device_id": "rc-car-01",
                "seq": "77",
                "timestamp_ms": "1710000005555",
                "frame_width": "320",
                "frame_height": "240",
                "jpeg_quality": "12",
                "mode": "AUTO",
            },
            files={"image": ("frame.jpg", make_dark_jpeg_bytes(), "image/jpeg")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "STOP"
    assert payload["reason_code"] == "FRAME_TOO_DARK"
