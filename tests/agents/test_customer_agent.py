from dataclasses import dataclass

from agents.specialists.customer import CustomerAgent
from backend.app.tools.registry import ToolRegistry
from backend.app.tools.result import ToolResult


class FakeAsyncTool:
    def __init__(self, name: str, output: object) -> None:
        self.name = name
        self.output = output

    async def ainvoke(self, input: dict[str, object]) -> object:
        del input
        return self.output


@dataclass
class FakeMemoryNote:
    content: str


class FakeMemoryService:
    async def recall_customer(
        self,
        customer_id: str,
        *,
        limit: int = 10,
    ) -> list[FakeMemoryNote]:
        del customer_id, limit
        return [
            FakeMemoryNote("Use the MFA recovery playbook."),
            FakeMemoryNote("Password=secret123"),
        ]


async def test_customer_agent_loads_context_through_registered_tools():
    registry = ToolRegistry(timeout_seconds=1)
    registry.register(
        FakeAsyncTool(
            "get_customer",
            {
                "id": "customer-1",
                "name": "Avery Morgan",
                "email": "avery@example.test",
            },
        )
    )
    registry.register(
        FakeAsyncTool(
            "get_subscription",
            [{"id": "sub-1", "plan": "enterprise", "seats": 25}],
        )
    )
    registry.register(
        FakeAsyncTool(
            "get_ticket_history",
            [{"number": "CD-1002", "subject": "Refund request"}],
        )
    )
    agent = CustomerAgent(
        registry,
        memory_service=FakeMemoryService(),
    )

    context = await agent.run(
        "customer-1",
        ticket_id="ticket-current",
    )

    assert context.customer["name"] == "Avery Morgan"
    assert context.subscription["plan"] == "enterprise"
    assert context.subscriptions[0]["seats"] == 25
    assert context.previous_tickets[0]["number"] == "CD-1002"
    assert "MFA recovery" in context.memory_notes[0]
    assert "secret123" not in repr(context.memory_notes)


async def test_customer_agent_returns_partial_context_when_tool_fails():
    registry = ToolRegistry(timeout_seconds=1)

    async def missing_tool(
        name: str,
        args: dict[str, object],
        approved: bool = False,
    ) -> ToolResult:
        del name, args, approved
        return ToolResult.failure(
            "get_customer",
            "unknown_tool",
            "unknown tool",
        )

    registry.execute = missing_tool
    agent = CustomerAgent(registry)

    context = await agent.run("customer-missing")

    assert context.customer == {}
    assert context.subscription is None
    assert context.previous_tickets == []
