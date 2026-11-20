from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from agents.prompts import ESCALATION_PROMPT, SECURITY_PREAMBLE
from agents.rules import (
    matching_escalation_rules,
    severity_for_escalation_matches,
    wrap_untrusted,
)
from backend.app.core.llm import LLMUsage, call_structured
from backend.app.schemas.common import Category, Severity
from backend.app.schemas.workflow import EscalationDecision, Evidence


class EscalationAgent:
    """Combine deterministic policy escalation rules with cautious LLM judgement."""

    def __init__(self, llm: Any | None = None) -> None:
        self.llm = llm
        self.last_usage = LLMUsage()
        self.last_duration_ms = 0

    async def run(
        self,
        ticket: Mapping[str, Any] | str,
        *,
        category: Category | str | None = None,
        severity: Severity | str | None = None,
        evidence: Sequence[Evidence | Mapping[str, Any]] | None = None,
        plan_name: str | None = None,
    ) -> EscalationDecision:
        ticket_text = self._ticket_text(ticket)
        policy_matches = matching_escalation_rules(ticket_text, plan_name)

        if policy_matches:
            teams = list(dict.fromkeys(str(match["team"]) for match in policy_matches))
            team = teams[0] if len(teams) == 1 else " + ".join(teams)
            policy_severity = severity_for_escalation_matches(policy_matches)
            return EscalationDecision(
                escalation_required=True,
                team=team,
                reason=self._policy_reason(policy_matches),
                severity=policy_severity,
                confidence=1.0,
            )

        prompt = "\n".join(
            (
                SECURITY_PREAMBLE,
                ESCALATION_PROMPT,
                f"Category: {self._category_text(category)}",
                f"Severity: {self._severity_text(severity)}",
                f"Ticket: {wrap_untrusted(ticket_text)}",
                *self._evidence_lines(evidence),
            )
        )

        judgement, usage, duration_ms = await call_structured(
            EscalationDecision,
            prompt,
            llm=self.llm,
            retries=2,
        )
        self.last_usage = usage
        self.last_duration_ms = duration_ms

        confidence = max(0.0, min(1.0, float(judgement.confidence)))
        model_severity = self._coerce_severity(judgement.severity) or self._coerce_severity(severity) or Severity.LOW

        if judgement.escalation_required and confidence >= 0.6 and model_severity in (Severity.HIGH, Severity.CRITICAL):
            team = judgement.team.strip() if judgement.team and judgement.team.strip() else None
            reason = judgement.reason.strip() or "The issue requires specialist review."
            return EscalationDecision(
                escalation_required=True,
                team=team,
                reason=reason[:500],
                severity=model_severity,
                confidence=confidence,
            )

        return EscalationDecision(
            escalation_required=False,
            team=None,
            reason="No deterministic policy rule or sufficiently confident specialist escalation was identified.",
            severity=model_severity,
            confidence=confidence,
        )

    @staticmethod
    def _ticket_text(ticket: Mapping[str, Any] | str) -> str:
        if isinstance(ticket, Mapping):
            subject = str(ticket.get("subject", "")).strip()
            body = str(ticket.get("body", "")).strip()
            return " ".join(part for part in (subject, body) if part) or str(ticket)
        return str(ticket).strip()

    @staticmethod
    def _category_text(category: Category | str | None) -> str:
        if isinstance(category, Category):
            return category.value
        return str(category or "other")

    @staticmethod
    def _severity_text(severity: Severity | str | None) -> str:
        if isinstance(severity, Severity):
            return severity.value
        return str(severity or "low")

    @staticmethod
    def _coerce_severity(value: Severity | str | None) -> Severity | None:
        if isinstance(value, Severity):
            return value
        if isinstance(value, str):
            try:
                return Severity(value.strip().lower())
            except ValueError:
                return None
        return None

    @staticmethod
    def _policy_reason(matches: list[dict[str, object]]) -> str:
        rules = list(dict.fromkeys(str(match["rule"]) for match in matches))
        teams = list(dict.fromkeys(str(match["team"]) for match in matches))
        return f"Deterministic escalation policy matched {', '.join(rules)}; route to {', '.join(teams)}."

    @staticmethod
    def _evidence_lines(evidence: Sequence[Evidence | Mapping[str, Any]] | None) -> list[str]:
        if not evidence:
            return []
        lines = ["Evidence:"]
        for item in evidence[:5]:
            if isinstance(item, Evidence):
                title, snippet, source = item.title, item.snippet, item.source
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


__all__ = ["EscalationAgent"]
