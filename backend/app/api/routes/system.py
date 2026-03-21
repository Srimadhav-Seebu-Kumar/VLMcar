from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request

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


@router.post("/estop")
def activate_estop(request: Request) -> dict[str, object]:
    """Activate remote emergency stop. All subsequent commands will be STOP."""

    request.app.state.estop_active = True
    return {
        "estop_active": True,
        "timestamp": datetime.now(tz=UTC).isoformat(),
    }


@router.delete("/estop")
def clear_estop(request: Request) -> dict[str, object]:
    """Clear remote emergency stop. Normal operation resumes."""

    request.app.state.estop_active = False
    return {
        "estop_active": False,
        "timestamp": datetime.now(tz=UTC).isoformat(),
    }


@router.get("/estop")
def estop_status(request: Request) -> dict[str, object]:
    """Return current remote emergency stop state."""

    return {
        "estop_active": getattr(request.app.state, "estop_active", False),
        "timestamp": datetime.now(tz=UTC).isoformat(),
    }
