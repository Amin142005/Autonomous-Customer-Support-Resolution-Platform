from __future__ import annotations

from enum import Enum
from collections.abc import Mapping, Sequence
from typing import Any

from langgraph.types import Command
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from agents.checkpointer import create_checkpointer
from agents.graph import build_support_graph
from backend.app.core.llm import get_llm
from backend.app.models.entities import Ticket, WorkflowRun
from backend.app.repositories.tickets import TicketRepository
from backend.app.repositories.workflow import WorkflowRunRepository
from backend.app.schemas.common import TicketStatus
from backend.app.schemas.workflow import WorkflowRunResponse, WorkflowStatusResponse
from backend.app.tools.registry import ToolRegistry


class WorkflowServiceError(Exception):
    def __init__(self, detail: str, status_code: int) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class WorkflowService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        registry: ToolRegistry | None = None,
        llm: Any | None = None,
        memory_service: Any | None = None,
    ) -> None:
        self.session = session
        self.runs = WorkflowRunRepository(session)
        self.tickets = TicketRepository(session)
        self.registry = registry or ToolRegistry()
        provider = llm if llm is not None else get_llm()
        self.llm = getattr(provider, "llm", provider)
        self.memory_service = memory_service

    async def create_run(self, ticket_id: str) -> WorkflowRunResponse:
        ticket = await self.tickets.get_detail(ticket_id)
        if ticket is None:
            raise WorkflowServiceError("Ticket not found", 404)
        if ticket.status == TicketStatus.WAITING_ON_APPROVAL:
            raise WorkflowServiceError(
                "Ticket already has a workflow waiting on approval",
                409,
            )

        previous = await self.runs.get_latest_for_ticket(ticket_id)
        if previous is not None and previous.status == "paused":
            raise WorkflowServiceError(
                "The current workflow is paused and must be resumed",
                409,
            )

        run = await self.runs.create(
            ticket_id=ticket_id,
            status="running",
            state={},
            thread_id=None,
        )
        await self.session.flush()

        ticket_number = ticket.number
        await self.tickets.update(ticket, {"status": TicketStatus.IN_PROGRESS})
        await self.session.commit()

        thread_id = run.id
        run.thread_id = thread_id
        run.state = {}
        await self.session.flush()
        await self.session.commit()

        return WorkflowRunResponse(workflow_id=run.id)

    async def start_workflow(self, ticket_id: str, workflow_id: str) -> WorkflowStatusResponse:
        ticket = await self.tickets.get_detail(ticket_id)
        run = await self.runs.get_by_id(workflow_id)
        if ticket is None:
            raise WorkflowServiceError("Ticket not found", 404)
        if run is None:
            raise WorkflowServiceError("Workflow not found", 404)

        initial_state = run.state or await self._initial_state(ticket, workflow_id, workflow_id)
        async with create_checkpointer() as checkpointer:
            graph = build_support_graph(checkpointer=checkpointer)
            final_state: dict[str, Any] = dict(initial_state)
            async for update in graph.astream(
                initial_state,
                {"configurable": {"thread_id": workflow_id}},
                stream_mode="values",
            ):
                if isinstance(update, dict):
                    final_state = update
                    run.state = self._safe_state(final_state)
                    run.status = "paused" if final_state.get("paused") else "completed"
                    await self.session.flush()

            await self.session.commit()

        return self._status(run, final_state)

    async def get_status(self, ticket_id: str) -> WorkflowStatusResponse:
        ticket = await self.tickets.get_detail(ticket_id)
        if ticket is None:
            raise WorkflowServiceError("Ticket not found", 404)
        run = await self.runs.get_latest_for_ticket(ticket_id)
        if run is None:
            raise WorkflowServiceError("Workflow not found", 404)
        state = dict(run.state or {})
        return self._status(run, state)

    async def resume_workflow(self, workflow_id: str, resume: Any) -> WorkflowStatusResponse:
        run = await self.runs.get_by_id(workflow_id)
        if run is None:
            raise WorkflowServiceError("Workflow not found", 404)
        if run.status != "paused":
            raise WorkflowServiceError("Workflow is not paused", 409)

        async with create_checkpointer() as checkpointer:
            graph = build_support_graph(checkpointer=checkpointer)
            result = await graph.ainvoke(
                Command(resume=resume),
                {"configurable": {"thread_id": workflow_id}},
            )

        state = dict(result or run.state or {})
        run.state = self._safe_state(state)
        run.status = "completed"
        await self.session.commit()
        return self._status(run, state)

    async def _initial_state(
        self,
        ticket: Ticket,
        workflow_id: str,
        thread_id: str,
    ) -> dict[str, Any]:
        ticket_data = {
            "id": ticket.id,
            "number": ticket.number,
            "customer_id": ticket.customer_id,
            "workspace_id": ticket.workspace_id,
            "subject": ticket.subject,
            "body": ticket.body,
            "channel": str(ticket.channel),
            "category": str(ticket.category) if ticket.category is not None else None,
            "severity": str(ticket.severity) if ticket.severity is not None else None,
        }
        return {
            "ticket_id": ticket.id,
            "ticket_number": ticket.number,
            "customer_id": ticket.customer_id,
            "thread_id": thread_id,
            "workflow_id": workflow_id,
            "ticket": ticket_data,
            "completed_nodes": [],
            "errors": [],
        }

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, Mapping):
            return {
                str(key): WorkflowService._json_safe(item)
                for key, item in value.items()
            }
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return [WorkflowService._json_safe(item) for item in value]
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        return str(value)

    @classmethod
    def _safe_state(cls, state: dict[str, Any]) -> dict[str, Any]:
        """Persist only JSON-safe workflow fields; omit runtime dependencies."""
        return {
            str(key): cls._json_safe(value)
            for key, value in state.items()
            if key not in {
                "registry",
                "tool_registry",
                "memory_service",
                "memory",
                "llm",
            }
        }

    @staticmethod
    def _status(run: WorkflowRun, state: dict[str, Any]) -> WorkflowStatusResponse:
        return WorkflowStatusResponse(
            workflow_id=run.id,
            status=run.status,
            ticket_id=run.ticket_id,
            thread_id=run.thread_id,
            state=WorkflowService._safe_state(state),
        )


__all__ = ["WorkflowService", "WorkflowServiceError"]
