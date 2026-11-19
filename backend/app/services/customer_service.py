from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.guardrails import scrub
from backend.app.repositories.customers import (
    CustomerMemoryRepository,
    CustomerRepository,
)
from backend.app.repositories.tickets import TicketRepository
from backend.app.schemas.customers import (
    CustomerDetail,
    CustomerListResponse,
    CustomerMemoryResponse,
    CustomerSummary,
    CustomerTicketHistoryResponse,
    SubscriptionResponse,
    WorkspaceResponse,
)
from backend.app.schemas.tickets import TicketSummary


class CustomerServiceError(Exception):
    def __init__(self, detail: str, status_code: int) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class CustomerService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.customers = CustomerRepository(session)
        self.tickets = TicketRepository(session)
        self.memory = CustomerMemoryRepository(session)

    async def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> CustomerListResponse:
        if limit < 1 or limit > 100:
            raise CustomerServiceError("limit must be between 1 and 100", 422)
        if offset < 0:
            raise CustomerServiceError("offset cannot be negative", 422)
        customers = await self.customers.list(limit=limit, offset=offset)
        return CustomerListResponse(
            items=[
                CustomerSummary.model_validate(customer)
                for customer in customers
            ]
        )

    async def get_detail(self, customer_id: str) -> CustomerDetail:
        customer = await self.customers.get_with_context(customer_id)
        if customer is None:
            raise CustomerServiceError("Customer not found", 404)

        tickets = sorted(
            customer.tickets,
            key=lambda ticket: ticket.created_at,
            reverse=True,
        )
        memory = await self.memory.list_for_customer(customer_id, limit=10)
        return CustomerDetail(
            id=customer.id,
            name=customer.name,
            email=customer.email,
            company=customer.company,
            plan=customer.plan,
            subscriptions=[
                SubscriptionResponse.model_validate(subscription)
                for subscription in customer.subscriptions
            ],
            workspaces=[
                WorkspaceResponse.model_validate(workspace)
                for workspace in customer.workspaces
            ],
            tickets=[
                TicketSummary.model_validate(ticket)
                for ticket in tickets
            ],
            memory=[
                CustomerMemoryResponse(
                    id=note.id,
                    type=note.type,
                    content=scrub(note.content),
                    source_ticket_id=note.source_ticket_id,
                    created_at=note.created_at,
                )
                for note in memory
            ],
        )

    async def get_ticket_history(
        self,
        customer_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> CustomerTicketHistoryResponse:
        customer = await self.customers.get_by_id(customer_id)
        if customer is None:
            raise CustomerServiceError("Customer not found", 404)
        if limit < 1 or limit > 100:
            raise CustomerServiceError("limit must be between 1 and 100", 422)
        if offset < 0:
            raise CustomerServiceError("offset cannot be negative", 422)

        customer_tickets = await self.tickets.list_for_customer(
            customer_id,
            limit=limit,
            offset=offset,
        )
        return CustomerTicketHistoryResponse(
            items=[
                TicketSummary.model_validate(ticket)
                for ticket in customer_tickets
            ]
        )
