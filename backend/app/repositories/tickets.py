from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.entities import Customer, Ticket, TicketMessage
from backend.app.repositories.base import BaseRepository
from backend.app.schemas.common import Category, Severity, TicketStatus


class TicketRepository(BaseRepository[Ticket]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Ticket)

    async def get_by_number(self, number: str) -> Ticket | None:
        statement = select(Ticket).where(Ticket.number == number)
        return await self.session.scalar(statement)

    async def next_ticket_number(self) -> str:
        statement = select(Ticket.number)
        result = await self.session.scalars(statement)
        highest = 1000
        for number in result.all():
            suffix = number.rpartition("-")[2]
            if suffix.isdigit():
                highest = max(highest, int(suffix))
        return f"CD-{highest + 1}"

    async def get_detail(self, ticket_id: str) -> Ticket | None:
        statement = (
            select(Ticket)
            .where(Ticket.id == ticket_id)
            .options(
                selectinload(Ticket.customer).selectinload(Customer.subscriptions),
                selectinload(Ticket.customer).selectinload(Customer.workspaces),
                selectinload(Ticket.customer).selectinload(Customer.memory),
                selectinload(Ticket.workspace),
                selectinload(Ticket.messages),
            )
        )
        return await self.session.scalar(statement)

    async def list_tickets(
        self,
        *,
        status: TicketStatus | None = None,
        category: Category | None = None,
        severity: Severity | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Ticket]:
        if limit < 1:
            raise ValueError("limit must be greater than zero")
        if offset < 0:
            raise ValueError("offset cannot be negative")

        statement = select(Ticket)
        if status is not None:
            statement = statement.where(Ticket.status == status)
        if category is not None:
            statement = statement.where(Ticket.category == category)
        if severity is not None:
            statement = statement.where(Ticket.severity == severity)
        statement = (
            statement.order_by(Ticket.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.scalars(statement)
        return list(result.all())

    async def list_for_customer(
        self,
        customer_id: str,
        *,
        exclude_ticket_id: str | None = None,
        limit: int = 20,
    ) -> list[Ticket]:
        if limit < 1:
            raise ValueError("limit must be greater than zero")

        statement = select(Ticket).where(Ticket.customer_id == customer_id)
        if exclude_ticket_id is not None:
            statement = statement.where(Ticket.id != exclude_ticket_id)
        statement = (
            statement.order_by(Ticket.created_at.desc()).limit(limit)
        )
        result = await self.session.scalars(statement)
        return list(result.all())


class TicketMessageRepository(BaseRepository[TicketMessage]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TicketMessage)

    async def list_for_ticket(self, ticket_id: str) -> list[TicketMessage]:
        statement = (
            select(TicketMessage)
            .where(TicketMessage.ticket_id == ticket_id)
            .order_by(TicketMessage.created_at.asc())
        )
        result = await self.session.scalars(statement)
        return list(result.all())
