from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from agents.nodes.investigate import (
    customer_context,
    knowledge_retrieval,
    troubleshooting,
)
from agents.nodes.resolution import resolution_planning, risk_check
from agents.nodes.supervisor import (
    classify_severity,
    ticket_summary,
    understand_ticket,
)
from agents.specialists.escalation import EscalationAgent
from agents.state import SupportState

GRAPH_NODES: tuple[str, ...] = (
    "understand_ticket",
    "classify_severity",
    "customer_context",
    "knowledge_retrieval",
    "troubleshooting",
    "resolution_planning",
    "risk_check",
    "escalation",
    "human_approval",
    "execute_resolution",
    "ticket_summary",
    "memory_update",
)

GRAPH_EDGES: tuple[tuple[str, str], ...] = (
    ("understand_ticket", "classify_severity"),
    ("classify_severity", "customer_context"),
    ("customer_context", "knowledge_retrieval"),
    ("knowledge_retrieval", "troubleshooting"),
    ("troubleshooting", "resolution_planning"),
    ("resolution_planning", "risk_check"),
    ("escalation", "ticket_summary"),
    ("human_approval", "execute_resolution"),
    ("execute_resolution", "ticket_summary"),
    ("ticket_summary", "memory_update"),
    ("memory_update", "END"),
)


async def escalation(state: SupportState) -> dict[str, object]:
    """Deterministically route policy cases or use cautious specialist judgement."""
    ticket = state.get("ticket")
    if not isinstance(ticket, dict):
        ticket = {}
    classification = state.get("classification")
    severity = state.get("severity")

    agent = EscalationAgent(llm=state.get("llm"))
    decision = await agent.run(
        ticket,
        category=getattr(classification, "category", None),
        severity=getattr(severity, "severity", None),
        evidence=state.get("evidence"),
        plan_name=state.get("ticket_summary") if isinstance(state.get("ticket_summary"), str) else None,
    )
    return {
        "escalation": decision,
        "escalation_required": decision.escalation_required,
        "completed_nodes": ["escalation"],
        "current_node": "escalation",
        "token_usage": agent.last_usage,
    }


async def human_approval(state: SupportState) -> dict[str, object]:
    """Pause consequential workflows until a human decision is recorded."""
    resolution = state.get("resolution")
    actions = (
        [
            {
                "tool": action.tool,
                "arguments": action.arguments,
                "approval_required": action.approval_required,
                "rationale": action.rationale,
            }
            for action in getattr(resolution, "actions", [])
            if bool(getattr(action, "approval_required", False))
        ]
        if resolution is not None
        else []
    )

    decision = interrupt({
        "kind": "human_approval",
        "ticket_id": state.get("ticket_id") or "",
        "workflow_id": state.get("workflow_id") or "",
        "actions": actions,
    })

    resumed = (
        decision
        if isinstance(decision, dict)
        else {"decision": str(decision)}
    )
    approved = str(resumed.get("decision", "")).casefold() in {"approve", "approved", "true", "yes"}

    return {
        "approval_status": "approved" if approved else "rejected",
        "paused": False,
        "completed_nodes": ["human_approval"],
        "current_node": "human_approval",
    }


async def execute_resolution(state: SupportState) -> dict[str, object]:
    """Execute planned actions through the shared ToolRegistry path."""
    from collections.abc import Mapping

    registry = state.get("tool_registry") or state.get("registry")
    if registry is None:
        from backend.app.tools.registry import ToolRegistry

        registry = ToolRegistry()

    resolution = state.get("resolution")
    if isinstance(resolution, Mapping):
        proposals = resolution.get("actions", [])
    else:
        proposals = getattr(resolution, "actions", []) if resolution is not None else []

    from backend.app.services.resolution_execution_service import ResolutionExecutionService

    executor = ResolutionExecutionService(session=None, registry=registry)
    execution_results = await executor.execute(
        ticket_id=str(state.get("ticket_id") or ""),
        workflow_id=str(state.get("workflow_id") or ""),
        proposals=list(proposals),
        approval_status=state.get("approval_status"),
    )

    return {
        "resolution_execution": execution_results,
        "completed_nodes": ["execute_resolution"],
        "current_node": "execute_resolution",
    }


async def memory_update(state: SupportState) -> dict[str, object]:
    """Placeholder for P11/P11 memory integration; P10-5 preserves graph shape."""
    del state
    return {
        "completed_nodes": ["memory_update"],
        "current_node": "memory_update",
    }


def route_risk(state: SupportState) -> Literal["escalation", "human_approval", "execute_resolution"]:
    if bool(state.get("escalation_required", False)):
        return "escalation"
    if bool(state.get("approval_required", False)):
        return "human_approval"
    if state.get("risk_level") == "high":
        return "escalation"
    return "execute_resolution"


def build_support_graph(checkpointer=None):
    graph = StateGraph(SupportState)

    graph.add_node("understand_ticket", understand_ticket)
    graph.add_node("classify_severity", classify_severity)
    graph.add_node("customer_context", customer_context)
    graph.add_node("knowledge_retrieval", knowledge_retrieval)
    graph.add_node("troubleshooting", troubleshooting)
    graph.add_node("resolution_planning", resolution_planning)
    graph.add_node("risk_check", risk_check)
    graph.add_node("escalation", escalation)
    graph.add_node("human_approval", human_approval)
    graph.add_node("execute_resolution", execute_resolution)
    graph.add_node("ticket_summary", ticket_summary)
    graph.add_node("memory_update", memory_update)

    graph.add_edge(START, "understand_ticket")
    graph.add_edge("understand_ticket", "classify_severity")
    graph.add_edge("classify_severity", "customer_context")
    graph.add_edge("customer_context", "knowledge_retrieval")
    graph.add_edge("knowledge_retrieval", "troubleshooting")
    graph.add_edge("troubleshooting", "resolution_planning")
    graph.add_edge("resolution_planning", "risk_check")
    graph.add_conditional_edges(
        "risk_check",
        route_risk,
        {
            "escalation": "escalation",
            "human_approval": "human_approval",
            "execute_resolution": "execute_resolution",
        },
    )
    graph.add_edge("escalation", "ticket_summary")
    graph.add_edge("human_approval", "execute_resolution")
    graph.add_edge("execute_resolution", "ticket_summary")
    graph.add_edge("ticket_summary", "memory_update")
    graph.add_edge("memory_update", END)

    return graph.compile(checkpointer=checkpointer)


__all__ = [
    "GRAPH_NODES",
    "GRAPH_EDGES",
    "build_support_graph",
    "route_risk",
]
