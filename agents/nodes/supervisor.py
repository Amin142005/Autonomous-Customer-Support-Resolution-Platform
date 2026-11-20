from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agents.specialists.supervisor import SupervisorAgent
from agents.state import SupportState


def _ticket_text(state: Mapping[str, Any]) -> dict[str, Any]:
    ticket = state.get("ticket")
    if isinstance(ticket, Mapping):
        return dict(ticket)
    return {}


async def understand_ticket(state: SupportState) -> dict[str, Any]:
    """Classify the ticket and detect prompt-injection content."""
    ticket = _ticket_text(state)

    try:
        agent = SupervisorAgent()
        classification = await agent.understand(ticket)
        injection_detected = agent.last_injection_detected
        usage = agent.last_usage
    except Exception as exc:  # noqa: BLE001
        return {
            "errors": [f"understand_ticket: {type(exc).__name__}"],
            "completed_nodes": ["understand_ticket"],
            "current_node": "understand_ticket",
        }

    return {
        "classification": classification,
        "injection_detected": injection_detected,
        "completed_nodes": ["understand_ticket"],
        "current_node": "understand_ticket",
        "token_usage": usage,
    }


async def classify_severity(state: SupportState) -> dict[str, Any]:
    """Assess severity and apply the deterministic rule set."""
    ticket = _ticket_text(state)
    classification = state.get("classification")

    try:
        agent = SupervisorAgent()
        severity = await agent.assess_severity(
            ticket,
            category=(
                classification.category
                if classification is not None
                else None
            ),
        )
        injection_detected = bool(
            state.get("injection_detected", False)
            or agent.last_injection_detected
        )
        usage = agent.last_usage
    except Exception as exc:  # noqa: BLE001
        return {
            "errors": [f"classify_severity: {type(exc).__name__}"],
            "completed_nodes": ["classify_severity"],
            "current_node": "classify_severity",
        }

    return {
        "severity": severity,
        "injection_detected": injection_detected,
        "completed_nodes": ["classify_severity"],
        "current_node": "classify_severity",
        "token_usage": usage,
    }


async def ticket_summary(state: SupportState) -> dict[str, Any]:
    """Create a concise internal summary from classification and severity."""
    ticket = _ticket_text(state)

    try:
        summary = await SupervisorAgent().ticket_summary(
            ticket,
            state.get("classification"),
            state.get("severity"),
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "errors": [f"ticket_summary: {type(exc).__name__}"],
            "completed_nodes": ["ticket_summary"],
            "current_node": "ticket_summary",
        }

    return {
        "ticket_summary": summary,
        "completed_nodes": ["ticket_summary"],
        "current_node": "ticket_summary",
    }


__all__ = ["understand_ticket", "classify_severity", "ticket_summary"]
