from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.app.core import security
from backend.app.core.config import Settings
from backend.app.core.security import require_role
from backend.app.schemas.common import Role

TEST_SECRET = "test-secret-with-at-least-32-characters"


def _token(secret: str, role: str = "viewer", *, expires: datetime | None = None) -> str:
    return jwt.encode(
        {
            "sub": "user-1",
            "email": "user@clouddesk.demo",
            "role": role,
            "exp": expires or datetime.now(UTC) + timedelta(minutes=5),
        },
        secret,
        algorithm="HS256",
    )


@pytest.fixture(autouse=True)
def jwt_settings(monkeypatch):
    settings = Settings(
        _env_file=None,
        jwt_secret="test-secret-with-at-least-32-characters",
        supabase_jwt_secret="",
    )
    monkeypatch.setattr(security, "get_settings", lambda: settings)


@pytest.fixture
def role_app():
    app = FastAPI()

    @app.get("/viewer")
    async def viewer(user=Depends(security.get_current_user)):  # noqa: B008
        return {"id": user.id, "role": user.role}

    @app.get("/agent", dependencies=[Depends(require_role(Role.AGENT))])
    async def agent():
        return {"ok": True}

    @app.get("/admin", dependencies=[Depends(require_role("admin"))])
    async def admin():
        return {"ok": True}

    return app


def test_missing_or_invalid_jwt_is_401(role_app):
    client = TestClient(role_app)
    assert client.get("/viewer").status_code == 401
    assert client.get("/agent", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_role_order_is_enforced(role_app):
    client = TestClient(role_app)

    viewer = {"Authorization": f"Bearer {_token(TEST_SECRET, 'viewer')}"}
    agent = {"Authorization": f"Bearer {_token(TEST_SECRET, 'agent')}"}
    admin = {"Authorization": f"Bearer {_token(TEST_SECRET, 'admin')}"}

    assert client.get("/agent", headers=viewer).status_code == 403
    assert client.get("/agent", headers=agent).status_code == 200
    assert client.get("/admin", headers=agent).status_code == 403
    assert client.get("/admin", headers=admin).status_code == 200


def test_expired_and_wrong_secret_tokens_are_401(role_app):
    client = TestClient(role_app)
    expired = _token(
        TEST_SECRET,
        expires=datetime.now(UTC) - timedelta(minutes=1),
    )
    wrong_secret = _token("wrong-secret-with-at-least-32-characters")
    headers_expired = {"Authorization": f"Bearer {expired}"}
    headers_wrong = {"Authorization": f"Bearer {wrong_secret}"}

    assert client.get("/agent", headers=headers_expired).status_code == 401
    assert client.get("/agent", headers=headers_wrong).status_code == 401
