from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Any

from agents.prompts import SECURITY_PREAMBLE, TROUBLESHOOTING_PROMPT
from agents.rules import wrap_untrusted
from backend.app.core.llm import LLMUsage, call_structured
from backend.app.schemas.common import Category
from backend.app.schemas.workflow import CustomerContext, Diagnosis, Evidence
from backend.app.tools.registry import ToolRegistry
from backend.app.tools.result import ToolResult


_CATEGORY_PLAYBOOKS: dict[Category, tuple[list[str], list[str], str]] = {
    Category.LOGIN_ISSUE: (
        ["Identity-provider or SSO configuration mismatch", "MFA or session state is stale"],
        ["Check the identity service status.", "Verify SSO and MFA configuration.", "Reproduce the login and confirm whether the issue affects one user or the whole team."],
        "identity",
    ),
    Category.API_FAILURE: (
        ["Rate limits or quota limits are being exceeded", "API credentials or request configuration are invalid"],
        ["Check the API service status.", "Inspect the returned status code and retry-after value.", "Verify credentials and request parameters."],
        "api",
    ),
    Category.STORAGE_QUOTA: (
        ["The workspace has exceeded its storage limit", "An upload contains an unsupported or incomplete file"],
        ["Check the storage service status.", "Confirm workspace usage and quota limits.", "Retry a small upload and verify file size and format."],
        "storage",
    ),
    Category.INTEGRATION: (
        ["The external integration credentials expired", "The integration configuration changed"],
        ["Check the integration-related service status.", "Verify the integration connection and recent authorization changes.", "Reconnect the integration and reproduce one event."],
        "collaboration",
    ),
    Category.BILLING: (
        ["The subscription seat count differs from the invoice", "A payment or billing-event synchronization delay exists"],
        ["Check the billing service status.", "Compare active seats with the subscription and invoice.", "Confirm whether the reported charge matches the billing record."],
        "billing",
    ),
    Category.WORKSPACE_PERMISSIONS: (
        ["Workspace sharing permissions are misconfigured", "The external collaborator domain or role is not allowed"],
        ["Check the collaboration service status.", "Verify workspace sharing settings and the recipient domain.", "Test sharing with an internal and external collaborator."],
        "collaboration",
    ),
    Category.ACCOUNT: (
        ["An account or workspace configuration change blocked access", "The requested account action has policy dependencies"],
        ["Check the relevant account service status.", "Verify workspace ownership and account policy requirements.", "Confirm the exact requested account change before acting."],
        "collaboration",
    ),
    Category.SECURITY: (
        ["A login or session may be compromised", "Suspicious activity came from an unknown or automated source"],
        ["Check identity service status.", "Review recent sessions and security events.", "Require a secure account recovery or escalation step before sensitive access."],
        "identity",
    ),
    Category.FEATURE_REQUEST: (
        ["The requested capability is not enabled in the current product plan", "The behavior is limited by an existing product configuration"],
        ["Confirm the requested behavior against the current product configuration.", "Check whether an existing setting or supported workflow applies."],
        "collaboration",
    ),
    Category.OTHER: (
        ["The reported symptom does not match a known product failure", "More diagnostic information is required"],
        ["Check the relevant service status.", "Reproduce the issue and collect the exact symptoms.", "Verify configuration and request details before proposing a fix."],
        "collaboration",
    ),
}


