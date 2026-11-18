from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.tickets import TicketSummary


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    customer_id: str
    plan: str
    status: str
    seats: int = 0
    monthly_price: float | None = None
    created_at: datetime
    updated_at: datetime


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    customer_id: str
    name: str
    status: str
    settings: dict | None = None
    created_at: datetime
    updated_at: datetime


class CustomerMemoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    content: str
    source_ticket_id: str | None = None
    created_at: datetime


class CustomerSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    company: str | None = None
    plan: str | None = None


class CustomerDetail(CustomerSummary):
    subscriptions: list[SubscriptionResponse] = Field(default_factory=list)
    workspaces: list[WorkspaceResponse] = Field(default_factory=list)
    tickets: list[TicketSummary] = Field(default_factory=list)
    memory: list[CustomerMemoryResponse] = Field(default_factory=list)


class CustomerResponse(CustomerSummary):
    pass


class CustomerListResponse(BaseModel):
    items: list[CustomerSummary] = Field(default_factory=list)


class CustomerTicketHistoryResponse(BaseModel):
    items: list[TicketSummary] = Field(default_factory=list)
