from __future__ import annotations

from enum import Enum
from collections.abc import Mapping, Sequence
from typing import Any

from langgraph.types import Command
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agents.checkpointer import create_checkpointer
from agents.tracer import WorkflowTracer
from agents.graph import build_support_graph
from backend.app.core.llm import get_llm
from backend.app.core.config import get_settings
from backend.app.models.entities import Ticket, WorkflowRun
from backend.app.repositories.tickets import TicketRepository
from backend.app.repositories.workflow import (
    ApprovalRequestRepository,
    WorkflowEventRepository,
    WorkflowRunRepository,
)
from backend.app.schemas.common import TicketStatus
from backend.app.schemas.workflow import WorkflowRunResponse, WorkflowStatusResponse
from backend.app.tools.registry import ToolRegistry
from backend.app.services.escalation_service import EscalationService
from backend.app.tools.read_only import register_read_only_tools
from backend.app.tools.write_tools import register_write_tools
from backend.app.services.knowledge_service import KnowledgeService
from integrations.factory import create_integrations


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
        self.events = WorkflowEventRepository(session)
        self.approvals = ApprovalRequestRepository(session)
        self.tickets = TicketRepository(session)
        self.registry = registry or ToolRegistry()
        if registry is None:
            bind = getattr(session, "bind", None)
            engine = getattr(bind, "engine", bind)
            if engine is not None:
                session_factory = async_sessionmaker(engine, expire_on_commit=False)
                settings = get_settings()
                knowledge = KnowledgeService.from_settings(settings)
                integrations = create_integrations()
                register_read_only_tools(
                    self.registry,
                    session_factory=session_factory,
                    knowledge_service=knowledge,
                    integrations=integrations,
                )
                register_write_tools(
                    self.registry,
                    session_factory=session_factory,
                    integrations=integrations,
                )
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

        initial_state = dict(run.state or await self._initial_state(ticket, workflow_id, workflow_id))
        initial_state.setdefault("registry", self.registry)
        initial_state.setdefault("llm", self.llm)
        initial_state.setdefault("memory_service", self.memory_service)

        tracer = WorkflowTracer(
            self.session,
            ticket_id=ticket_id,
            workflow_id=workflow_id,
        )
        previous_started: set[str] = set()
        previous_completed: set[str] = set()
        previous_tools: set[tuple[str, str]] = set()
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
                    interrupts = update.get("__interrupt__")
                    interrupt_list = (
                        list(interrupts)
                        if isinstance(interrupts, (list, tuple))
                        else []
                    )

                    if interrupt_list:
                        interrupt_value = getattr(interrupt_list[0], "value", interrupt_list[0])
                        interrupt_payload = (
                            dict(interrupt_value)
                            if isinstance(interrupt_value, Mapping)
                            else {"kind": "human_approval"}
                        )
                        actions = interrupt_payload.get("actions", [])
                        action_items = actions if isinstance(actions, list) else []

                        existing = await self.approvals.get_pending_for_ticket(ticket_id)
                        approval_id = existing.id if existing is not None else None
                        if existing is None:
                            for action in action_items:
                                if not isinstance(action, Mapping):
                                    continue
                                tool_name = str(action.get("tool", "unknown"))
                                action_args = (
                                    dict(action.get("arguments", {}))
                                    if isinstance(action.get("arguments"), Mapping)
                                    else {}
                                )
                                created = await self.approvals.create(
                                    ticket_id=ticket_id,
                                    workflow_id=workflow_id,
                                    action_name=tool_name,
                                    action_args=action_args,
                                    status="pending",
                                )
                                if approval_id is None:
                                    approval_id = created.id

                        await self.tickets.update(
                            ticket,
                            {"status": TicketStatus.WAITING_ON_APPROVAL},
                        )
                        run.status = "paused"
                        final_state["approval_status"] = "pending"
                        final_state["paused"] = True
                        final_state["approval_id"] = approval_id
                        await tracer.record(
                            "approval_requested",
                            payload={"actions": action_items},
                        )

                    run.state = self._safe_state(final_state)
                    run.status = (
                        "paused"
                        if final_state.get("paused")
                        or interrupt_list
                        else "completed"
                    )

                    current_node = str(final_state.get("current_node") or "")
                    if current_node and current_node not in previous_started:
                        previous_started.add(current_node)
                        await tracer.node_started(current_node)

                    tool_names = {
                        "customer_context": ("get_customer", "get_subscription", "get_ticket_history"),
                        "knowledge_retrieval": ("search_docs",),
                        "troubleshooting": ("check_service_status",),
                    }
                    if current_node in tool_names:
                        for tool_name in tool_names[current_node]:
                            key = (current_node, tool_name)
                            if key not in previous_tools:
                                previous_tools.add(key)
                                await tracer.tool_called(tool_name, node_name=current_node)

                    completed = final_state.get("completed_nodes", [])
                    if isinstance(completed, (list, tuple)):
                        for node_name in completed:
                            name = str(node_name)
                            if name and name not in previous_completed:
                                previous_completed.add(name)
                                await tracer.node_completed(name, duration_ms=0)

                    execution = final_state.get("resolution_execution")
                    if isinstance(execution, list) and execution:
                        from backend.app.repositories.workflow import ResolutionActionRepository

                        action_repository = ResolutionActionRepository(self.session)
                        approval_id = final_state.get("approval_id")
                        approved_by = None
                        if approval_id:
                            approval = await self.approvals.get_by_id(str(approval_id))
                            approved_by = approval.decided_by if approval is not None else None

                        existing_actions = await action_repository.list_for_ticket(ticket_id)
                        existing_keys = {
                            (item.tool_name, str(item.args or {}), item.status)
                            for item in existing_actions
                        }
                        for item in execution:
                            if not isinstance(item, Mapping):
                                continue
                            tool_name = str(item.get("tool", "unknown"))
                            arguments = (
                                dict(item.get("arguments", {}))
                                if isinstance(item.get("arguments"), Mapping)
                                else {}
                            )
                            status = str(item.get("status", "unknown"))
                            key = (tool_name, str(arguments), status)
                            if key in existing_keys:
                                continue
                            await action_repository.create(
                                ticket_id=ticket_id,
                                workflow_id=workflow_id,
                                tool_name=tool_name,
                                args=arguments,
                                status=status,
                                result=(
                                    dict(item.get("output", {}))
                                    if isinstance(item.get("output"), Mapping)
                                    else None
                                ),
                                approved_by=(
                                    approved_by
                                    if bool(item.get("approval_required", False))
                                    else None
                                ),
                            )
                            existing_keys.add(key)

                    usage = final_state.get("token_usage")
                    if usage is not None:
                        current_node = str(final_state.get("current_node") or "workflow")
                        await tracer.llm_called(
                            node_name=current_node,
                            usage=usage,
                        )
                    await self.session.flush()

            if run.status != "paused":
                await tracer.workflow_completed()
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
            "registry": self.registry,
            "llm": self.llm,
            "memory_service": self.memory_service,
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
                "__interrupt__",
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
