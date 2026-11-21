from __future__ import annotations

from agents.nodes.investigate import (
    customer_context,
    knowledge_retrieval,
    troubleshooting,
)
from backend.app.schemas.common import Category
from backend.app.tools.registry import ToolRegistry


class FakeAsyncTool:
    def __init__(self, name: str, output: object) -> None:
        self.name = name
        self.output = output

    async def ainvoke(self, input: dict[str, object]) -> object:
        del input
        return self.output


class FakeMemory:
    async def recall_customer(self, customer_id: str, *, limit: int = 10):
        del customer_id, limit
        return []


def investigation_registry() -> ToolRegistry:
    registry = ToolRegistry(timeout_seconds=1)
    registry.register(FakeAsyncTool("get_customer", {"id": "customer-1", "name": "Avery"}))
    registry.register(FakeAsyncTool("get_subscription", [{"plan": "enterprise", "seats": 25}]))
    registry.register(FakeAsyncTool("get_ticket_history", [{"number": "CD-0999"}]))
    registry.register(FakeAsyncTool("search_docs", [{
        "id": "sso",
        "title": "SSO login troubleshooting",
        "source": "kb://sso#login",
        "snippet": "Verify identity provider settings.",
        "score": 0.9,
        "url": "/knowledge/sso",
        "article_id": "sso",
    }]))
    registry.register(FakeAsyncTool("check_service_status", {
        "service_name": "identity",
        "state": "degraded",
        "summary": "Identity failures are under investigation.",
        "incident_ids": ["incident-1"],
    }))
    return registry


async def test_investigation_nodes_return_partial_state_and_outputs():
    registry = investigation_registry()
    state = {
        "ticket_id": "ticket-1",
        "customer_id": "customer-1",
        "ticket": {
            "id": "ticket-1",
            "customer_id": "customer-1",
            "subject": "SSO login fails for the whole team",
            "body": "Every user cannot sign in.",
        },
        "classification": type("Classification", (), {"category": Category.LOGIN_ISSUE, "summary": "SSO login failures affect the team"})(),
        "registry": registry,
        "memory_service": FakeMemory(),
    }

    customer_result = await customer_context(state)
    assert customer_result["customer_context"].customer["name"] == "Avery"
    assert customer_result["completed_nodes"] == ["customer_context"]

    knowledge_result = await knowledge_retrieval({**state, **customer_result})
    assert knowledge_result["evidence"]
    assert knowledge_result["completed_nodes"] == ["knowledge_retrieval"]

    diagnosis_result = await troubleshooting({**state, **customer_result, **knowledge_result})
    assert diagnosis_result["diagnosis"].steps
    assert diagnosis_result["diagnosis"].checks
    assert diagnosis_result["completed_nodes"] == ["troubleshooting"]


async def test_customer_context_reports_missing_customer_id():
    result = await customer_context({"ticket": {"subject": "Login problem"}})

    assert result["customer_context"] is None
    assert result["errors"] == ["customer_context: missing customer_id"]
    assert result["completed_nodes"] == ["customer_context"]


async def test_knowledge_retrieval_is_resilient_to_unknown_tools():
    result = await knowledge_retrieval({
        "ticket": {"subject": "Storage quota exceeded", "body": "Uploads fail."},
        "registry": ToolRegistry(timeout_seconds=1),
    })

    assert result["evidence"] == []
    assert isinstance(result["previous_cases"], list)
    assert result["completed_nodes"] == ["knowledge_retrieval"]
