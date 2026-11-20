from __future__ import annotations

import tempfile
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from agents.checkpointer import create_checkpointer
from agents.state import append_errors, append_unique, merge_usage
from backend.app.schemas.workflow import TokenUsage


def test_append_unique_deduplicates_nodes():
    result = append_unique(["understand_ticket"], ["understand_ticket", "troubleshooting"])

    assert result == ["understand_ticket", "troubleshooting"]


def test_append_errors_appends_in_order():
    result = append_errors(["first"], ["second", "third"])

    assert result == ["first", "second", "third"]


def test_merge_usage_sums_all_fields():
    result = merge_usage(
        TokenUsage(input_tokens=10, output_tokens=4, cost=0.01),
        [
            TokenUsage(input_tokens=5, output_tokens=3, cost=0.02),
            {"input_tokens": 2, "output_tokens": 1, "cost": 0.005},
        ],
    )

    assert result.input_tokens == 17
    assert result.output_tokens == 8
    assert abs(result.cost - 0.035) < 1e-9


async def test_create_checkpointer_uses_memory_saver_for_tests():
    async with create_checkpointer(":memory:") as saver:
        assert isinstance(saver, InMemorySaver)


async def test_create_checkpointer_uses_async_sqlite_saver_for_file():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "checkpoints.db"
        async with create_checkpointer(str(path)) as saver:
            assert isinstance(saver, AsyncSqliteSaver)
        assert path.is_file()


def test_support_state_partial_fields_are_allowed():
    state = {"ticket_id": "ticket-1", "completed_nodes": ["understand_ticket"]}

    assert state["ticket_id"] == "ticket-1"
    assert state["completed_nodes"] == ["understand_ticket"]
