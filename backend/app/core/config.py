from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Centralized backend runtime configuration loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_env: str = Field(default="dev", validation_alias="APP_ENV")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    backend_host: str = Field(default="0.0.0.0", validation_alias="BACKEND_HOST")
    backend_port: int = Field(default=8000, ge=1, le=65535, validation_alias="BACKEND_PORT")

    database_url: str = Field(default="sqlite:///./data/rc_car.db", validation_alias="DATABASE_URL")
    artifacts_dir: Path = Field(default=Path("./data"), validation_alias="ARTIFACTS_DIR")

    ollama_base_url: str = Field(default="http://127.0.0.1:11434", validation_alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llava", validation_alias="OLLAMA_MODEL")
    model_timeout_s: int = Field(default=15, ge=1, le=120, validation_alias="MODEL_TIMEOUT_S")

    min_confidence: float = Field(default=0.55, ge=0.0, le=1.0, validation_alias="MIN_CONFIDENCE")
    max_pulse_ms: int = Field(default=400, ge=1, le=2000, validation_alias="MAX_PULSE_MS")
    quality_min_score: float = Field(
        default=0.2, ge=0.0, le=1.0, validation_alias="QUALITY_MIN_SCORE"
    )
    quality_min_brightness: float = Field(
        default=20.0, ge=0.0, le=255.0, validation_alias="QUALITY_MIN_BRIGHTNESS"
    )
    quality_max_brightness: float = Field(
        default=235.0, ge=0.0, le=255.0, validation_alias="QUALITY_MAX_BRIGHTNESS"
    )
    quality_min_blur_score: float = Field(
        default=2.0, ge=0.0, validation_alias="QUALITY_MIN_BLUR_SCORE"
    )

    app_name: str = "zero-shot-rc-car-backend"
    app_version: str = "0.1.0"


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return cached settings for process-wide use."""

    return AppSettings()
