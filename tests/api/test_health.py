import asyncio
import json
import logging
from io import StringIO
from collections.abc import Generator, Mapping
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from starlette.types import ASGIApp

from backend.app.api import health as health_api
from backend.app.core.config import Settings
from backend.app.core.logging import setup_logging
from backend.app.main import app
from backend.app.middleware.request_id import RequestIdMiddleware


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


def request(
    application: ASGIApp,
    method: str,
    path: str,
    headers: Mapping[str, str] | None = None,
) -> httpx.Response:
    async def perform_request() -> httpx.Response:
        transport = httpx.ASGITransport(
            app=application,
            raise_app_exceptions=False,
        )
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, headers=headers)

    return asyncio.run(perform_request())


def assert_uuid_request_id(response: httpx.Response) -> None:
    request_id = response.headers["X-Request-ID"]
    assert str(UUID(request_id)) == request_id


def test_health_and_liveness_do_not_check_dependencies(monkeypatch):
    def unexpected_settings_access():
        raise AssertionError("liveness endpoints must not access dependency settings")

    monkeypatch.setattr(health_api, "get_settings", unexpected_settings_access)

    assert request(app, "GET", "/health").json() == {"status": "ok"}
    assert request(app, "GET", "/health/live").json() == {"status": "ok"}


def test_readiness_uses_configuration_checks():
    response = request(app, "GET", "/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_reports_missing_configuration(monkeypatch):
    settings = Settings(
        _env_file=None,
        demo_mode=False,
        database_url="",
        redis_url="",
        use_fake_redis=False,
        vector_store="qdrant",
        qdrant_url="",
        llm_provider="openai",
        llm_api_key="",
    )
    monkeypatch.setattr(health_api, "get_settings", lambda: settings)

    response = request(app, "GET", "/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "checks": {
            "database": False,
            "redis": False,
            "vector_store": False,
            "llm": False,
        },
    }


def test_request_id_is_echoed_and_generated():
    echoed = request(app, "GET", "/health", {"X-Request-ID": "request-123"})
    assert echoed.headers["X-Request-ID"] == "request-123"

    generated = request(app, "GET", "/missing")
    assert generated.status_code == 404
    assert_uuid_request_id(generated)


def test_invalid_request_id_is_replaced():
    response = request(app, "GET", "/health", {"X-Request-ID": "x" * 129})

    request_id = response.headers["X-Request-ID"]
    assert request_id != "x" * 129
    assert_uuid_request_id(response)


def test_request_id_is_present_on_unhandled_errors():
    test_app = FastAPI()

    @test_app.get("/failure")
    def fail() -> None:
        raise RuntimeError("expected test failure")

    response = request(RequestIdMiddleware(test_app), "GET", "/failure")

    assert response.status_code == 500
    assert_uuid_request_id(response)


def test_request_id_is_bound_to_json_logs():
    output = StringIO()
    setup_logging(stream=output)
    test_app = FastAPI()

    @test_app.get("/logged")
    def logged() -> dict[str, str]:
        logging.getLogger("health.test").info("health check")
        return {"status": "ok"}

    response = request(
        RequestIdMiddleware(test_app),
        "GET",
        "/logged",
        {"X-Request-ID": "trace-456"},
    )

    record = json.loads(output.getvalue().splitlines()[0])
    assert response.headers["X-Request-ID"] == "trace-456"
    assert record["request_id"] == "trace-456"
    assert record["workflow_id"] is None


def test_cors_exposes_request_id_header():
    preflight = request(
        app,
        "OPTIONS",
        "/health",
        {
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Request-ID",
        },
    )
    response = request(
        app,
        "GET",
        "/health",
        {"Origin": "http://localhost:3000"},
    )

    assert preflight.status_code == 200
    assert_uuid_request_id(preflight)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "x-request-id" in response.headers["access-control-expose-headers"].lower()
    assert_uuid_request_id(response)
