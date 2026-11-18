from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp

from backend.app.api.auth import router as auth_router
from backend.app.api.health import router as health_router
from backend.app.core.config import get_settings
from backend.app.core.database import create_database_engine, create_tables
from backend.app.core.logging import setup_logging
from backend.app.middleware.audit import AuditMiddleware
from backend.app.middleware.rate_limit import RateLimitMiddleware
from backend.app.middleware.request_id import RequestIdMiddleware
from backend.app.services.seed_service import bootstrap_demo_data


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    settings = get_settings()
    engine = create_database_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app.state.database_engine = engine
    app.state.session_factory = session_factory
    try:
        await create_tables(engine)
        if settings.demo_mode:
            async with session_factory() as session:
                await bootstrap_demo_data(session, settings.sample_data_dir)
        yield
    finally:
        await engine.dispose()


def create_app() -> ASGIApp:
    settings = get_settings()
    fastapi_app = FastAPI(title="CloudDesk Support API", lifespan=lifespan)
    fastapi_app.include_router(health_router)
    fastapi_app.include_router(auth_router, prefix="/api/v1")

    cors_app = CORSMiddleware(
        app=fastapi_app,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    limited_app = RateLimitMiddleware(cors_app)
    audited_app = AuditMiddleware(limited_app)
    return RequestIdMiddleware(audited_app)


app = create_app()
