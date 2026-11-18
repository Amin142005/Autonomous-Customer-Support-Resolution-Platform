from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from backend.app.schemas.common import (
    Category,
    Channel,
    Severity,
    TicketStatus,
)


class TicketCustomerInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    plan: str | None = Field(default=None, max_length=50)


class TicketCreateRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1)
    channel: Channel
    customer_id: str | None = None
    customer: TicketCustomerInput | None = None
    workspace_id: str | None = None

    @model_validator(mode="after")
    def require_one_customer_source(self) -> TicketCreateRequest:
        if (self.customer_id is None) == (self.customer is None):
            raise ValueError(
                "Provide exactly one of customer_id or customer"
            )
        return self


class TicketCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1)
    channel: Channel
    customer_id: str | None = None
    customer: TicketCustomerInput | None = None
    workspace_id: str | None = None

    @model_validator(mode="after")
    def require_one_customer_source(self) -> TicketCreate:
        if (self.customer_id is None) == (self.customer is None):
            raise ValueError(
                "Provide exactly one of customer_id or customer"
            )
        return self


class TicketCustomerSummary(BaseModel):
    id: str
    name: str
    email: str
    company: str | None = None
    plan: str | None = None


class TicketWorkspaceSummary(BaseModel):
    id: str
    name: str
    status: str


class TicketMessageResponse(BaseModel):
    id: str
    ticket_id: str
    author_type: str
    author_id: str | None = None
    body: str
    created_at: datetime


class TicketSummary(BaseModel):
    id: str
    number: str
    customer_id: str
    workspace_id: str | None = None
    subject: str
    body: str
    channel: Channel
    category: Category | None = None
    severity: Severity | None = None
    status: TicketStatus
    summary: str | None = None
    assignee_id: str | None = None
    created_at: datetime
    updated_at: datetime


class TicketDetail(TicketSummary):
    customer: TicketCustomerSummary
    workspace: TicketWorkspaceSummary | None = None
    messages: list[TicketMessageResponse] = Field(default_factory=list)


class TicketResponse(TicketSummary):
    pass


class TicketCreateResponse(BaseModel):
    ticket: TicketDetail


class TicketListResponse(BaseModel):
    items: list[TicketSummary] = Field(default_factory=list)

