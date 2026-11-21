from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agents.rules import matching_escalation_rules
from agents.specialists.resolution import ResolutionAgent
from agents.state import SupportState
from backend.app.core.guardrails import validate_customer_output
from backend.app.schemas.common import Category, Severity


def _ticket_text(state: Mapping[str, Any]) -> dict[str, Any]:
    ticket = state.get("ticket")
    if isinstance(ticket, Mapping):
        return dict(ticket)
    return {}


def _ticket_rule_text(state: Mapping[str, Any]) -> str:
    ticket = _ticket_text(state)
    subject = str(ticket.get("subject", "")).strip()
    body = str(ticket.get("body", "")).strip()
    summary = state.get("ticket_summary")
    parts = [
        str(summary).strip() if isinstance(summary, str) else "",
        subject,
        body,
    ]
    return " ".join(part for part in parts if part)


def _category(state: Mapping[str, Any]) -> Category | None:
    classification = state.get("classification")
    category = getattr(classification, "category", None)
    if isinstance(category, Category):
        return category
    if isinstance(category, str):
        try:
            return Category(category.lower())
        except ValueError:
            return None
    return None


def _severity(state: Mapping[str, Any]) -> Severity | None:
    assessment = state.get("severity")
    value = getattr(assessment, "severity", assessment)
    if isinstance(value, Severity):
        return value
    if isinstance(value, str):
        try:
            return Severity(value.lower())
        except ValueError:
            return None
    return None


async def resolution_planning(state: SupportState) -> dict[str, Any]:
    """Create a grounded resolution plan and deterministic action proposals."""
    ticket = _ticket_text(state)
    llm = state.get("llm")

    try:
        agent = ResolutionAgent(llm=llm)
        plan = await agent.run(
            ticket,
            state.get("diagnosis"),
            category=_category(state),
            evidence=state.get("evidence"),
            customer_context=state.get("customer_context"),
            severity=_severity(state),
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "errors": [f"resolution_planning: {type(exc).__name__}"],
            "completed_nodes": ["resolution_planning"],
            "current_node": "resolution_planning",
            "approval_required": False,
        }

    approval_required = any(
        bool(action.approval_required)
        for action in plan.actions
    )

    return {
        "resolution": plan,
        "approval_required": approval_required,
        "completed_nodes": ["resolution_planning"],
        "current_node": "resolution_planning",
        "token_usage": agent.last_usage,
    }


async def risk_check(state: SupportState) -> dict[str, Any]:
    """Apply deterministic high-risk routing conditions before escalation/approval."""
    ticket_text = _ticket_rule_text(state)
    plan_name = (
        state.get("ticket_summary")
        if isinstance(state.get("ticket_summary"), str)
        else None
    )

    policy_matches = matching_escalation_rules(ticket_text, plan_name)
    severity = _severity(state)
    resolution = state.get("resolution")

    approval_required = bool(state.get("approval_required", False))
    if resolution is not None:
        approval_required = approval_required or any(
            bool(action.approval_required)
            for action in resolution.actions
        )

    injection_detected = bool(state.get("injection_detected", False))

    output_validation_failed = False
    if resolution is not None:
        reply = resolution.customer_reply or resolution.reply
        customer_context = state.get("customer_context")
        allowed_id = None
        allowed_name = None
        if isinstance(customer_context, Mapping):
            customer = customer_context.get("customer")
            if isinstance(customer, Mapping):
                allowed_id = str(customer.get("id") or "") or None
                allowed_name = str(customer.get("name") or "") or None
        elif customer_context is not None:
            customer = getattr(customer_context, "customer", None)
            if isinstance(customer, Mapping):
                allowed_id = str(customer.get("id") or "") or None
                allowed_name = str(customer.get("name") or "") or None

        is_valid, _ = validate_customer_output(
            reply,
            allowed_customer_id=allowed_id,
            allowed_customer_name=allowed_name,
        )
        output_validation_failed = not is_valid

    if (
        approval_required
        or policy_matches
        or severity == Severity.CRITICAL
        or injection_detected
        or output_validation_failed
    ):
        risk_level = "high"
    elif severity == Severity.HIGH:
        risk_level = "medium"
    else:
        risk_level = "low"

    return {
        "risk_level": risk_level,
        "escalation_required": bool(policy_matches),
        "approval_required": approval_required,
        "completed_nodes": ["risk_check"],
        "current_node": "risk_check",
    }


__all__ = ["resolution_planning", "risk_check"]
