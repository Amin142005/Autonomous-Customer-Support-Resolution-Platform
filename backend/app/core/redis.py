from __future__ import annotations

from typing import Any, Protocol

import fakeredis.aioredis
import redis.asyncio as redis_async

from backend.app.core.config import get_settings


class RedisProtocol(Protocol):
    async def incr(self, name: str) -> int: ...

    async def expire(self, name: str, seconds: int) -> bool: ...

    async def ttl(self, name: str) -> int: ...

    async def eval(self, script: str, numkeys: int, *keys_and_args: Any) -> Any: ...

    async def ping(self) -> bool: ...

    async def aclose(self) -> None: ...


_memory_client: fakeredis.aioredis.FakeRedis | None = None
_redis_client: redis_async.Redis | None = None


async def create_redis_client() -> RedisProtocol:
    global _memory_client, _redis_client

    settings = get_settings()
    if settings.use_fake_redis or not settings.redis_url:
        if _memory_client is None:
            _memory_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
        return _memory_client

    if _redis_client is None:
        _redis_client = redis_async.from_url(
            settings.redis_url,
            decode_responses=True,
        )
    return _redis_client


get_redis = create_redis_client


async def reset_redis_clients() -> None:
    global _memory_client, _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
    if _memory_client is not None:
        await _memory_client.aclose()
    _redis_client = None
    _memory_client = None
