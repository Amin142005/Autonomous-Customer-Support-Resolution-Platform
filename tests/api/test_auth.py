import jwt
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.api.auth import router as auth_router
from backend.app.core.config import Settings, get_settings
from backend.app.core.database import create_tables
from backend.app.models.entities import Profile


@pytest_asyncio.fixture
async def auth_app(monkeypatch):
    settings = Settings(
        _env_file=None,
        demo_mode=True,
        jwt_secret="test-secret-with-at-least-32-characters",
    )
    monkeypatch.setattr(
        "backend.app.api.auth.get_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        "backend.app.core.security.get_settings",
        lambda: settings,
    )
    get_settings.cache_clear()

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await create_tables(engine)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        session.add_all(
            [
                Profile(
                    id="viewer-id",
                    email="vic.viewer@clouddesk.demo",
                    full_name="Vic Chen",
                    role="viewer",
                ),
                Profile(
                    id="agent-id",
                    email="sam.agent@clouddesk.demo",
                    full_name="Sam Rivera",
                    role="agent",
                ),
            ]
        )
        await session.commit()

    app = FastAPI()
    app.include_router(auth_router, prefix="/api/v1")
    app.state.session_factory = session_factory

    yield app
    await engine.dispose()


async def test_demo_token_contains_expected_claims(auth_app):
    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/auth/demo-token",
            json={"email": "sam.agent@clouddesk.demo"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 28800
    assert body["user"]["role"] == "agent"

    payload = jwt.decode(
        body["access_token"],
        "test-secret-with-at-least-32-characters",
        algorithms=["HS256"],
    )
    assert payload["sub"] == "agent-id"
    assert payload["role"] == "agent"
    assert payload["exp"] - payload["iat"] == 28800


async def test_demo_token_rejects_unknown_user(auth_app):
    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/auth/demo-token",
            json={"email": "missing@clouddesk.demo"},
        )
    assert response.status_code == 404


async def test_me_returns_authenticated_profile(auth_app):
    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://testserver",
    ) as client:
        issued = await client.post(
            "/api/v1/auth/demo-token",
            json={"email": "vic.viewer@clouddesk.demo"},
        )
        token = issued.json()["access_token"]
        me = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert me.status_code == 200
    assert me.json() == {
        "id": "viewer-id",
        "email": "vic.viewer@clouddesk.demo",
        "full_name": "Vic Chen",
        "role": "viewer",
    }


async def test_me_requires_bearer_token(auth_app):
    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
