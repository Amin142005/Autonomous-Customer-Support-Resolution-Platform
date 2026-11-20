from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.guardrails import scrub
from backend.app.schemas.workflow import CustomerContext
from backend.app.tools.registry import ToolRegistry
from backend.app.tools.result import ToolResult


class CustomerAgent:
    """Load customer context through registered tools and durable memory."""

    def __init__(
        self,
        registry: ToolRegistry | Any,
        *,
        memory_service: Any | None = None,
    ) -> None:
        self.registry = registry
        self.memory_service = memory_service

    async def run(
        self,
        customer_id: str,
        *,
        ticket_id: str | None = None,
        exclude_ticket_id: str | None = None,
        limit: int = 20,
    ) -> CustomerContext:
        normalized_id = customer_id.strip()
        if not normalized_id:
            raise ValueError("customer_id must not be empty")
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")

        customer = await self._execute_output(
            "get_customer",
            {"customer_id": normalized_id},
        )
        subscriptions = await self._execute_output(
            "get_subscription",
            {"customer_id": normalized_id},
        )
        previous_tickets = await self._execute_output(
            "get_ticket_history",
            {
                "customer_id": normalized_id,
                "limit": limit,
                "offset": 0,
                "exclude_ticket_id": (
                    exclude_ticket_id
                    if exclude_ticket_id is not None
                    else ticket_id
                ),
            },
        )

        customer_data = customer if isinstance(customer, Mapping) else {}
        subscription_data = (
            subscriptions if isinstance(subscriptions, list) else []
        )
        ticket_data = (
            previous_tickets if isinstance(previous_tickets, list) else []
        )

        workspaces = await self._load_workspaces(normalized_id)
        memory_notes = await self._load_memory_notes(normalized_id)

        return CustomerContext(
            customer=dict(customer_data),
            subscription=(
                subscription_data[0]
                if subscription_data
                and isinstance(subscription_data[0], Mapping)
                else None
            ),
            subscriptions=[
                dict(item) for item in subscription_data
                if isinstance(item, Mapping)
            ],
            workspaces=workspaces,
            previous_tickets=[
                dict(item) for item in ticket_data
                if isinstance(item, Mapping)
            ],
            memory_notes=memory_notes,
        )

    async def _execute_output(
        self,
        tool_name: str,
        arguments: Mapping[str, object],
    ) -> object | None:
        try:
            result: ToolResult | object = await self.registry.execute(
                tool_name,
                arguments,
            )
        except Exception:  # noqa: BLE001
            return None
        if isinstance(result, ToolResult):
            if not result.ok:
                return None
            return result.output
        if isinstance(result, Mapping):
            if result.get("ok") is False:
                return None
            if "output" in result:
                return result["output"]
        return result

    async def _load_workspaces(self, customer_id: str) -> list[dict[str, Any]]:
        tool_names = getattr(self.registry, "tool_names", ())
        if "get_workspaces" not in tool_names:
            return []

        output = await self._execute_output(
            "get_workspaces",
            {"customer_id": customer_id},
        )
        if not isinstance(output, list):
            return []
        return [dict(item) for item in output if isinstance(item, Mapping)]

    async def _load_memory_notes(self, customer_id: str) -> list[str]:
        if self.memory_service is None:
            return []

        recall = getattr(self.memory_service, "recall_customer", None)
        if recall is None:
            recall = getattr(self.memory_service, "recall", None)
        if recall is None:
            return []

        try:
            result = await recall(customer_id, limit=10)
        except Exception:  # noqa: BLE001
            return []
        notes: list[str] = []
        for item in result:
            if isinstance(item, Mapping):
                content = item.get("content")
            else:
                content = getattr(item, "content", None)
            if not isinstance(content, str):
                continue
            scrubbed = scrub(content).strip()
            if scrubbed:
                notes.append(scrubbed)
            if len(notes) >= 10:
                break
        return notes


__all__ = ["CustomerAgent"]
