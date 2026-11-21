from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agents.tracer import WorkflowTracer
from backend.app.models.entities import Escalation
from backend.app.repositories.tickets import TicketRepository
from backend.app.repositories.workflow import EscalationRepository
from backend.app.schemas.common import TicketStatus
from backend.app.schemas.workflow import (
    EscalationDecision,
    EscalationResponse,
    EscalationListResponse,
)


class EscalationServiceError(Exception):
    def __init__(self, detail: str, status_code: int) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class EscalationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.escalations = EscalationRepository(session)
        self.tickets = TicketRepository(session)

    async def route(
        self,
        *,
        ticket_id: str,
        workflow_id: str,
        decision: EscalationDecision,
    ) -> Escalation:
        if not decision.escalation_required:
            raise EscalationServiceError("Escalation is not required", 409)

        team = (decision.team or "support operations").strip()
        reason = (decision.reason or "The workflow requires specialist review.").strip()
        if not team:
            team = "support operations"
        if not reason:
            reason = "The workflow requires specialist review."

        ticket = await self.tickets.get_by_id(ticket_id)
        if ticket is None:
            raise EscalationServiceError("Ticket not found", 404)

        existing = await self.escalations.get_open_for_ticket(ticket_id)
        if existing is not None:
            await self.tickets.update(ticket, {"status": TicketStatus.ESCALATED})
            await self.session.flush()
            return existing

        escalation = await self.escalations.create(
            ticket_id=ticket_id,
            team=team,
            reason=reason,
            status="open",
        )
        await self.tickets.update(ticket, {"status": TicketStatus.ESCALATED})
        await self.session.flush()

        tracer = WorkflowTracer(
            self.session,
            ticket_id=ticket_id,
            workflow_id=workflow_id,
        )
        await tracer.record(
            "escalation_created",
            node_name="escalation",
            payload={
                "escalation_id": escalation.id,
                "team": team,
                "reason": reason,
            },
        )
        await self.session.flush()

        return escalation

    async def list_open(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> EscalationListResponse:
        if limit < 1 or limit > 100:
            raise EscalationServiceError("limit must be between 1 and 100", 422)
        if offset < 0:
            raise EscalationServiceError("offset cannot be negative", 422)

        escalations = await self.escalations.list_open(limit=limit, offset=offset)
        return EscalationListResponse(
            items=[self._response(item) for item in escalations]
        )

    async def get(self, escalation_id: str) -> EscalationResponse:
        escalation = await self.escalations.get_by_id(escalation_id)
        if escalation is None:
            raise EscalationServiceError("Escalation not found", 404)
        return self._response(escalation)

    @staticmethod
    def _response(escalation: Escalation) -> EscalationResponse:
        return EscalationResponse(
            id=escalation.id,
            ticket_id=escalation.ticket_id,
            team=escalation.team,
            reason=escalation.reason,
            status=escalation.status,
            created_at=escalation.created_at,
            updated_at=escalation.updated_at,
        )


__all__ = ["EscalationService", "EscalationServiceError"]
