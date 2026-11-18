from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_session
from backend.app.core.security import AuthenticatedUser, require_role
from backend.app.schemas.common import (
    Category,
    Role,
    Severity,
    TicketStatus,
)
from backend.app.schemas.tickets import (
    TicketCreateRequest,
    TicketCreateResponse,
    TicketDetail,
    TicketListResponse,
)
from backend.app.services.ticket_service import (
    TicketService,
    TicketServiceError,
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
