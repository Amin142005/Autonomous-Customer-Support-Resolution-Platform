from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp

from backend.app.api.health import router as health_router
from backend.app.core.config import get_settings
from backend.app.core.logging import setup_logging
from backend.app.middleware.request_id import RequestIdMiddleware


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    yield


def create_app() -> ASGIApp:
    settings = get_settings()
    fastapi_app = FastAPI(title="CloudDesk Support API", lifespan=lifespan)
    fastapi_app.include_router(health_router)

    cors_app = CORSMiddleware(
        app=fastapi_app,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    return RequestIdMiddleware(cors_app)


app = create_app()
