from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_session
from backend.app.core.security import AuthenticatedUser, require_role
from backend.app.schemas.common import Role
from backend.app.schemas.customers import (
    CustomerDetail,
    CustomerListResponse,
    CustomerTicketHistoryResponse,
)
from backend.app.services.customer_service import (
    CustomerService,
    CustomerServiceError,
)

router = APIRouter(prefix="/customers", tags=["customers"])

ViewerUser = Annotated[AuthenticatedUser, Depends(require_role(Role.VIEWER))]


def _raise_service_error(exc: CustomerServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("", response_model=CustomerListResponse)
async def list_customers(
    _current_user: ViewerUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> CustomerListResponse:
    try:
        return await CustomerService(session).list(limit=limit, offset=offset)
    except CustomerServiceError as exc:
        _raise_service_error(exc)


@router.get("/{customer_id}", response_model=CustomerDetail)
async def get_customer(
    customer_id: str,
    _current_user: ViewerUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> CustomerDetail:
    try:
        return await CustomerService(session).get_detail(customer_id)
    except CustomerServiceError as exc:
        _raise_service_error(exc)


@router.get("/{customer_id}/tickets", response_model=CustomerTicketHistoryResponse)
async def get_customer_tickets(
    customer_id: str,
    _current_user: ViewerUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> CustomerTicketHistoryResponse:
    try:
        return await CustomerService(session).get_ticket_history(
            customer_id,
            limit=limit,
            offset=offset,
        )
    except CustomerServiceError as exc:
        _raise_service_error(exc)
