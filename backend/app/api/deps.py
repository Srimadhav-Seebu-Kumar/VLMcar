from __future__ import annotations

from typing import cast

from fastapi import Request

from backend.app.core.config import AppSettings


def get_app_settings(request: Request) -> AppSettings:
    """FastAPI dependency to retrieve shared application settings."""

    return cast(AppSettings, request.app.state.settings)
