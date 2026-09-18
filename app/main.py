"""FastAPI application entrypoint.

Run with:  uvicorn app.main:app --reload --port 8001
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.internal_auth import InternalServiceAuthMiddleware
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.infrastructure.backend.client import create_http_client

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    app.state.http_client = create_http_client()
    logger.info("%s started — backend=%s", settings.app_name, settings.backend_base_url)
    try:
        yield
    finally:
        await app.state.http_client.aclose()
        logger.info("%s stopped", settings.app_name)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Rosewood AI — property & rent assistant",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(InternalServiceAuthMiddleware)

    app.include_router(api_router)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name}

    return app


app = create_app()
