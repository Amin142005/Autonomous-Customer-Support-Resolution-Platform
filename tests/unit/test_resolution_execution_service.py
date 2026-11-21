from __future__ import annotations

from backend.app.services.resolution_execution_service import ResolutionExecutionService


class FakeRegistry:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object], bool]] = []

    async def execute(
        self,
        name: str,
        args: dict[str, object],
        *,
        approved: bool = False,
    ):
        self.calls.append((name, args, approved))
        from backend.app.tools.result import ToolResult

        return ToolResult(ok=True, tool_name=name, output={"status": "simulated"})


async def test_execute_resolution_runs_ordinary_action_through_registry():
    registry = FakeRegistry()
    executor = ResolutionExecutionService(session=None, registry=registry)

    results = await executor.execute(
        ticket_id="ticket-1",
        workflow_id="workflow-1",
        proposals=[{
            "tool": "update_ticket",
            "arguments": {"ticket_id": "ticket-1", "status": "in_progress"},
            "approval_required": False,
        }],
        approval_status=None,
    )

    assert results[0]["status"] == "completed"
    assert registry.calls == [
        ("update_ticket", {"ticket_id": "ticket-1", "status": "in_progress"}, False)
    ]


async def test_execute_resolution_blocks_consequential_action_without_approval():
    registry = FakeRegistry()
    executor = ResolutionExecutionService(session=None, registry=registry)

    results = await executor.execute(
        ticket_id="ticket-1",
        workflow_id="workflow-1",
        proposals=[{
            "tool": "create_refund_request",
            "arguments": {"customer_id": "customer-1", "amount": "25.00"},
            "approval_required": True,
        }],
        approval_status="pending",
    )

    assert results[0]["status"] == "approval_required"
    assert registry.calls == []


async def test_execute_resolution_runs_approved_action_through_registry():
    registry = FakeRegistry()
    executor = ResolutionExecutionService(session=None, registry=registry)

    results = await executor.execute(
        ticket_id="ticket-1",
        workflow_id="workflow-1",
        proposals=[{
            "tool": "create_refund_request",
            "arguments": {"customer_id": "customer-1", "amount": "25.00"},
            "approval_required": True,
        }],
        approval_status="approved",
        approval_decided_by="agent-1",
    )

    assert results[0]["status"] == "completed"
    assert registry.calls == [
        ("create_refund_request", {"customer_id": "customer-1", "amount": "25.00"}, True)
    ]
