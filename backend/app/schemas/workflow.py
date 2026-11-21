from __future__ import annotations
from datetime import datetime

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.common import Category, Severity


class Classification(BaseModel):
    model_config = ConfigDict(use_enum_values=False)

    category: Category
    summary: str = Field(min_length=1)


class SeverityAssessment(BaseModel):
    severity: Severity
    reason: str = Field(min_length=1)


class Evidence(BaseModel):
    id: str
    title: str
    source: str
    snippet: str
    score: float = 0.0
    url: str = ""
    article_id: str = ""

    def as_dict(self) -> dict[str, str | float]:
        return {
            "id": self.id,
            "title": self.title,
            "source": self.source,
            "snippet": self.snippet,
            "score": self.score,
            "url": self.url,
            "article_id": self.article_id,
        }


class PreviousCase(BaseModel):
    ticket_number: str = ""
    number: str = ""
    subject: str = ""
    category: Category | None = None
    resolution: str = ""
    summary: str = ""
    similarity: float = 0.0


class CustomerContext(BaseModel):
    customer: dict[str, Any] = Field(default_factory=dict)
    subscription: dict[str, Any] | None = None
    subscriptions: list[dict[str, Any]] = Field(default_factory=list)
    workspaces: list[dict[str, Any]] = Field(default_factory=list)
    previous_tickets: list[dict[str, Any]] = Field(default_factory=list)
    memory_notes: list[str] = Field(default_factory=list)


class Diagnosis(BaseModel):
    probable_causes: list[str] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    checks: list[dict[str, Any]] = Field(default_factory=list)
    root_cause: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ActionProposal(BaseModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    approval_required: bool = False
    rationale: str = ""


class ResolutionPlan(BaseModel):
    summary: str = ""
    customer_reply: str = ""
    reply: str = ""
    internal_notes: str = ""
    steps: list[str] = Field(default_factory=list)
    actions: list[ActionProposal] = Field(default_factory=list)


class EscalationDecision(BaseModel):
    escalation_required: bool = False
    team: str | None = None
    reason: str = ""
    severity: Severity | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0


class WorkflowRunResponse(BaseModel):
    workflow_id: str


class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    status: str
    ticket_id: str
    thread_id: str | None = None
    state: dict[str, Any] = Field(default_factory=dict)


class WorkflowEventResponse(BaseModel):
    id: str
    ticket_id: str
    workflow_id: str | None = None
    event_type: str
    node_name: str | None = None
    payload: dict[str, Any] | None = None
    duration_ms: int | None = None
    token_usage: dict[str, Any] | None = None
    created_at: datetime


class WorkflowEventsResponse(BaseModel):
    items: list[WorkflowEventResponse] = Field(default_factory=list)


class ApprovalDecisionRequest(BaseModel):
    comment: str = Field(default="", max_length=2000)


class ApprovalResponse(BaseModel):
    id: str
    ticket_id: str
    workflow_id: str | None = None
    action_name: str
    action_args: dict[str, Any] | None = None
    status: str
    decided_by: str | None = None
    reason: str | None = None
    decided_at: datetime | None = None
    workflow: WorkflowStatusResponse | None = None


class StructuredLLMResult(BaseModel):
    output: object
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    duration_ms: float = 0.0


class EscalationResponse(BaseModel):
    id: str
    ticket_id: str
    team: str
    reason: str
    status: str
    created_at: datetime
    updated_at: datetime


class EscalationListResponse(BaseModel):
    items: list[EscalationResponse] = Field(default_factory=list)


__all__ = [
    "ActionProposal",
    "ApprovalDecisionRequest",
    "ApprovalResponse",
    "Classification",
    "CustomerContext",
    "Diagnosis",
    "EscalationDecision",
    "EscalationResponse",
    "EscalationListResponse",
    "Evidence",
    "PreviousCase",
    "ResolutionPlan",
    "SeverityAssessment",
    "StructuredLLMResult",
    "TokenUsage",
    "WorkflowRunResponse",
    "WorkflowStatusResponse",
    "WorkflowEventResponse",
    "WorkflowEventsResponse",
]
