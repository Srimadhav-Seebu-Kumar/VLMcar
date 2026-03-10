from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.core.config import AppSettings
from backend.app.main import create_app


def build_test_settings() -> AppSettings:
    return AppSettings(
        app_env="test",
        log_level="INFO",
        ollama_model="llava-test",
        artifacts_dir=Path("./tmp_artifacts"),
    )


def test_health_endpoint_returns_expected_payload() -> None:
    app = create_app(settings=build_test_settings())
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "zero-shot-rc-car-backend"
    assert payload["environment"] == "test"


def test_version_endpoint_returns_model_and_version() -> None:
    app = create_app(settings=build_test_settings())
    with TestClient(app) as client:
        response = client.get("/version")

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == "0.1.0"
    assert payload["model"] == "llava-test"
    assert payload["environment"] == "test"
