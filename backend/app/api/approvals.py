from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_session
from backend.app.core.security import AuthenticatedUser, require_role
from backend.app.schemas.common import Role
from backend.app.schemas.workflow import ApprovalDecisionRequest, ApprovalResponse
from backend.app.services.approval_service import (
    ApprovalService,
    ApprovalServiceError,
)

router = APIRouter(prefix="/approvals", tags=["approvals"])

ViewerUser = Annotated[AuthenticatedUser, Depends(require_role(Role.VIEWER))]
AgentUser = Annotated[AuthenticatedUser, Depends(require_role(Role.AGENT))]


def _raise_service_error(exc: ApprovalServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: str,
    _current_user: ViewerUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> ApprovalResponse:
    try:
        return await ApprovalService(session).get(approval_id)
    except ApprovalServiceError as exc:
        _raise_service_error(exc)


@router.post("/{approval_id}/approve", response_model=ApprovalResponse)
async def approve_approval(
    approval_id: str,
    request: ApprovalDecisionRequest,
    current_user: AgentUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> ApprovalResponse:
    try:
        return await ApprovalService(session).approve(
            approval_id,
            request,
            actor_id=current_user.id,
        )
    except ApprovalServiceError as exc:
        _raise_service_error(exc)


@router.post("/{approval_id}/reject", response_model=ApprovalResponse)
async def reject_approval(
    approval_id: str,
    request: ApprovalDecisionRequest,
    current_user: AgentUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> ApprovalResponse:
    try:
        return await ApprovalService(session).reject(
            approval_id,
            request,
            actor_id=current_user.id,
        )
    except ApprovalServiceError as exc:
        _raise_service_error(exc)


__all__ = ["router"]
