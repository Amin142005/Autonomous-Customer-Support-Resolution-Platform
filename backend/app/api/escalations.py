from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_session
from backend.app.core.security import AuthenticatedUser, require_role
from backend.app.schemas.common import Role
from backend.app.schemas.workflow import EscalationListResponse, EscalationResponse
from backend.app.services.escalation_service import (
    EscalationService,
    EscalationServiceError,
)

router = APIRouter(prefix="/escalations", tags=["escalations"])

ViewerUser = Annotated[AuthenticatedUser, Depends(require_role(Role.VIEWER))]


def _raise_service_error(exc: EscalationServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("", response_model=EscalationListResponse)
async def list_escalations(
    _current_user: ViewerUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> EscalationListResponse:
    try:
        return await EscalationService(session).list_open(limit=limit, offset=offset)
    except EscalationServiceError as exc:
        _raise_service_error(exc)


@router.get("/{escalation_id}", response_model=EscalationResponse)
async def get_escalation(
    escalation_id: str,
    _current_user: ViewerUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> EscalationResponse:
    try:
        return await EscalationService(session).get(escalation_id)
    except EscalationServiceError as exc:
        _raise_service_error(exc)


__all__ = ["router"]
