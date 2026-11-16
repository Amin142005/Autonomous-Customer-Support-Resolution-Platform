from __future__ import annotations

import json
import logging
import re
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Generator, TextIO

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_workflow_id: ContextVar[str | None] = ContextVar("workflow_id", default=None)

_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b([a-z0-9_-]*(?:api[_-]?key|secret|password|passwd|token|authorization))"
    r"(\s*[:=]\s*)(?:(?:Bearer|Basic)\s+)?(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
_BEARER_TOKEN = re.compile(r"(?i)\bBearer\s+\S+")
_JWT_TOKEN = re.compile(
    r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"
)
_URL_CREDENTIALS = re.compile(r"(?i)(\b[a-z][a-z0-9+.-]*://)[^/@\s]+@")
_SENSITIVE_QUERY_VALUE = re.compile(
    r"(?i)([?&](?:password|passwd|pwd|token|api[_-]?key|secret|authorization)=)[^&\s]+"
)
_SENSITIVE_KEY = re.compile(
    r"(?i)(?:^|[_-])(?:secret|password|passwd|token|authorization|credential|api[_-]?key)(?:$|[_-])"
)
_STANDARD_RECORD_KEYS = set(logging.makeLogRecord({}).__dict__) | {
    "message",
    "asctime",
}
_RESERVED_PAYLOAD_KEYS = {
    "timestamp",
    "level",
    "logger",
    "message",
    "request_id",
    "workflow_id",
    "exception",
}


def _redact_text(value: str) -> str:
    value = _URL_CREDENTIALS.sub(r"\1[REDACTED]@", value)
    value = _SECRET_ASSIGNMENT.sub(r"\1\2[REDACTED]", value)
    value = _BEARER_TOKEN.sub("Bearer [REDACTED]", value)
    value = _JWT_TOKEN.sub("[REDACTED]", value)
    return _SENSITIVE_QUERY_VALUE.sub(r"\1[REDACTED]", value)


def _safe_value(value: Any, key: str | None = None) -> Any:
    if key is not None and _SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, dict):
        return {
            str(item_key): _safe_value(item, str(item_key))
            for item_key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _redact_text(str(value))


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": _redact_text(record.name),
            "message": _redact_text(record.getMessage()),
            "request_id": _request_id.get(),
            "workflow_id": _workflow_id.get(),
        }

        if record.exc_info:
            payload["exception"] = _redact_text(self.formatException(record.exc_info))

        for key, value in record.__dict__.items():
            if (
                key not in _STANDARD_RECORD_KEYS
                and key not in _RESERVED_PAYLOAD_KEYS
                and not key.startswith("_")
            ):
                payload[key] = _safe_value(value, key)

        return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


def setup_logging(
    level: int = logging.INFO,
    stream: TextIO | None = None,
) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        if getattr(handler, "_clouddesk_json_handler", False):
            handler.close()

    handler = logging.StreamHandler(stream if stream is not None else sys.stdout)
    handler.setFormatter(_JsonFormatter())
    handler._clouddesk_json_handler = True  # type: ignore[attr-defined]
    root_logger.addHandler(handler)


@contextmanager
def log_context(
    request_id: str | None = None,
    workflow_id: str | None = None,
) -> Generator[None, None, None]:
    request_token = _request_id.set(request_id)
    workflow_token = _workflow_id.set(workflow_id)
    try:
        yield
    finally:
        _workflow_id.reset(workflow_token)
        _request_id.reset(request_token)
