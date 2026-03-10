from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.api.deps import get_app_settings
from backend.app.core.config import AppSettings

router = APIRouter(tags=["system"])


@router.get("/health")
def health(settings: Annotated[AppSettings, Depends(get_app_settings)]) -> dict[str, object]:
    """Liveness endpoint for backend and edge connectivity checks."""

    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
        "timestamp": datetime.now(tz=UTC).isoformat(),
    }


@router.get("/version")
def version(settings: Annotated[AppSettings, Depends(get_app_settings)]) -> dict[str, object]:
    """Return backend and model version metadata."""

    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "model": settings.ollama_model,
        "environment": settings.app_env,
    }
