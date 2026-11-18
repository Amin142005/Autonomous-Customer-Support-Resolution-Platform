from __future__ import annotations

import json
import time
from typing import Any

from redis.exceptions import RedisError
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.app.core.config import get_settings
from backend.app.core.redis import create_redis_client


class FixedWindowRateLimiter:
    def __init__(
        self,
        limit: int,
        window_seconds: int = 60,
        redis_client: Any | None = None,
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.redis_client = redis_client

    async def check(self, client_key: str) -> tuple[bool, int, int]:
        now = int(time.time())
        window = now // self.window_seconds
        reset = (window + 1) * self.window_seconds
        key = f"rl:{client_key}:{window}"

        client = self.redis_client or await create_redis_client()
        try:
            count = await client.incr(key)
            if count == 1:
                await client.expire(key, self.window_seconds)
        except (RedisError, OSError, ConnectionError, TimeoutError):
            return True, self.limit, reset

        remaining = max(0, self.limit - count)
        return count <= self.limit, remaining, reset


class RateLimitMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        limiter: FixedWindowRateLimiter | None = None,
    ) -> None:
        self.app = app
        settings = get_settings()
        self.limiter = limiter or FixedWindowRateLimiter(
            limit=settings.rate_limit_per_minute,
            window_seconds=60,
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        client_ip = client[0] if client else "unknown"
        allowed, remaining, reset = await self.limiter.check(client_ip)

        if not allowed:
            retry_after = max(1, reset - int(time.time()))
            body = json.dumps({"detail": "Rate limit exceeded"}).encode("utf-8")
            headers = [
                (b"content-type", b"application/json"),
                (b"x-ratelimit-limit", str(self.limiter.limit).encode("ascii")),
                (b"x-ratelimit-remaining", b"0"),
                (b"x-ratelimit-reset", str(reset).encode("ascii")),
                (b"retry-after", str(retry_after).encode("ascii")),
            ]
            await send(
                {
                    "type": "http.response.start",
                    "status": 429,
                    "headers": headers,
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        async def send_with_limit_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"x-ratelimit-limit", str(self.limiter.limit).encode("ascii")),
                        (b"x-ratelimit-remaining", str(remaining).encode("ascii")),
                        (b"x-ratelimit-reset", str(reset).encode("ascii")),
                    ]
                )
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_limit_headers)
