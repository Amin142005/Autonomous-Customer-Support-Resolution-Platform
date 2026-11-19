from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.redis import RedisProtocol
from backend.app.models.entities import CustomerMemory
from memory.long_term import LongTermMemory
from memory.short_term import ShortTermMemory


class MemoryService:
    """Coordinate short-term Redis memory and durable customer memory."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        redis_client: RedisProtocol | None = None,
    ) -> None:
        self.session = session
        self.short_term = ShortTermMemory(redis_client)
        self.long_term = LongTermMemory(session)

    async def recall_customer(
        self,
        customer_id: str,
        *,
        limit: int = 10,
    ) -> list[CustomerMemory]:
        return await self.long_term.recall(customer_id, limit=limit)

    recall = recall_customer

    async def record_resolution(
        self,
        customer_id: str,
        *,
        ticket_id: str,
        past_issue: str,
        troubleshooting_steps: Iterable[str],
        resolution_note: str,
    ) -> list[tuple[CustomerMemory, bool]]:
        """Record the durable resolution summary for a completed workflow."""
        normalized_ticket = ticket_id.strip()
        if not normalized_ticket:
            raise ValueError("ticket_id must not be empty")

        steps = [
            step.strip()
            for step in troubleshooting_steps
            if isinstance(step, str) and step.strip()
        ][0:3]

        records: list[tuple[CustomerMemory, bool]] = []
        try:
            past_issue_record, past_issue_created = await self.long_term.record(
                customer_id,
                type="past_issue",
                content=past_issue,
                source_ticket_id=normalized_ticket,
            )
            records.append((past_issue_record, past_issue_created))

            for step in steps:
                step_record, step_created = await self.long_term.record(
                    customer_id,
                    type="troubleshooting",
                    content=step,
                    source_ticket_id=normalized_ticket,
                )
                records.append((step_record, step_created))

            resolution_record, resolution_created = await self.long_term.record(
                customer_id,
                type="note",
                content=resolution_note,
                source_ticket_id=normalized_ticket,
            )
            records.append((resolution_record, resolution_created))

            await self.session.commit()
            return records
        except Exception:
            await self.session.rollback()
            raise

    async def get_conversation(self, ticket_id: str) -> list[Any]:
        return await self.short_term.get_conversation(ticket_id)

    async def append_conversation(
        self,
        ticket_id: str,
        message: object,
    ) -> list[Any]:
        return await self.short_term.append_conversation(ticket_id, message)

    async def get_workflow_state(self, workflow_id: str) -> Any | None:
        return await self.short_term.get_workflow_state(workflow_id)

    async def set_workflow_state(
        self,
        workflow_id: str,
        state: dict[str, object] | object,
    ) -> bool:
        return await self.short_term.set_workflow_state(workflow_id, state)