class TroubleshootingAgent:
    """Diagnose a support issue using service state, evidence, and an LLM."""

    def __init__(self, registry: ToolRegistry | Any, llm: Any | None = None) -> None:
        self.registry = registry
        self.llm = llm
        self.last_usage = LLMUsage()
        self.last_duration_ms = 0

    async def run(
        self,
        ticket: Mapping[str, Any] | str | None = None,
        body: str | None = None,
        *,
        category: Category | str | None = None,
        evidence: Sequence[Evidence | Mapping[str, Any]] | None = None,
        customer_context: CustomerContext | Mapping[str, Any] | None = None,
        subject: str | None = None,
        text: str | None = None,
    ) -> Diagnosis:
        category_value = self._category(category)
        ticket_text = self._ticket_text(ticket, body, subject, text)
        probable_causes, steps, service_name = _CATEGORY_PLAYBOOKS[category_value]

        status = await self._check_status(service_name)
        checks: list[dict[str, Any]] = []
        if status:
            checks.append(status)

        evidence_lines = self._evidence_lines(evidence)
        context_lines = self._context_lines(customer_context)
        status_lines = [f"Service status: {status}"] if status else []
        prompt = "\n".join(
            line
            for line in (
                SECURITY_PREAMBLE,
                TROUBLESHOOTING_PROMPT,
                f"Category: {category_value.value}",
                f"Ticket: {wrap_untrusted(ticket_text)}",
                *evidence_lines,
                *context_lines,
                *status_lines,
            )
            if line
        )

        model_diagnosis, usage, duration_ms = await call_structured(
            Diagnosis,
            prompt,
            llm=self.llm,
            retries=2,
        )
        self.last_usage = usage
        self.last_duration_ms = duration_ms

        merged_causes = self._merge(probable_causes, model_diagnosis.probable_causes, model_diagnosis.hypotheses)
        merged_steps = self._merge(list(steps), model_diagnosis.steps)

        numbered_steps = [
            f"{index}. {step}" if not re.match(r"^\d+[.)]\s", step) else step
            for index, step in enumerate(merged_steps, start=1)
        ]

        if model_diagnosis.root_cause:
            root_cause = " ".join(model_diagnosis.root_cause.split())[:500]
        elif len(merged_causes) == 1:
            root_cause = merged_causes[0]
        else:
            root_cause = None

        confidence = max(0.0, min(1.0, float(model_diagnosis.confidence)))
        if status and status.get("state") in {"degraded", "outage"}:
            confidence = max(confidence, 0.75)

        return Diagnosis(
            probable_causes=merged_causes,
            hypotheses=list(dict.fromkeys(model_diagnosis.hypotheses + probable_causes)),
            steps=numbered_steps,
            checks=checks,
            root_cause=root_cause,
            confidence=confidence,
        )

    async def _check_status(self, service_name: str) -> dict[str, Any] | None:
        if not hasattr(self.registry, "execute"):
            return None
        try:
            result: ToolResult | object = await self.registry.execute(
                "check_service_status",
                {"service_name": service_name},
            )
        except Exception:  # noqa: BLE001
            return None

        if isinstance(result, ToolResult):
            if not result.ok:
                return None
            output = result.output
        elif isinstance(result, Mapping):
            if result.get("ok") is False:
                return None
            output = result.get("output", result)
        else:
            output = result

        if not isinstance(output, Mapping):
            return None
        return {
            "service_name": str(output.get("service_name", service_name)),
            "state": str(output.get("state", "unknown")),
            "summary": str(output.get("summary", "")),
            "incident_ids": list(output.get("incident_ids", [])),
        }

    @staticmethod
    def _category(category: Category | str | None) -> Category:
        if isinstance(category, Category):
            return category
        if isinstance(category, str):
            try:
                return Category(category.lower())
            except ValueError:
                pass
        return Category.OTHER

    @staticmethod
    def _ticket_text(
        ticket: Mapping[str, Any] | str | None,
        body: str | None,
        subject: str | None,
        text: str | None,
    ) -> str:
        if text is not None:
            source = text
        elif subject is not None:
            source = subject
        elif isinstance(ticket, Mapping):
            subject_text = str(ticket.get("subject", "")).strip()
            body_text = str(ticket.get("body", body or "")).strip()
            source = " ".join(part for part in (subject_text, body_text) if part)
        else:
            source = str(ticket or "")
        if body and isinstance(ticket, str) and body.strip():
            source = f"{source}\n{body.strip()}"
        return source.strip() or "Support ticket requires diagnosis."

    @staticmethod
    def _evidence_lines(evidence: Sequence[Evidence | Mapping[str, Any]] | None) -> list[str]:
        if not evidence:
            return []
        lines = ["Evidence:"]
        for item in evidence[:5]:
            if isinstance(item, Evidence):
                title = item.title
                snippet = item.snippet
                source = item.source
            elif isinstance(item, Mapping):
                title = str(item.get("title", ""))
                snippet = str(item.get("snippet", ""))
                source = str(item.get("source", ""))
            else:
                continue
            content = " - ".join(part for part in (title, snippet, source) if part)
            if content:
                lines.append(content)
        return lines

    @staticmethod
    def _context_lines(customer_context: CustomerContext | Mapping[str, Any] | None) -> list[str]:
        if customer_context is None:
            return []
        if isinstance(customer_context, CustomerContext):
            data = customer_context.model_dump()
        else:
            data = dict(customer_context)
        subscription = data.get("subscription")
        memory_notes = data.get("memory_notes", [])
        lines: list[str] = []
        if isinstance(subscription, Mapping):
            lines.append(f"Subscription: {dict(subscription)}")
        if isinstance(memory_notes, Sequence) and not isinstance(memory_notes, (str, bytes)):
            for note in memory_notes[:5]:
                if isinstance(note, str) and note.strip():
                    lines.append(f"Memory note: {note.strip()}")
        return lines

    @staticmethod
    def _merge(*groups: Sequence[str]) -> list[str]:
        merged: list[str] = []
        for group in groups:
            for value in group:
                cleaned = " ".join(str(value).split())
                if cleaned and cleaned not in merged:
                    merged.append(cleaned)
        return merged


__all__ = ["TroubleshootingAgent"]
