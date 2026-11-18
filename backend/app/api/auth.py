from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from backend.app.core.database import get_session
from backend.app.core.security import AuthenticatedUser, get_current_user
from backend.app.repositories.identity import ProfileRepository
from backend.app.schemas.auth import (
    AuthProfile,
    DemoTokenRequest,
    DemoTokenResponse,
    MeResponse,
)
from backend.app.schemas.common import Role

router = APIRouter(prefix="/auth", tags=["auth"])

DEMO_TOKEN_LIFETIME_SECONDS = 8 * 60 * 60


def _auth_profile(profile) -> AuthProfile:
    return AuthProfile(
        id=profile.id,
        email=profile.email,
        full_name=profile.full_name,
        role=profile.role,
    )


@router.post("/demo-token", response_model=DemoTokenResponse)
async def issue_demo_token(
    request: DemoTokenRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> DemoTokenResponse:
    settings = get_settings()
    if not settings.demo_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo authentication is disabled",
        )

    profile = await ProfileRepository(session).get_by_email(request.email.strip().lower())
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo user not found",
        )

    now = datetime.now(UTC)
    expires = now + timedelta(seconds=DEMO_TOKEN_LIFETIME_SECONDS)
    payload = {
        "sub": profile.id,
        "email": profile.email,
        "role": Role(profile.role).value,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    token = jwt.encode(
        payload,
        settings.effective_jwt_secret,
        algorithm="HS256",
    )
    user = _auth_profile(profile)
    return DemoTokenResponse(
        access_token=token,
        expires_in=DEMO_TOKEN_LIFETIME_SECONDS,
        user=user,
    )


@router.get("/me", response_model=MeResponse)
async def get_me(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> MeResponse:
    repository = ProfileRepository(session)
    profile = await repository.get_by_id(current_user.id)
    if profile is None:
        profile = await repository.get_by_email(current_user.email)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Authenticated profile not found",
        )

    return MeResponse(
        id=profile.id,
        email=profile.email,
        full_name=profile.full_name,
        role=profile.role,
    )
