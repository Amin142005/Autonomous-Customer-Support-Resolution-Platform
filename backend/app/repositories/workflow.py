from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import (
    ApprovalRequest,
    Escalation,
    ResolutionAction,
    WorkflowEvent,
    WorkflowRun,
)
from backend.app.repositories.base import BaseRepository


class WorkflowRunRepository(BaseRepository[WorkflowRun]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, WorkflowRun)

    async def get_latest_for_ticket(self, ticket_id: str) -> WorkflowRun | None:
        statement = (
            select(WorkflowRun)
            .where(WorkflowRun.ticket_id == ticket_id)
            .order_by(WorkflowRun.created_at.desc())
            .limit(1)
        )
        return await self.session.scalar(statement)


class WorkflowEventRepository(BaseRepository[WorkflowEvent]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, WorkflowEvent)

    async def list_for_workflow(self, workflow_id: str) -> list[WorkflowEvent]:
        statement = (
            select(WorkflowEvent)
            .where(WorkflowEvent.workflow_id == workflow_id)
            .order_by(WorkflowEvent.created_at.asc())
        )
        result = await self.session.scalars(statement)
        return list(result.all())


class ResolutionActionRepository(BaseRepository[ResolutionAction]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ResolutionAction)

    async def list_for_ticket(self, ticket_id: str) -> list[ResolutionAction]:
        statement = (
            select(ResolutionAction)
            .where(ResolutionAction.ticket_id == ticket_id)
            .order_by(ResolutionAction.created_at.asc())
        )
        result = await self.session.scalars(statement)
        return list(result.all())


class ApprovalRequestRepository(BaseRepository[ApprovalRequest]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ApprovalRequest)

    async def get_pending_for_ticket(self, ticket_id: str) -> ApprovalRequest | None:
        statement = (
            select(ApprovalRequest)
            .where(
                ApprovalRequest.ticket_id == ticket_id,
                ApprovalRequest.status == "pending",
            )
            .order_by(ApprovalRequest.created_at.desc())
            .limit(1)
        )
        return await self.session.scalar(statement)


class EscalationRepository(BaseRepository[Escalation]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Escalation)

    async def list_open(self, *, limit: int = 100, offset: int = 0) -> list[Escalation]:
        if limit < 1:
            raise ValueError("limit must be greater than zero")
        if offset < 0:
            raise ValueError("offset cannot be negative")
        statement = (
            select(Escalation)
            .where(Escalation.status == "open")
            .order_by(Escalation.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.scalars(statement)
        return list(result.all())

    async def get_open_for_ticket(self, ticket_id: str) -> Escalation | None:
        statement = (
            select(Escalation)
            .where(
                Escalation.ticket_id == ticket_id,
                Escalation.status == "open",
            )
            .order_by(Escalation.created_at.desc())
            .limit(1)
        )
        return await self.session.scalar(statement)
