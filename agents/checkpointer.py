from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from backend.app.core.config import get_settings


@asynccontextmanager
async def create_checkpointer(
    path: str | None = None,
) -> AsyncIterator[BaseCheckpointSaver]:
    """Create an in-memory or SQLite LangGraph checkpointer.

    In-memory checkpoints are used for tests. A file-backed SQLite checkpointer
    preserves workflow state across process restarts and approval resumes.
    """
    selected_path = path if path is not None else get_settings().checkpoint_db_path

    if selected_path.strip() == ":memory:":
        yield InMemorySaver()
        return

    parent = selected_path.strip()
    if not parent:
        raise ValueError("CHECKPOINT_DB_PATH must not be empty")

    async with AsyncSqliteSaver.from_conn_string(parent) as saver:
        yield saver


__all__ = ["create_checkpointer"]
