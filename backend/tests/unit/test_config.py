from __future__ import annotations

from pathlib import Path

from pytest import MonkeyPatch

from backend.app.core.config import AppSettings, get_settings


def test_settings_load_from_explicit_environment_values() -> None:
    settings = AppSettings(
        app_env="test",
        log_level="DEBUG",
        backend_port=9001,
        ollama_model="llava:latest",
    )
    assert settings.app_env == "test"
    assert settings.log_level == "DEBUG"
    assert settings.backend_port == 9001
    assert settings.ollama_model == "llava:latest"


def test_get_settings_reads_environment(monkeypatch: MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "ci")
    monkeypatch.setenv("ARTIFACTS_DIR", "./tmp_test_artifacts")

    settings = get_settings()
    assert settings.app_env == "ci"
    assert settings.artifacts_dir == Path("./tmp_test_artifacts")

    get_settings.cache_clear()
