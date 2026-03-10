from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from backend.app.core.config import AppSettings
from backend.app.main import create_app
from backend.app.services.storage import FrameRepository, clear_cached_db_handles, session_scope


def build_test_settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        app_env="test",
        log_level="INFO",
        ollama_model="llava-test",
        artifacts_dir=tmp_path / "artifacts",
        database_url=f"sqlite:///{tmp_path / 'control_route_test.db'}",
    )


def make_jpeg_bytes() -> bytes:
    image = Image.new("RGB", (16, 16), color=(255, 0, 0))
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

    assert len(frames) == 1
    frame = frames[0]
    assert frame.quality_score is not None
    assert Path(frame.file_path).exists()
