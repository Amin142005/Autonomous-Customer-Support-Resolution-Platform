import jwt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.core.database import create_tables
from backend.app.middleware.audit import AuditMiddleware
from backend.app.middleware.request_id import RequestIdMiddleware
from backend.app.models.entities import AuditLog


@pytest.fixture
async def audit_app(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await create_tables(engine)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    app = FastAPI()
    app.state.session_factory = session_factory

    @app.get("/items")
    async def list_items():
        return {"items": []}

    @app.post("/items")
    async def create_item():
        return {"created": True}

    application = RequestIdMiddleware(AuditMiddleware(app, session_factory))
    yield application, session_factory
    await engine.dispose()


async def test_audit_records_state_changing_request(audit_app):
    application, session_factory = audit_app
    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/items",
            headers={"X-Request-ID": "audit-request-1"},
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "audit-request-1"

    async with session_factory() as session:
        rows = (await session.execute(AuditLog.__table__.select())).all()

    assert len(rows) == 1
    row = rows[0]._mapping
    assert row["method"] == "POST"
    assert row["path"] == "/items"
    assert row["status_code"] == 200
    assert row["request_id"] == "audit-request-1"
    assert row["data"] is None


async def test_audit_does_not_record_get(audit_app):
    application, session_factory = audit_app
    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/items")

    assert response.status_code == 200
    async with session_factory() as session:
        rows = (await session.execute(AuditLog.__table__.select())).all()
    assert rows == []


async def test_audit_records_actor_from_valid_bearer_token(
    audit_app,
    monkeypatch,
):
    application, session_factory = audit_app
    secret = "test-secret-with-at-least-32-characters"
    monkeypatch.setattr(
        "backend.app.middleware.audit.get_settings",
        lambda: __import__(
            "backend.app.core.config",
            fromlist=["Settings"],
        ).Settings(_env_file=None, jwt_secret=secret),
    )

    token = jwt.encode({"sub": "profile-123"}, secret, algorithm="HS256")
    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/items",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    async with session_factory() as session:
        row = (await session.scalars(select(AuditLog))).first()
    assert row is not None
    assert row.actor_id == "profile-123"