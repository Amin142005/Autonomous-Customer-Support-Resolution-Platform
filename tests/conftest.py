import os


os.environ.update(
    {
        "DEMO_MODE": "true",
        "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "CHECKPOINT_DB_PATH": ":memory:",
        "REDIS_URL": "",
        "USE_FAKE_REDIS": "true",
        "LLM_PROVIDER": "fake",
        "LLM_API_KEY": "",
        "EMBEDDING_PROVIDER": "fake",
        "VECTOR_STORE": "memory",
        "QDRANT_URL": "",
        "QDRANT_API_KEY": "",
    }
)
