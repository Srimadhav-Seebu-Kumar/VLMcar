from __future__ import annotations

from typing import cast

from fastapi import Request

from backend.app.core.config import AppSettings
from backend.app.services.inference.base import InferenceAdapter


def get_app_settings(request: Request) -> AppSettings:
    """FastAPI dependency to retrieve shared application settings."""

    return cast(AppSettings, request.app.state.settings)


def get_inference_adapter(request: Request) -> InferenceAdapter:
    """FastAPI dependency to retrieve configured inference adapter."""

    return cast(InferenceAdapter, request.app.state.inference_adapter)
