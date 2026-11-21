from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Annotated, Any, TypedDict

from backend.app.schemas.workflow import (
    Classification,
    CustomerContext,
    Diagnosis,
    EscalationDecision,
    Evidence,
    PreviousCase,
    ResolutionPlan,
    SeverityAssessment,
    TokenUsage,
)


def append_unique(left: list[str] | None, right: list[str] | Sequence[str] | str | None) -> list[str]:
    """Append values to a workflow list without introducing duplicates."""
    combined = list(left or [])
    if right is None:
        return combined
    if isinstance(right, str):
        values: Sequence[str] = (right,)
    else:
        values = right
    for value in values:
        if value not in combined:
            combined.append(str(value))
    return combined


def append_errors(left: list[str] | None, right: list[str] | Sequence[str] | str | None) -> list[str]:
    """Append workflow errors while preserving the order they occurred."""
    return append_unique(left, right)


def merge_usage(
    left: TokenUsage | Mapping[str, Any] | None,
    right: TokenUsage | Mapping[str, Any] | Sequence[TokenUsage | Mapping[str, Any]] | None,
) -> TokenUsage:
    """Sum token usage across workflow nodes."""

    def to_usage(value: Any) -> TokenUsage:
        if isinstance(value, TokenUsage):
            return value
        if hasattr(value, "input_tokens") or hasattr(value, "output_tokens") or hasattr(value, "cost"):
            return TokenUsage(
                input_tokens=int(getattr(value, "input_tokens", 0) or 0),
                output_tokens=int(getattr(value, "output_tokens", 0) or 0),
                cost=float(getattr(value, "cost", 0.0) or 0.0),
            )
        if isinstance(value, Mapping):
            try:
                return TokenUsage.model_validate(value)
            except (TypeError, ValueError):
                return TokenUsage()
        return TokenUsage()

    totals = to_usage(left)
    input_tokens = totals.input_tokens
    output_tokens = totals.output_tokens
    cost = totals.cost

    if right is None:
        values: Sequence[Any] = ()
    elif isinstance(right, (TokenUsage, Mapping)) or hasattr(right, "input_tokens"):
        values = (right,)
    else:
        values = right

    for value in values:
        usage = to_usage(value)
        input_tokens += usage.input_tokens
        output_tokens += usage.output_tokens
        cost += usage.cost

    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost=cost,
    )


class SupportState(TypedDict, total=False):
    """LangGraph state for one support-ticket workflow run."""

    ticket_id: str
    ticket_number: str
    customer_id: str
    thread_id: str
    workflow_id: str
    ticket: dict[str, Any]
    ticket_summary: str

    classification: Classification | None
    severity: SeverityAssessment | None
    injection_detected: bool
    customer_context: CustomerContext | None
    evidence: list[Evidence]
    previous_cases: list[PreviousCase]
    diagnosis: Diagnosis | None
    resolution: ResolutionPlan | None
    resolution_execution: list[dict[str, Any]]
    escalation: EscalationDecision | None

    risk_level: str
    escalation_required: bool
    approval_required: bool
    approval_status: str
    approval_id: str | None
    paused: bool

    current_node: str
    completed_nodes: Annotated[list[str], append_unique]
    errors: Annotated[list[str], append_errors]
    token_usage: Annotated[TokenUsage, merge_usage]

    # Runtime dependencies injected by the workflow service when building a run.
    registry: Any
    tool_registry: Any
    memory_service: Any
    memory: Any
    llm: Any


__all__ = [
    "SupportState",
    "append_errors",
    "append_unique",
    "merge_usage",
]
