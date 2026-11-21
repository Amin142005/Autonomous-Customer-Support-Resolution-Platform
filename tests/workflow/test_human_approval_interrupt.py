from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, END, StateGraph

from agents.graph import human_approval
from agents.state import SupportState
from backend.app.schemas.workflow import ResolutionPlan


async def test_human_approval_interrupts_before_execution():
    graph = StateGraph(SupportState)
    graph.add_node("human_approval", human_approval)
    graph.add_edge(START, "human_approval")
    graph.add_edge("human_approval", END)
    compiled = graph.compile(checkpointer=InMemorySaver())

    interrupt_payload = None
    async for update in compiled.astream(
        {
            "ticket_id": "ticket-refund",
            "workflow_id": "workflow-refund",
            "resolution": ResolutionPlan(
                actions=[
                    {
                        "tool": "create_refund_request",
                        "arguments": {"customer_id": "customer-refund", "amount": "25.00"},
                        "approval_required": True,
                        "rationale": "Refund requires approval",
                    }
                ],
            ),
        },
        {"configurable": {"thread_id": "workflow-refund-unit"}},
        stream_mode="values",
    ):
        if isinstance(update, dict):
            interrupt_items = update.get("__interrupt__")
            if interrupt_items:
                interrupt_payload = getattr(interrupt_items[0], "value", interrupt_items[0])

    assert interrupt_payload is not None
    assert interrupt_payload["kind"] == "human_approval"
    assert interrupt_payload["actions"][0]["tool"] == "create_refund_request"
