from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.guardrails import scrub
from backend.app.models.entities import CustomerMemory
from backend.app.repositories.customers import (
    CustomerMemoryRepository,
    CustomerRepository,
)
from backend.app.repositories.tickets import TicketRepository

PERMITTED_MEMORY_TYPES = frozenset(
    {
        "preference",
        "past_issue",
        "troubleshooting",
        "note",
    }
)


class LongTermMemoryError(ValueError):
    pass


class LongTermMemory:
    """Safely store and recall durable, customer-scoped memory notes."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        permitted_types: frozenset[str] = PERMITTED_MEMORY_TYPES,
    ) -> None:
        self.session = session
        self.permitted_types = permitted_types
        self.customers = CustomerRepository(session)
        self.tickets = TicketRepository(session)
        self.memory = CustomerMemoryRepository(session)

    async def recall(
        self,
        customer_id: str,
        *,
        limit: int = 10,
    ) -> list[CustomerMemory]:
        normalized_customer = customer_id.strip()
        if not normalized_customer:
            raise LongTermMemoryError("customer_id must not be empty")
        if limit < 1 or limit > 10:
            raise LongTermMemoryError("limit must be between 1 and 10")

        customer = await self.customers.get_by_id(normalized_customer)
        if customer is None:
            raise LookupError(f"Customer {normalized_customer!r} was not found")
        return await self.memory.list_for_customer(normalized_customer, limit=limit)

    async def record(
        self,
        customer_id: str,
        *,
        type: str,
        content: str,
        source_ticket_id: str | None = None,
    ) -> tuple[CustomerMemory, bool]:
        """Create a scrubbed note, returning `(note, created)`."""
        normalized_customer = customer_id.strip()
        if not normalized_customer:
            raise LongTermMemoryError("customer_id must not be empty")

        normalized_type = type.strip().lower()
        if normalized_type not in self.permitted_types:
            allowed = ", ".join(sorted(self.permitted_types))
            raise LongTermMemoryError(
                f"type must be one of: {allowed}"
            )

        if not isinstance(content, str):
            raise LongTermMemoryError("content must be text")
        normalized_content = scrub(content).strip()
        if not normalized_content:
            raise LongTermMemoryError("content must not be empty")

        customer = await self.customers.get_by_id(normalized_customer)
        if customer is None:
            raise LookupError(f"Customer {normalized_customer!r} was not found")

        normalized_source = (
            source_ticket_id.strip()
            if isinstance(source_ticket_id, str)
            else source_ticket_id
        )
        if normalized_source is not None:
            if not normalized_source:
                normalized_source = None
            else:
                ticket = await self.tickets.get_by_id(normalized_source)
                if ticket is None:
                    raise LookupError(
                        f"Ticket {normalized_source!r} was not found"
                    )
                if ticket.customer_id != normalized_customer:
                    raise LongTermMemoryError(
                        "source_ticket_id must belong to the customer"
                    )
                if (
                    normalized_content.casefold()
                    == ticket.body.strip().casefold()
                    or (
                        ticket.body.strip()
                        and ticket.body.strip().casefold()
                        in normalized_content.casefold()
                    )
                ):
                    raise LongTermMemoryError(
                        "raw ticket body cannot be stored in memory"
                    )

        exact = await self.memory.find_exact(
            normalized_customer,
            type=normalized_type,
            content=normalized_content,
            source_ticket_id=normalized_source,
        )
        if exact is not None:
            return exact, False

        note = await self.memory.create(
            customer_id=normalized_customer,
            type=normalized_type,
            content=normalized_content,
            source_ticket_id=normalized_source,
        )
        await self.session.flush()
        return note, True

    async def has_note(
        self,
        customer_id: str,
        *,
        type: str,
        content: str,
        source_ticket_id: str | None = None,
    ) -> bool:
        normalized_customer = customer_id.strip()
        normalized_type = type.strip().lower()
        normalized_content = scrub(content).strip()
        normalized_source = (
            source_ticket_id.strip()
            if isinstance(source_ticket_id, str)
            else source_ticket_id
        )
        if not normalized_customer or not normalized_type or not normalized_content:
            return False
        note = await self.memory.find_exact(
            normalized_customer,
            type=normalized_type,
            content=normalized_content,
            source_ticket_id=normalized_source or None,
        )
        return note is not None

    record_unique = record
