from __future__ import annotations

from typing import Any

import jwt
from sqlalchemy.exc import SQLAlchemyError
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.app.core.config import get_settings
from backend.app.models.entities import AuditLog


class AuditMiddleware:
    def __init__(self, app: ASGIApp, session_factory: Any | None = None) -> None:
        self.app = app
        self.session_factory = session_factory

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = str(scope.get("method", "GET")).upper()
        if method == "GET":
            await self.app(scope, receive, send)
            return

        status_code: int | None = None

        async def send_with_status(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_with_status)
        except Exception:
            status_code = 500
            raise
        finally:
            await self._record(scope, method, status_code)

    async def _record(
        self,
        scope: Scope,
        method: str,
        status_code: int | None,
    ) -> None:
        if method in {"HEAD", "OPTIONS"}:
            return

        session_factory = self.session_factory
        if session_factory is None:
            application = scope.get("app")
            if application is not None:
                session_factory = getattr(application.state, "session_factory", None)
        if session_factory is None:
            return

        state = scope.get("state", {})
        request_id = state.get("request_id")
        path = str(scope.get("path", "") or "")

        try:
            async with session_factory() as session:
                session.add(
                    AuditLog(
                        actor_id=self._actor_id(scope),
                        method=method,
                        path=path,
                        status_code=status_code,
                        request_id=request_id,
                        data=None,
                    )
                )
                await session.commit()
        except (SQLAlchemyError, OSError, RuntimeError):
            return

    @staticmethod
    def _actor_id(scope: Scope) -> str | None:
        authorization = None
        for name, value in scope.get("headers", []):
            if name.lower() == b"authorization":
                try:
                    authorization = value.decode("ascii")
                except UnicodeDecodeError:
                    return None
                break
        if authorization is None:
            return None

        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None

        secret = get_settings().effective_jwt_secret
        if not secret:
            return None

        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                options={"require": ["sub"], "verify_exp": False},
            )
        except jwt.PyJWTError:
            return None

        subject = payload.get("sub")
        return subject if isinstance(subject, str) and subject else None