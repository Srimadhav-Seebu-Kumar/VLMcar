from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.api.routes.control import router as control_router
from backend.app.api.routes.system import router as system_router
from backend.app.core.config import AppSettings, get_settings
from backend.app.core.logging import configure_logging
from backend.app.services.storage import init_db

logger = logging.getLogger(__name__)


def create_app(settings: AppSettings | None = None) -> FastAPI:
    """Create and configure the FastAPI application instance."""

    app_settings = settings or get_settings()
    app_settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(app_settings.log_level)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        init_db(app_settings.database_url)
        logger.info(
            "backend_startup",
            extra={"model": app_settings.ollama_model, "environment": app_settings.app_env},
        )
        yield
        logger.info("backend_shutdown", extra={"environment": app_settings.app_env})

    app = FastAPI(
        title="Zero-Shot RC Car Backend",
        version=app_settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.include_router(system_router)
    app.include_router(control_router)

    return app


app = create_app()
