from __future__ import annotations

from decimal import Decimal, InvalidOperation

from langchain_core.tools import BaseTool, tool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.repositories.tickets import TicketRepository
from backend.app.schemas.common import Category, Severity, TicketStatus
from backend.app.schemas.tickets import TicketSummary
from backend.app.tools.registry import ToolRegistry
from integrations.factory import IntegrationBundle


def build_write_tools(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    integrations: IntegrationBundle,
) -> tuple[BaseTool, ...]:
    @tool
    async def update_ticket(
        ticket_id: str,
        status: str | None = None,
        summary: str | None = None,
        category: str | None = None,
        severity: str | None = None,
        subject: str | None = None,
        assignee_id: str | None = None,
    ) -> dict[str, object]:
        """Update a ticket's status or support metadata without changing its message body."""
        normalized_id = ticket_id.strip()
        if not normalized_id:
            raise ValueError("ticket_id must not be empty")

        values: dict[str, object] = {}
        if status is not None:
            values["status"] = TicketStatus(status.strip().lower())
        if summary is not None:
            normalized_summary = summary.strip()
            if not normalized_summary:
                raise ValueError("summary must not be empty")
            values["summary"] = normalized_summary
        if category is not None:
            values["category"] = Category(category.strip().lower())
        if severity is not None:
            values["severity"] = Severity(severity.strip().lower())
        if subject is not None:
            normalized_subject = subject.strip()
            if not normalized_subject:
                raise ValueError("subject must not be empty")
            values["subject"] = normalized_subject
        if assignee_id is not None:
            normalized_assignee = assignee_id.strip()
            values["assignee_id"] = normalized_assignee or None
        if not values:
            raise ValueError("At least one ticket field must be provided")

        async with session_factory() as session:
            repository = TicketRepository(session)
            ticket = await repository.get_by_id(normalized_id)
            if ticket is None:
                raise LookupError(f"Ticket {normalized_id!r} was not found")
            updated = await repository.update(ticket, values)
            await session.commit()
        return TicketSummary.model_validate(updated).model_dump(mode="json")

    @tool
    async def reset_demo_setting(
        workspace_id: str,
        setting_name: str,
        default_value: object,
    ) -> dict[str, object]:
        """Reset a workspace setting to its approved default value in the mock workspace integration."""
        normalized_workspace = workspace_id.strip()
        normalized_setting = setting_name.strip()
        if not normalized_workspace:
            raise ValueError("workspace_id must not be empty")
        if not normalized_setting:
            raise ValueError("setting_name must not be empty")

        reset = await integrations.workspace_admin.reset_setting(
            normalized_workspace,
            normalized_setting,
            default_value,
        )
        return {
            "workspace_id": reset.workspace_id,
            "setting_name": reset.setting_name,
            "value": reset.value,
            "simulated": reset.simulated,
        }

    @tool
    async def create_refund_request(
        customer_id: str,
        amount: str | float,
        reason: str,
    ) -> dict[str, object]:
        """Create a simulated refund request for a customer; real money is never charged."""
        normalized_customer = customer_id.strip()
        normalized_reason = reason.strip()
        if not normalized_customer:
            raise ValueError("customer_id must not be empty")
        if not normalized_reason:
            raise ValueError("reason must not be empty")
        if isinstance(amount, bool):
            raise TypeError("amount must be a positive finite Decimal")

        try:
            decimal_amount = Decimal(str(amount))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError("amount must be a positive finite Decimal") from exc
        if not decimal_amount.is_finite() or decimal_amount <= 0:
            raise ValueError("amount must be a positive finite Decimal")

        receipt = await integrations.billing.create_refund_request(
            normalized_customer,
            decimal_amount,
            normalized_reason,
        )
        return {
            "request_id": receipt.request_id,
            "customer_id": receipt.customer_id,
            "amount": str(receipt.amount),
            "status": receipt.status,
            "simulated": receipt.simulated,
        }

    return update_ticket, reset_demo_setting, create_refund_request


def register_write_tools(
    registry: ToolRegistry,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    integrations: IntegrationBundle,
) -> tuple[str, ...]:
    tools = build_write_tools(
        session_factory=session_factory,
        integrations=integrations,
    )
    for write_tool in tools:
        registry.register(
            write_tool,
            requires_approval=(write_tool.name == "reset_demo_setting"),
        )
    return tuple(write_tool.name for write_tool in tools)
