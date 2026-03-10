from __future__ import annotations

from typing import cast

from fastapi import Request

from backend.app.core.config import AppSettings
from backend.app.services.decision import DecisionPolicy
from backend.app.services.inference import InferenceAdapter, PromptManager, StructuredOutputParser


def get_app_settings(request: Request) -> AppSettings:
    """FastAPI dependency to retrieve shared application settings."""

    return cast(AppSettings, request.app.state.settings)


def get_inference_adapter(request: Request) -> InferenceAdapter:
    """FastAPI dependency to retrieve configured inference adapter."""

    return cast(InferenceAdapter, request.app.state.inference_adapter)


def get_prompt_manager(request: Request) -> PromptManager:
    """FastAPI dependency to retrieve prompt manager singleton."""

    return cast(PromptManager, request.app.state.prompt_manager)


def get_output_parser(request: Request) -> StructuredOutputParser:
    """FastAPI dependency to retrieve structured model output parser."""

    return cast(StructuredOutputParser, request.app.state.output_parser)


def get_decision_policy(request: Request) -> DecisionPolicy:
    """FastAPI dependency to retrieve decision policy singleton."""

    return cast(DecisionPolicy, request.app.state.decision_policy)
