from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_session
from backend.app.core.security import AuthenticatedUser, require_role
from backend.app.repositories.workflow import WorkflowEventRepository, WorkflowRunRepository
from backend.app.schemas.common import (
    Category,
    Role,
    Severity,
    TicketStatus,
)
from backend.app.schemas.tickets import (
    TicketActionResponse,
    TicketCreateRequest,
    TicketCreateResponse,
    TicketDetail,
    TicketListResponse,
    TicketReplyRequest,
)
from backend.app.schemas.workflow import (
    WorkflowEventResponse,
    WorkflowEventsResponse,
    WorkflowRunResponse,
    WorkflowStatusResponse,
)
from backend.app.services.ticket_service import (
    TicketService,
    TicketServiceError,
)
from backend.app.services.workflow_service import (
    WorkflowService,
    WorkflowServiceError,
)

router = APIRouter(prefix="/tickets", tags=["tickets"])

ViewerUser = Annotated[AuthenticatedUser, Depends(require_role(Role.VIEWER))]
AgentUser = Annotated[AuthenticatedUser, Depends(require_role(Role.AGENT))]


def _raise_service_error(exc: TicketServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("", response_model=TicketListResponse)
async def list_tickets(
    _current_user: ViewerUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    status_filter: TicketStatus | None = Query(default=None, alias="status"),  # noqa: B008
    category: Category | None = None,
    severity: Severity | None = None,
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> TicketListResponse:
    try:
        return await TicketService(session).list(
            status=status_filter,
            category=category,
            severity=severity,
            limit=limit,
            offset=offset,
        )
    except TicketServiceError as exc:
        _raise_service_error(exc)


@router.post("", response_model=TicketCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    request: TicketCreateRequest,
    _current_user: AgentUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> TicketCreateResponse:
    try:
        detail = await TicketService(session).create(request)
        return TicketCreateResponse(ticket=detail)
    except TicketServiceError as exc:
        _raise_service_error(exc)


@router.get("/{ticket_id}", response_model=TicketDetail)
async def get_ticket(
    ticket_id: str,
    _current_user: ViewerUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> TicketDetail:
    try:
        return await TicketService(session).get_detail(ticket_id)
    except TicketServiceError as exc:
        _raise_service_error(exc)


@router.post("/{ticket_id}/run", response_model=WorkflowRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_workflow(
    ticket_id: str,
    background_tasks: BackgroundTasks,
    _current_user: AgentUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> WorkflowRunResponse:
    try:
        response = await WorkflowService(session).create_run(ticket_id)
        background_tasks.add_task(
            WorkflowService(session).start_workflow,
            ticket_id,
            response.workflow_id,
        )
        return response
    except WorkflowServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/{ticket_id}/workflow", response_model=WorkflowStatusResponse)
async def get_workflow(
    ticket_id: str,
    _current_user: ViewerUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> WorkflowStatusResponse:
    try:
        return await WorkflowService(session).get_status(ticket_id)
    except WorkflowServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/{ticket_id}/events", response_model=WorkflowEventsResponse)
async def get_workflow_events(
    ticket_id: str,
    _current_user: ViewerUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> WorkflowEventsResponse:
    try:
        await TicketService(session).get_detail(ticket_id)
    except TicketServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    run = await WorkflowRunRepository(session).get_latest_for_ticket(ticket_id)
    if run is None:
        return WorkflowEventsResponse(items=[])

    events = await WorkflowEventRepository(session).list_for_workflow(run.id)
    items = [
        WorkflowEventResponse(
            id=event.id,
            ticket_id=event.ticket_id,
            workflow_id=event.workflow_id,
            event_type=event.event_type,
            node_name=event.node_name,
            payload=event.payload,
            duration_ms=event.duration_ms,
            token_usage=event.token_usage,
            created_at=event.created_at,
        )
        for event in events
    ]
    return WorkflowEventsResponse(items=items)


@router.post("/{ticket_id}/reply", response_model=TicketActionResponse)
async def reply_ticket(
    ticket_id: str,
    request: TicketReplyRequest,
    current_user: AgentUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> TicketActionResponse:
    try:
        detail = await TicketService(session).reply(
            ticket_id,
            request.body,
            actor_id=current_user.id,
        )
        return TicketActionResponse(ticket=detail, message="Customer reply recorded")
    except TicketServiceError as exc:
        _raise_service_error(exc)


@router.post("/{ticket_id}/request-info", response_model=TicketActionResponse)
async def request_ticket_info(
    ticket_id: str,
    request: TicketReplyRequest,
    current_user: AgentUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> TicketActionResponse:
    try:
        detail = await TicketService(session).request_info(
            ticket_id,
            request.body,
            actor_id=current_user.id,
        )
        return TicketActionResponse(ticket=detail, message="Information request recorded")
    except TicketServiceError as exc:
        _raise_service_error(exc)


@router.post("/{ticket_id}/escalate", response_model=TicketActionResponse)
async def escalate_ticket(
    ticket_id: str,
    request: TicketReplyRequest,
    _current_user: AgentUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> TicketActionResponse:
    try:
        detail = await TicketService(session).escalate(ticket_id, request.body)
        return TicketActionResponse(ticket=detail, message="Ticket escalated")
    except TicketServiceError as exc:
        _raise_service_error(exc)
