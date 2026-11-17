from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import Request
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.app.models.entities import Base


def create_database_engine(database_url: str) -> AsyncEngine:
    url = make_url(database_url)
    if (
        url.get_backend_name() == "sqlite"
        and url.database not in (None, "", ":memory:")
    ):
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    return create_async_engine(database_url, pool_pre_ping=True)


async def create_tables(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        yield session
