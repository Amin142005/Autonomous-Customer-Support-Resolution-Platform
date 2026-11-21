from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import ApprovalRequest, Ticket
from backend.app.repositories.tickets import TicketRepository
from backend.app.repositories.workflow import (
    ApprovalRequestRepository,
    WorkflowRunRepository,
)
from backend.app.schemas.common import TicketStatus
from backend.app.schemas.workflow import (
    ApprovalDecisionRequest,
    ApprovalResponse,
    WorkflowStatusResponse,
)
from backend.app.services.workflow_service import WorkflowService
from agents.tracer import WorkflowTracer


class ApprovalServiceError(Exception):
    def __init__(self, detail: str, status_code: int) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class ApprovalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.approvals = ApprovalRequestRepository(session)
        self.runs = WorkflowRunRepository(session)
        self.tickets = TicketRepository(session)

    async def get(self, approval_id: str) -> ApprovalResponse:
        approval = await self.approvals.get_by_id(approval_id)
        if approval is None:
            raise ApprovalServiceError("Approval not found", 404)
        workflow = await self._workflow_status(approval)
        return self._response(approval, workflow)

    async def decide(
        self,
        approval_id: str,
        request: ApprovalDecisionRequest,
        *,
        actor_id: str,
        decision: Literal["approved", "rejected"],
    ) -> ApprovalResponse:
        approval = await self.approvals.get_by_id(approval_id)
        if approval is None:
            raise ApprovalServiceError("Approval not found", 404)
        if approval.status != "pending":
            raise ApprovalServiceError("Approval is no longer pending", 409)
        if approval.workflow_id is None:
            raise ApprovalServiceError("Approval is not attached to a workflow", 409)

        run = await self.runs.get_by_id(approval.workflow_id)
        if run is None:
            raise ApprovalServiceError("Workflow not found", 404)
        if run.status != "paused":
            raise ApprovalServiceError("Workflow is not paused", 409)

        comment = request.comment.strip() if request.comment else ""
        approval.status = decision
        approval.decided_by = actor_id
        approval.reason = comment or None
        approval.decided_at = datetime.now(timezone.utc)

        ticket = await self.tickets.get_by_id(approval.ticket_id)
        if ticket is None:
            raise ApprovalServiceError("Ticket not found", 404)

        if decision == "approved":
            await self.tickets.update(ticket, {"status": TicketStatus.IN_PROGRESS})
        else:
            await self.tickets.update(ticket, {"status": TicketStatus.ESCALATED})

        await self.session.flush()

        tracer = WorkflowTracer(
            self.session,
            ticket_id=approval.ticket_id,
            workflow_id=approval.workflow_id,
        )
        await tracer.record(
            "approval_resolved",
            payload={
                "approval_id": approval.id,
                "decision": decision,
                "decided_by": actor_id,
            },
        )

        workflow = await WorkflowService(self.session).resume_workflow(
            approval.workflow_id,
            {"decision": decision, "comment": comment},
        )

        await self.session.flush()
        await self.session.commit()

        approval = await self.approvals.get_by_id(approval_id)
        if approval is None:
            raise ApprovalServiceError("Approval not found", 404)
        return self._response(approval, workflow)

    async def approve(
        self,
        approval_id: str,
        request: ApprovalDecisionRequest,
        *,
        actor_id: str,
    ) -> ApprovalResponse:
        return await self.decide(
            approval_id,
            request,
            actor_id=actor_id,
            decision="approved",
        )

    async def reject(
        self,
        approval_id: str,
        request: ApprovalDecisionRequest,
        *,
        actor_id: str,
    ) -> ApprovalResponse:
        return await self.decide(
            approval_id,
            request,
            actor_id=actor_id,
            decision="rejected",
        )

    async def _workflow_status(
        self,
        approval: ApprovalRequest,
    ) -> WorkflowStatusResponse | None:
        if approval.workflow_id is None:
            return None
        run = await self.runs.get_by_id(approval.workflow_id)
        if run is None:
            return None
        state = dict(run.state or {})
        return WorkflowStatusResponse(
            workflow_id=run.id,
            status=run.status,
            ticket_id=run.ticket_id,
            thread_id=run.thread_id,
            state=state,
        )

    @staticmethod
    def _response(
        approval: ApprovalRequest,
        workflow: WorkflowStatusResponse | None,
    ) -> ApprovalResponse:
        return ApprovalResponse(
            id=approval.id,
            ticket_id=approval.ticket_id,
            workflow_id=approval.workflow_id,
            action_name=approval.action_name,
            action_args=approval.action_args,
            status=approval.status,
            decided_by=approval.decided_by,
            reason=approval.reason,
            decided_at=approval.decided_at,
            workflow=workflow,
        )


__all__ = ["ApprovalService", "ApprovalServiceError"]
