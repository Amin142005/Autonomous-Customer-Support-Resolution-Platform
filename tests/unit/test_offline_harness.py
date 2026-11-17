import os

from backend.app.core.config import get_settings


def test_pytest_environment_uses_offline_dependencies():
    settings = get_settings()

    assert settings.demo_mode is True
    assert settings.database_url == "sqlite+aiosqlite:///:memory:"
    assert settings.llm_provider == "fake"
    assert settings.vector_store == "memory"
    assert os.environ["CHECKPOINT_DB_PATH"] == ":memory:"
    assert os.environ["USE_FAKE_REDIS"] == "true"
