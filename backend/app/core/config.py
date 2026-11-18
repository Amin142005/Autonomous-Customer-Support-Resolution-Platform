from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_CREDENTIALS_IN_URL = re.compile(r"(?i)(\b[a-z][a-z0-9+.-]*://)[^/@\s]+@")
_SENSITIVE_QUERY_VALUE = re.compile(
    r"(?i)([?&](?:password|passwd|pwd|token|api[_-]?key|secret|authorization)=)[^&\s]+"
)
_SENSITIVE_KEY = re.compile(
    r"(?i)(?:^|[_-])(?:secret|password|passwd|token|authorization|credential|api[_-]?key)(?:$|[_-])"
)


def _redact_text(value: str) -> str:
    value = _CREDENTIALS_IN_URL.sub(r"\1[REDACTED]@", value)
    return _SENSITIVE_QUERY_VALUE.sub(r"\1[REDACTED]", value)


def _redact_dump(value: Any, key: str | None = None) -> Any:
    if key is not None and _SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, SecretStr):
        return "[REDACTED]"
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, dict):
        return {
            item_key: _redact_dump(item, str(item_key))
            for item_key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact_dump(item) for item in value]
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    demo_mode: bool = True
    environment: str = "development"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    jwt_secret: SecretStr = SecretStr("")
    supabase_jwt_secret: SecretStr = SecretStr("")
    database_url: str = "sqlite+aiosqlite:///./data/support.db"
    checkpoint_db_path: str = "./data/checkpoints.db"
    redis_url: str = ""
    use_fake_redis: bool = False

    llm_provider: str = "fake"
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = "fake"

    embedding_provider: str = "fake"
    embedding_model: str = "fake-hash"
    embedding_dimensions: int = Field(default=384, gt=0)

    vector_store: str = "memory"
    qdrant_url: str = ""
    qdrant_api_key: SecretStr = SecretStr("")
    qdrant_collection: str = "clouddesk_knowledge"

    approval_required_for_refunds: bool = True
    max_refund_without_approval: int = Field(default=0, ge=0)
    tool_timeout_seconds: float = Field(default=30.0, gt=0)
    rate_limit_per_minute: int = Field(default=120, gt=0)
    sample_data_dir: str = "sample_data"

    langchain_tracing_v2: bool = False
    langchain_api_key: SecretStr = SecretStr("")
    langchain_project: str = "clouddesk-support"

    @property
    def effective_jwt_secret(self) -> str:
        configured = (
            self.supabase_jwt_secret.get_secret_value()
            or self.jwt_secret.get_secret_value()
        )
        if configured:
            return configured
        if self.demo_mode:
            return "clouddesk-demo-only-local-secret"
        return ""

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        return _redact_dump(super().model_dump(**kwargs))


@lru_cache
def get_settings() -> Settings:
    return Settings()
