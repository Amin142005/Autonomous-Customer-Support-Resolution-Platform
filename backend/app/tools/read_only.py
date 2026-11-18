from __future__ import annotations

from typing import Literal

from langchain_core.tools import BaseTool, tool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.repositories.customers import (
    CustomerRepository,
    SubscriptionRepository,
)
from backend.app.repositories.tickets import TicketRepository
from backend.app.schemas.customers import CustomerSummary, SubscriptionResponse
from backend.app.schemas.knowledge import KnowledgeSearchRequest
from backend.app.schemas.tickets import TicketSummary
from backend.app.services.knowledge_service import KnowledgeService
from backend.app.tools.registry import ToolRegistry
from integrations.factory import IntegrationBundle


def build_read_only_tools(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    knowledge_service: KnowledgeService,
    integrations: IntegrationBundle,
) -> tuple[BaseTool, ...]:
    @tool
    async def get_customer(customer_id: str) -> dict[str, object]:
        """Read a customer's basic support profile by customer ID."""
        normalized_id = customer_id.strip()
        if not normalized_id:
            raise ValueError("customer_id must not be empty")
        async with session_factory() as session:
            customer = await CustomerRepository(session).get_by_id(normalized_id)
        if customer is None:
            raise LookupError(f"Customer {normalized_id!r} was not found")
        return CustomerSummary.model_validate(customer).model_dump(mode="json")

    @tool
    async def get_subscription(customer_id: str) -> list[dict[str, object]]:
        """Read all subscription records for a customer ID."""
        normalized_id = customer_id.strip()
        if not normalized_id:
            raise ValueError("customer_id must not be empty")
        async with session_factory() as session:
            customer = await CustomerRepository(session).get_by_id(normalized_id)
            if customer is None:
                raise LookupError(f"Customer {normalized_id!r} was not found")
            subscriptions = await SubscriptionRepository(session).list_for_customer(
                normalized_id
            )
        return [
            SubscriptionResponse.model_validate(subscription).model_dump(
                mode="json"
            )
            for subscription in subscriptions
        ]

    @tool
    async def get_ticket_history(
        customer_id: str,
        limit: int = 20,
        offset: int = 0,
        exclude_ticket_id: str | None = None,
    ) -> list[dict[str, object]]:
        """Read prior ticket summaries for a customer without message bodies."""
        normalized_id = customer_id.strip()
        if not normalized_id:
            raise ValueError("customer_id must not be empty")
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        if offset < 0:
            raise ValueError("offset cannot be negative")

        async with session_factory() as session:
            customer = await CustomerRepository(session).get_by_id(normalized_id)
            if customer is None:
                raise LookupError(f"Customer {normalized_id!r} was not found")
            tickets = await TicketRepository(session).list_for_customer(
                normalized_id,
                exclude_ticket_id=exclude_ticket_id,
                limit=limit,
                offset=offset,
            )
        return [
            TicketSummary.model_validate(ticket).model_dump(
                mode="json",
                exclude={"body"},
            )
            for ticket in tickets
        ]

    @tool
    async def search_docs(
        query: str,
        category: str | None = None,
        mode: Literal["hybrid", "semantic", "keyword"] = "hybrid",
        top_k: int = 5,
    ) -> list[dict[str, str | float]]:
        """Search support articles and return ranked passages with citations."""
        request = KnowledgeSearchRequest(
            query=query,
            category=category,
            mode=mode,
            top_k=top_k,
        )
        evidence = await knowledge_service.search(
            request.query,
            category=request.category,
            mode=request.mode,
            top_k=request.top_k,
        )
        return [item.as_dict() for item in evidence]

    @tool
    async def check_service_status(service_name: str) -> dict[str, object]:
        """Read the latest mocked status for a CloudDesk service."""
        normalized_name = service_name.strip()
        if not normalized_name:
            raise ValueError("service_name must not be empty")
        status = await integrations.service_status.check_service_status(
            normalized_name
        )
        return {
            "service_name": status.service_name,
            "state": status.state,
            "summary": status.summary,
            "incident_ids": list(status.incident_ids),
        }

    return (
        get_customer,
        get_subscription,
        get_ticket_history,
        search_docs,
        check_service_status,
    )


def register_read_only_tools(
    registry: ToolRegistry,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    knowledge_service: KnowledgeService,
    integrations: IntegrationBundle,
) -> tuple[str, ...]:
    tools = build_read_only_tools(
        session_factory=session_factory,
        knowledge_service=knowledge_service,
        integrations=integrations,
    )
    for read_only_tool in tools:
        registry.register(read_only_tool)
    return tuple(read_only_tool.name for read_only_tool in tools)
