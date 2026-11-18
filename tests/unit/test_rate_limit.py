import fakeredis.aioredis
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.core.config import get_settings
from backend.app.core.redis import create_redis_client
from backend.app.middleware.rate_limit import (
    FixedWindowRateLimiter,
    RateLimitMiddleware,
)


@pytest.fixture
def fake_redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


async def test_fixed_window_allows_limit_then_rejects(fake_redis):
    limiter = FixedWindowRateLimiter(
        limit=3,
        window_seconds=60,
        redis_client=fake_redis,
    )

    results = [await limiter.check("test-client") for _ in range(4)]

    assert [allowed for allowed, _, _ in results] == [True, True, True, False]
    assert results[0][1] == 2
    assert results[2][1] == 0
    assert results[3][1] == 0


async def test_fixed_window_separates_clients(fake_redis):
    limiter = FixedWindowRateLimiter(
        limit=1,
        window_seconds=60,
        redis_client=fake_redis,
    )

    first = await limiter.check("client-a")
    second = await limiter.check("client-b")
    repeated = await limiter.check("client-a")

    assert first[0] is True
    assert second[0] is True
    assert repeated[0] is False


def test_middleware_returns_429_and_limit_headers(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(
        "backend.app.middleware.rate_limit.get_settings",
        lambda: settings.model_copy(update={"rate_limit_per_minute": 2}),
    )
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    limiter = FixedWindowRateLimiter(
        limit=2,
        window_seconds=60,
        redis_client=fake_redis,
    )

    app = FastAPI()

    @app.get("/limited")
    async def limited():
        return {"ok": True}

    application = RateLimitMiddleware(app, limiter=limiter)
    client = TestClient(application)

    assert client.get("/limited").status_code == 200
    assert client.get("/limited").status_code == 200
    blocked = client.get("/limited")
    assert blocked.status_code == 429
    assert blocked.json() == {"detail": "Rate limit exceeded"}
    assert blocked.headers["x-ratelimit-limit"] == "2"
    assert blocked.headers["retry-after"]


async def test_redis_factory_uses_fakeredis(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(
        "backend.app.core.redis.get_settings",
        lambda: settings.model_copy(
            update={"redis_url": "", "use_fake_redis": True}
        ),
    )
    client = await create_redis_client()
    await client.set("rate-limit-check", "ok")
    assert await client.get("rate-limit-check") == "ok"
