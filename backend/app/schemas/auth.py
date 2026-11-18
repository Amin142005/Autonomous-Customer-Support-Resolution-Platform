from __future__ import annotations

from pydantic import BaseModel

from backend.app.schemas.common import Role


class DemoTokenRequest(BaseModel):
    email: str


class AuthUser(BaseModel):
    id: str
    email: str
    role: Role


class AuthProfile(AuthUser):
    full_name: str


class DemoTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 28800
    user: AuthProfile


class MeResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: Role

