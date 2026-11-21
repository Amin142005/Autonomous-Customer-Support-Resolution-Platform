from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agents.specialists.customer import CustomerAgent
from agents.specialists.knowledge import KnowledgeAgent
from agents.specialists.troubleshooting import TroubleshootingAgent
from agents.state import SupportState
from backend.app.tools.registry import ToolRegistry


def _ticket_text(state: Mapping[str, Any]) -> dict[str, Any]:
    ticket = state.get("ticket")
    if isinstance(ticket, Mapping):
        return dict(ticket)
    return {}


def _registry(state: Mapping[str, Any]) -> ToolRegistry:
    for key in ("registry", "tool_registry"):
        value = state.get(key)
        if isinstance(value, ToolRegistry) or hasattr(value, "execute"):
            return value
    return ToolRegistry()


def _memory_service(state: Mapping[str, Any]) -> Any | None:
    for key in ("memory_service", "memory"):
        value = state.get(key)
        if value is not None:
            return value
    return None


def _query(state: Mapping[str, Any]) -> str:
    ticket_summary = state.get("ticket_summary")
    if isinstance(ticket_summary, str) and ticket_summary.strip():
        return ticket_summary.strip()

    ticket = _ticket_text(state)
    subject = str(ticket.get("subject", "")).strip()
    body = str(ticket.get("body", "")).strip()
    query = " ".join(part for part in (subject, body) if part)
    if query:
        return query

    classification = state.get("classification")
    if classification is not None:
        summary = getattr(classification, "summary", None)
        if isinstance(summary, str) and summary.strip():
            return summary.strip()
    return "Support ticket investigation"


async def customer_context(state: SupportState) -> dict[str, Any]:
    """Load customer, subscription, workspace, history, and memory context."""
    ticket = _ticket_text(state)
    customer_id = str(
        state.get("customer_id")
        or ticket.get("customer_id")
        or ""
    ).strip()

    if not customer_id:
        return {
            "customer_context": None,
            "errors": ["customer_context: missing customer_id"],
            "completed_nodes": ["customer_context"],
            "current_node": "customer_context",
        }

    try:
        context = await CustomerAgent(
            _registry(state),
            memory_service=_memory_service(state),
        ).run(
            customer_id,
            ticket_id=str(state.get("ticket_id") or ticket.get("id") or "") or None,
            exclude_ticket_id=str(state.get("ticket_id") or ticket.get("id") or "") or None,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "errors": [f"customer_context: {type(exc).__name__}"],
            "completed_nodes": ["customer_context"],
            "current_node": "customer_context",
        }

    return {
        "customer_context": context,
        "completed_nodes": ["customer_context"],
        "current_node": "customer_context",
    }


async def knowledge_retrieval(state: SupportState) -> dict[str, Any]:
    """Retrieve cited knowledge evidence and similar resolved cases."""
    classification = state.get("classification")
    category = getattr(classification, "category", None)

    try:
        evidence, previous_cases = await KnowledgeAgent(_registry(state)).run(
            _query(state),
            category=category,
            mode="hybrid",
            top_k=5,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "errors": [f"knowledge_retrieval: {type(exc).__name__}"],
            "completed_nodes": ["knowledge_retrieval"],
            "current_node": "knowledge_retrieval",
        }

    return {
        "evidence": evidence,
        "previous_cases": previous_cases,
        "completed_nodes": ["knowledge_retrieval"],
        "current_node": "knowledge_retrieval",
    }


async def troubleshooting(state: SupportState) -> dict[str, Any]:
    """Create probable causes and numbered troubleshooting steps."""
    classification = state.get("classification")
    category = getattr(classification, "category", None)

    llm = state.get("llm")
    agent = TroubleshootingAgent(_registry(state), llm=llm)

    try:
        diagnosis = await agent.run(
            _ticket_text(state),
            category=category,
            evidence=state.get("evidence"),
            customer_context=state.get("customer_context"),
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "errors": [f"troubleshooting: {type(exc).__name__}"],
            "completed_nodes": ["troubleshooting"],
            "current_node": "troubleshooting",
        }

    return {
        "diagnosis": diagnosis,
        "completed_nodes": ["troubleshooting"],
        "current_node": "troubleshooting",
        "token_usage": agent.last_usage,
    }


__all__ = ["customer_context", "knowledge_retrieval", "troubleshooting"]
