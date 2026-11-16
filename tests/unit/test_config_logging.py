import json
import logging
from io import StringIO
from typing import Generator

import pytest

from backend.app.core.config import Settings, get_settings
from backend.app.core.logging import log_context, setup_logging


@pytest.fixture(autouse=True)
def restore_root_logging() -> Generator[None, None, None]:
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    original_level = root_logger.level
    yield
    for handler in root_logger.handlers[:]:
        if getattr(handler, "_clouddesk_json_handler", False):
            root_logger.removeHandler(handler)
            handler.close()
    root_logger.handlers[:] = original_handlers
    root_logger.setLevel(original_level)


def test_settings_have_offline_safe_defaults():
    settings = Settings(_env_file=None)

    assert settings.llm_provider == "fake"
    assert settings.vector_store == "memory"
    assert settings.database_url == "sqlite+aiosqlite:///./data/support.db"
    assert settings.approval_required_for_refunds is True
    assert settings.max_refund_without_approval == 0
    assert settings.rate_limit_per_minute == 120


def test_settings_load_environment_values_and_cache(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("CORS_ORIGINS", '["https://console.example"]')
    monkeypatch.setenv("JWT_SECRET", "local-secret")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "supabase-secret")
    monkeypatch.setenv("MAX_REFUND_WITHOUT_APPROVAL", "25")

    settings = get_settings()

    assert settings.demo_mode is False
    assert settings.cors_origins == ["https://console.example"]
    assert settings.max_refund_without_approval == 25
    assert settings.effective_jwt_secret == "supabase-secret"
    assert get_settings() is settings

    get_settings.cache_clear()


def test_settings_dump_redacts_secrets_and_url_credentials():
    settings = Settings(
        _env_file=None,
        jwt_secret="jwt-secret",
        llm_api_key="llm-secret",
        database_url="postgresql+asyncpg://user:db-secret@db.example/support",
        redis_url="redis://user:redis-secret@cache.example/0",
    )

    dumped = settings.model_dump()

    assert dumped["jwt_secret"] == "[REDACTED]"
    assert dumped["llm_api_key"] == "[REDACTED]"
    assert "user:db-secret@" not in dumped["database_url"]
    assert "[REDACTED]@" in dumped["database_url"]
    assert "user:redis-secret@" not in dumped["redis_url"]


def test_json_logs_include_context_and_redact_sensitive_values():
    output = StringIO()
    setup_logging(stream=output)
    logger = logging.getLogger("cloudesk.test")

    with log_context(request_id="request-123", workflow_id="workflow-456"):
        logger.info(
            "Authorization: Bearer bearer-secret password=pass-secret "
            "access_token=access-secret jwt=eyJhbGciOi.test-payload.signature "
            "database=postgresql://user:url-secret@db.example/app?token=query-secret",
            extra={
                "customer_id": "customer-1",
                "api_key": "extra-secret",
                "request_id": "spoofed-request-id",
            },
        )
        try:
            raise ValueError("password=exception-secret")
        except ValueError:
            logger.exception("request failed")

    record, exception_record = map(json.loads, output.getvalue().splitlines())

    assert record["request_id"] == "request-123"
    assert record["workflow_id"] == "workflow-456"
    assert record["customer_id"] == "customer-1"
    assert record["api_key"] == "[REDACTED]"
    assert "eyJhbGciOi.test-payload.signature" not in record["message"]
    assert "bearer-secret" not in record["message"]
    assert "pass-secret" not in record["message"]
    assert "access-secret" not in record["message"]
    assert "url-secret" not in record["message"]
    assert "query-secret" not in record["message"]
    assert "exception-secret" not in exception_record["exception"]


def test_json_logs_have_null_context_outside_context_manager():
    output = StringIO()
    setup_logging(stream=output)
    logging.getLogger("cloudesk.test").info("ready")

    record = json.loads(output.getvalue())

    assert record["request_id"] is None
    assert record["workflow_id"] is None

