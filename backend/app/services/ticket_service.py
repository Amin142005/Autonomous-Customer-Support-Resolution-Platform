from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import Ticket
from backend.app.repositories.customers import (
    CustomerRepository,
    WorkspaceRepository,
)
from backend.app.repositories.tickets import (
    TicketMessageRepository,
    TicketRepository,
)
from backend.app.schemas.common import (
    Category,
    Channel,
    Severity,
    TicketStatus,
)
from backend.app.schemas.tickets import (
    TicketCreateRequest,
    TicketCustomerSummary,
    TicketDetail,
    TicketListResponse,
    TicketMessageResponse,
    TicketSummary,
    TicketWorkspaceSummary,
)


class TicketServiceError(Exception):
    def __init__(self, detail: str, status_code: int) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class TicketService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tickets = TicketRepository(session)
        self.customers = CustomerRepository(session)
        self.workspaces = WorkspaceRepository(session)
        self.messages = TicketMessageRepository(session)

    async def list(
        self,
        *,
        status: TicketStatus | None = None,
        category: Category | None = None,
        severity: Severity | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> TicketListResponse:
        if limit < 1 or limit > 100:
            raise TicketServiceError("limit must be between 1 and 100", 422)
        if offset < 0:
            raise TicketServiceError("offset cannot be negative", 422)
        tickets = await self.tickets.list_tickets(
            status=status,
            category=category,
            severity=severity,
            limit=limit,
            offset=offset,
        )
        return TicketListResponse(items=[TicketSummary.model_validate(ticket) for ticket in tickets])

    async def get_detail(self, ticket_id: str) -> TicketDetail:
        ticket = await self.tickets.get_detail(ticket_id)
        if ticket is None:
            raise TicketServiceError("Ticket not found", 404)
        return self._detail(ticket)

    async def create(self, request: TicketCreateRequest) -> TicketDetail:
        if request.customer_id is not None:
            customer = await self.customers.get_by_id(request.customer_id)
            if customer is None:
                raise TicketServiceError("Customer not found", 404)
        else:
            if request.customer is None:
                raise TicketServiceError(
                    "Provide exactly one of customer_id or customer",
                    422,
                )
            email = request.customer.email.strip().lower()
            customer = await self.customers.get_by_email(email)
            if customer is None:
                customer = await self.customers.create(
                    name=request.customer.name.strip(),
                    email=email,
                    company=request.customer.company,
                    plan=request.customer.plan,
                )

        if request.workspace_id is not None:
            workspace = await self.workspaces.get_by_id(request.workspace_id)
            if workspace is None or workspace.customer_id != customer.id:
                raise TicketServiceError(
                    "Workspace not found for customer",
                    404,
                )
        else:
            workspace = None

        ticket = await self.tickets.create(
            number=await self.tickets.next_ticket_number(),
            customer_id=customer.id,
            workspace_id=workspace.id if workspace is not None else None,
            subject=request.subject.strip(),
            body=request.body.strip(),
            channel=Channel(request.channel),
            status=TicketStatus.NEW,
        )
        await self.messages.create(
            ticket_id=ticket.id,
            author_type="customer",
            body=request.body.strip(),
        )
        await self.session.commit()

        detail = await self.tickets.get_detail(ticket.id)
        if detail is None:
            raise TicketServiceError("Ticket not found after creation", 500)
        return self._detail(detail)

    def _detail(self, ticket: Ticket) -> TicketDetail:
        customer = ticket.customer
        workspace = ticket.workspace
        messages = [
            TicketMessageResponse.model_validate(message)
            for message in sorted(ticket.messages, key=lambda item: item.created_at)
        ]
        return TicketDetail(
            id=ticket.id,
            number=ticket.number,
            customer_id=ticket.customer_id,
            workspace_id=ticket.workspace_id,
            subject=ticket.subject,
            body=ticket.body,
            channel=ticket.channel,
            category=ticket.category,
            severity=ticket.severity,
            status=ticket.status,
            summary=ticket.summary,
            assignee_id=ticket.assignee_id,
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
            customer=TicketCustomerSummary.model_validate(customer),
            workspace=(
                TicketWorkspaceSummary.model_validate(workspace)
                if workspace is not None
                else None
            ),
            messages=messages,
        )
