from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agents.prompts import (
    SECURITY_PREAMBLE,
    SUPERVISOR_CLASSIFICATION_PROMPT,
    SUPERVISOR_SEVERITY_PROMPT,
)
from agents.rules import (
    rule_category,
    rule_severity,
    scan_for_injection,
    wrap_untrusted,
)
from backend.app.core.llm import LLMUsage, call_structured
from backend.app.schemas.common import Category
from backend.app.schemas.workflow import Classification, SeverityAssessment


class SupervisorAgent:
    """Understand and triage a support ticket."""

    def __init__(self, llm: Any | None = None) -> None:
        self.llm = llm
        self.last_injection_detected = False
        self.last_usage = LLMUsage()
        self.last_duration_ms = 0

    async def understand(
        self,
        ticket: Mapping[str, Any] | str | None = None,
        body: str | None = None,
        *,
        subject: str | None = None,
        text: str | None = None,
    ) -> Classification:
        source = text if text is not None else subject if subject is not None else ticket
        ticket_text = self._ticket_text(source or "", body)
        self.last_injection_detected = scan_for_injection(ticket_text)

        prompt = (
            f"{SECURITY_PREAMBLE}\n\n"
            f"{SUPERVISOR_CLASSIFICATION_PROMPT}\n\n"
            f"{wrap_untrusted(ticket_text)}"
        )
        classification, usage, duration_ms = await call_structured(
            Classification,
            prompt,
            llm=self.llm,
            retries=2,
        )
        self.last_usage = usage
        self.last_duration_ms = duration_ms

        policy_category = rule_category(ticket_text, classification.category)
        try:
            category = Category(str(policy_category).lower())
        except (TypeError, ValueError):
            category = Category.OTHER

        summary = " ".join(classification.summary.split())
        if not summary:
            summary = self._one_line_summary(ticket_text)

        return Classification(category=category, summary=summary[:500])

    async def assess_severity(
        self,
        ticket: Mapping[str, Any] | str | None = None,
        body: str | None = None,
        category: Category | str | None = None,
        *,
        subject: str | None = None,
        text: str | None = None,
    ) -> SeverityAssessment:
        source = text if text is not None else subject if subject is not None else ticket
        ticket_text = self._ticket_text(source or "", body)
        self.last_injection_detected = scan_for_injection(ticket_text)

        prompt = (
            f"{SECURITY_PREAMBLE}\n\n"
            f"{SUPERVISOR_SEVERITY_PROMPT}\n\n"
            f"{wrap_untrusted(ticket_text)}"
        )
        assessment, usage, duration_ms = await call_structured(
            SeverityAssessment,
            prompt,
            llm=self.llm,
            retries=2,
        )
        self.last_usage = usage
        self.last_duration_ms = duration_ms

        severity = rule_severity(ticket_text, assessment.severity, category)
        reason = " ".join(assessment.reason.split())
        if not reason:
            reason = f"Policy and ticket context indicate {severity.value} severity."

        return SeverityAssessment(severity=severity, reason=reason[:500])

    async def ticket_summary(
        self,
        ticket: Mapping[str, Any] | str,
        classification: Classification | None = None,
        severity: SeverityAssessment | None = None,
    ) -> str:
        del ticket
        parts: list[str] = []
        if classification is not None:
            parts.append(
                f"{classification.category.value}: {classification.summary}"
            )
        if severity is not None:
            parts.append(
                f"{severity.severity.value} severity - {severity.reason}"
            )
        summary = " ".join(parts)
        return " ".join(summary.split())[:1000]

    async def run(
        self,
        ticket: Mapping[str, Any] | str,
        body: str | None = None,
    ) -> tuple[Classification, SeverityAssessment, bool, LLMUsage, int]:
        classification = await self.understand(ticket, body)
        severity = await self.assess_severity(ticket, body, classification.category)
        return (
            classification,
            severity,
            self.last_injection_detected,
            LLMUsage(),
            0,
        )

    @staticmethod
    def _ticket_text(
        ticket: Mapping[str, Any] | str,
        body: str | None,
    ) -> str:
        if isinstance(ticket, Mapping):
            subject = str(ticket.get("subject", "")).strip()
            ticket_body = str(ticket.get("body", "")).strip()
            text = " ".join(part for part in (subject, ticket_body) if part)
            return text or str(ticket)
        text = str(ticket).strip()
        if body and body.strip():
            return f"{text}\n{body.strip()}"
        return text

    @staticmethod
    def _one_line_summary(text: str) -> str:
        first = " ".join(text.split())
        return first[:500] if first else "Support ticket requires classification."


__all__ = ["SupervisorAgent"]
