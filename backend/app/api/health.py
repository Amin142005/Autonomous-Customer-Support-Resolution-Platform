from fastapi import APIRouter
from fastapi.responses import JSONResponse
from starlette.responses import Response

from backend.app.core.config import Settings, get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


def _readiness_checks(settings: Settings) -> dict[str, bool]:
    return {
        "database": bool(settings.database_url),
        "redis": bool(
            settings.redis_url or settings.use_fake_redis or settings.demo_mode
        ),
        "vector_store": settings.vector_store == "memory"
        or (settings.vector_store == "qdrant" and bool(settings.qdrant_url)),
        "llm": settings.llm_provider == "fake"
        or bool(settings.llm_api_key.get_secret_value()),
    }


@router.get("/health/ready", response_model=None)
def ready() -> Response | dict[str, bool | str]:
    checks = _readiness_checks(get_settings())
    if not all(checks.values()):
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "checks": checks},
        )
    return {"status": "ready"}
