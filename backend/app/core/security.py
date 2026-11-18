from __future__ import annotations

from collections.abc import Callable
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from backend.app.core.config import get_settings
from backend.app.schemas.common import Role

ROLE_RANK: dict[Role, int] = {
    Role.VIEWER: 1,
    Role.AGENT: 2,
    Role.ADMIN: 3,
}

ROLE_RANK_BY_NAME: dict[str, int] = {
    role.value: rank for role, rank in ROLE_RANK.items()
}
ROLE_LEVELS = ROLE_RANK_BY_NAME

_bearer_scheme = HTTPBearer(auto_error=False)


class AuthenticatedUser(BaseModel):
    id: str
    email: str
    role: Role


CurrentUser = AuthenticatedUser


def _claim_role(payload: dict[str, Any]) -> str | None:
    role = payload.get("role")
    if isinstance(role, str):
        return role
    role = payload.get("user_role")
    if isinstance(role, str):
        return role

    app_metadata = payload.get("app_metadata")
    if isinstance(app_metadata, dict):
        role = app_metadata.get("role")
        if isinstance(role, str):
            return role

    user_metadata = payload.get("user_metadata")
    if isinstance(user_metadata, dict):
        role = user_metadata.get("role")
        if isinstance(role, str):
            return role
    return None


def decode_jwt(token: str, secret: str | None = None) -> dict[str, Any]:
    secret = secret or get_settings().effective_jwt_secret
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is not configured",
        )

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"require": ["sub", "exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        ) from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )
    return payload


decode_access_token = decode_jwt
verify_jwt = decode_jwt


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),  # noqa: B008
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer authentication",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_jwt(credentials.credentials)
    role_name = _claim_role(payload)
    try:
        role = Role(role_name)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has an invalid role",
        ) from exc

    user_id = payload.get("sub")
    email = payload.get("email")
    if not isinstance(user_id, str) or not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has an invalid subject",
        )
    if not isinstance(email, str) or not email:
        email = ""

    return AuthenticatedUser(id=user_id, email=email, role=role)


def require_role(minimum_role: Role | str) -> Callable[..., AuthenticatedUser]:
    try:
        required_role = Role(minimum_role)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Unknown CloudDesk role: {minimum_role}") from exc
    required_rank = ROLE_RANK[required_role]

    async def dependency(
        current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
    ) -> AuthenticatedUser:
        if ROLE_RANK[current_user.role] < required_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role permissions",
            )
        return current_user

    return dependency
