from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.api.knowledge import router as knowledge_router
from backend.app.core.config import Settings
from backend.app.schemas.common import Role
from backend.app.services.knowledge_service import KnowledgeService

KNOWLEDGE_DIR = Path(__file__).parents[2] / "sample_data" / "knowledge_base"
TEST_SECRET = "test-secret-with-at-least-32-characters"


@pytest_asyncio.fixture
async def knowledge_app(monkeypatch):
    settings = Settings(
        _env_file=None,
        demo_mode=True,
        jwt_secret=TEST_SECRET,
        vector_store="memory",
        sample_data_dir=str(KNOWLEDGE_DIR.parent),
    )
    monkeypatch.setattr(
        "backend.app.core.security.get_settings",
        lambda: settings,
    )
    service = KnowledgeService.from_settings(
        settings,
        articles_dir=KNOWLEDGE_DIR,
    )
    await service.initialize()
    app = FastAPI()
    app.include_router(knowledge_router, prefix="/api/v1")
    app.state.knowledge_service = service
    return app


def token_for(role: Role) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": f"{role.value}-id",
            "email": f"{role.value}@clouddesk.demo",
            "role": role.value,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        TEST_SECRET,
        algorithm="HS256",
    )


def auth_headers(role: Role) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_for(role)}"}


async def test_knowledge_list_detail_and_search(knowledge_app):
    async with AsyncClient(
        transport=ASGITransport(app=knowledge_app),
        base_url="http://testserver",
    ) as client:
        unauthorized = await client.get("/api/v1/knowledge")
        listed = await client.get(
            "/api/v1/knowledge",
            headers=auth_headers(Role.VIEWER),
        )
        article = await client.get(
            "/api/v1/knowledge/mfa-recovery",
            headers=auth_headers(Role.VIEWER),
        )
        missing = await client.get(
            "/api/v1/knowledge/missing",
            headers=auth_headers(Role.VIEWER),
        )
        search = await client.post(
            "/api/v1/knowledge/search",
            json={
                "query": "API 429 retry backoff",
                "category": "api_failure",
                "mode": "hybrid",
                "top_k": 3,
            },
            headers=auth_headers(Role.VIEWER),
        )

    assert unauthorized.status_code == 401
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 15
    assert listed.json()["items"][0]["id"] == "api-authentication"
    assert article.status_code == 200
    assert article.json()["title"] == "MFA Recovery"
    assert "# Resolution" in article.json()["content"]
    assert missing.status_code == 404
    assert search.status_code == 200
    assert search.json()["items"][0]["article_id"] == "api-rate-limits"
    assert search.json()["items"][0]["source"].startswith("kb://api-rate-limits#")


async def test_knowledge_search_validates_request(knowledge_app):
    async with AsyncClient(
        transport=ASGITransport(app=knowledge_app),
        base_url="http://testserver",
    ) as client:
        blank_query = await client.post(
            "/api/v1/knowledge/search",
            json={"query": "   "},
            headers=auth_headers(Role.VIEWER),
        )
        excessive_top_k = await client.post(
            "/api/v1/knowledge/search",
            json={"query": "login", "top_k": 21},
            headers=auth_headers(Role.VIEWER),
        )

    assert blank_query.status_code == 422
    assert excessive_top_k.status_code == 422


async def test_reindex_is_admin_only_and_rebuilds_index(knowledge_app):
    async with AsyncClient(
        transport=ASGITransport(app=knowledge_app),
        base_url="http://testserver",
    ) as client:
        forbidden = await client.post(
            "/api/v1/knowledge/reindex",
            headers=auth_headers(Role.AGENT),
        )
        reindexed = await client.post(
            "/api/v1/knowledge/reindex",
            headers=auth_headers(Role.ADMIN),
        )

    assert forbidden.status_code == 403
    assert reindexed.status_code == 200
    assert reindexed.json()["articles_indexed"] == 15
    assert reindexed.json()["chunks_indexed"] > 15
