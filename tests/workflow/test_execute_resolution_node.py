from __future__ import annotations

from agents.graph import execute_resolution
from backend.app.schemas.workflow import ResolutionPlan


class FakeRegistry:
    async def execute(self, name: str, args: dict[str, object], *, approved: bool = False):
        del args
        from backend.app.tools.result import ToolResult

        return ToolResult(ok=True, tool_name=name, output={"approved": approved})


async def test_execute_resolution_node_runs_update_through_registry():
    result = await execute_resolution({
        "ticket_id": "ticket-1",
        "workflow_id": "workflow-1",
        "tool_registry": FakeRegistry(),
        "resolution": ResolutionPlan(actions=[{
            "tool": "update_ticket",
            "arguments": {"ticket_id": "ticket-1", "status": "in_progress"},
            "approval_required": False,
        }]),
    })

    assert result["completed_nodes"] == ["execute_resolution"]
    assert result["resolution_execution"][0]["status"] == "completed"


async def test_execute_resolution_node_blocks_refund_without_approval():
    registry = FakeRegistry()
    registry.execute = None

    result = await execute_resolution({
        "ticket_id": "ticket-1",
        "workflow_id": "workflow-1",
        "approval_status": "pending",
        "tool_registry": registry,
        "resolution": ResolutionPlan(actions=[{
            "tool": "create_refund_request",
            "arguments": {"customer_id": "customer-1", "amount": "25.00"},
            "approval_required": True,
        }]),
    })

    assert result["resolution_execution"][0]["status"] == "approval_required"
