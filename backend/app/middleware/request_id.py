from __future__ import annotations

import re
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.app.core.logging import log_context

REQUEST_ID_HEADER = b"x-request-id"
_SAFE_REQUEST_ID = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z")


def _request_id(headers: list[tuple[bytes, bytes]]) -> str:
    for name, value in headers:
        if name.lower() != REQUEST_ID_HEADER:
            continue
        try:
            candidate = value.decode("ascii").strip()
        except UnicodeDecodeError:
            break
        if _SAFE_REQUEST_ID.fullmatch(candidate):
            return candidate
        break
    return str(uuid4())


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _request_id(scope.get("headers", []))
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() != REQUEST_ID_HEADER
                ]
                headers.append((REQUEST_ID_HEADER, request_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        with log_context(request_id=request_id):
            await self.app(scope, receive, send_with_request_id)
