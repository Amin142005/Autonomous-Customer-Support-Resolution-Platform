from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Any

from agents.prompts import RESOLUTION_PROMPT, SECURITY_PREAMBLE
from agents.rules import wrap_untrusted
from backend.app.core.guardrails import validate_customer_output
from backend.app.core.llm import LLMUsage, call_structured
from backend.app.schemas.common import Category
from backend.app.schemas.workflow import (
    ActionProposal,
    CustomerContext,
    Diagnosis,
    Evidence,
    ResolutionPlan,
)


class ResolutionAgent:
    """Create a grounded resolution plan and deterministic action proposals."""

    def __init__(self, llm: Any | None = None) -> None:
        self.llm = llm
        self.last_usage = LLMUsage()
        self.last_duration_ms = 0

    async def run(
        self,
        ticket: Mapping[str, Any] | str,
        diagnosis: Diagnosis | Mapping[str, Any] | None = None,
        *,
        category: Category | str | None = None,
        evidence: Sequence[Evidence | Mapping[str, Any]] | None = None,
        customer_context: CustomerContext | Mapping[str, Any] | None = None,
        severity: Any | None = None,
    ) -> ResolutionPlan:
        del severity
        category_value = self._category(category, ticket)
        ticket_text = self._ticket_text(ticket)
        diagnosis_model = self._diagnosis(diagnosis)

        evidence_lines = self._evidence_lines(evidence)
        diagnosis_lines = [
            f"Probable causes: {', '.join(diagnosis_model.probable_causes)}",
            f"Troubleshooting steps: {' | '.join(diagnosis_model.steps)}",
        ]
        if diagnosis_model.root_cause:
            diagnosis_lines.append(f"Root cause: {diagnosis_model.root_cause}")

        prompt = "\n".join(
            (
                SECURITY_PREAMBLE,
                RESOLUTION_PROMPT,
                f"Category: {category_value.value}",
                f"Ticket: {wrap_untrusted(ticket_text)}",
                *diagnosis_lines,
                *evidence_lines,
            )
        )

        plan, usage, duration_ms = await call_structured(
            ResolutionPlan,
            prompt,
            llm=self.llm,
            retries=2,
        )
        self.last_usage = usage
        self.last_duration_ms = duration_ms

        grounded_reply = self._ground_response(plan.customer_reply or plan.reply, diagnosis_model)
        safe_reply = grounded_reply.strip()
        allowed_id, allowed_name = self._allowed_customer(customer_context)
        is_valid, _ = validate_customer_output(
            safe_reply,
            allowed_customer_id=allowed_id,
            allowed_customer_name=allowed_name,
        )
        if not is_valid:
            safe_reply = self._safe_fallback(diagnosis_model)

        steps = self._merge(diagnosis_model.steps, plan.steps)
        actions = self.plan_actions(
            ticket,
            category_value,
            diagnosis_model,
            customer_context,
        )

        summary = " ".join(plan.summary.split()).strip() or "Apply the verified troubleshooting steps."
        internal_notes = " ".join(plan.internal_notes.split()).strip()
        if not internal_notes:
            internal_notes = "Follow the approved support playbook and preserve the evidence trail."

        return ResolutionPlan(
            summary=summary[:1000],
            customer_reply=safe_reply,
            reply=safe_reply,
            internal_notes=internal_notes[:2000],
            steps=steps,
            actions=actions,
        )

    def plan_actions(
        self,
        ticket: Mapping[str, Any] | str,
        category: Category | str | None = None,
        diagnosis: Diagnosis | Mapping[str, Any] | None = None,
        customer_context: CustomerContext | Mapping[str, Any] | None = None,
    ) -> list[ActionProposal]:
        del diagnosis
        category_value = self._category(category, ticket)
        ticket_text = self._ticket_text(ticket).casefold()
        ticket_id = self._ticket_id(ticket)
        context = self._context_dict(customer_context)
        customer_id = str(context.get("customer", {}).get("id", "")) if isinstance(context.get("customer"), Mapping) else ""

        actions: list[ActionProposal] = []
        if ticket_id:
            actions.append(ActionProposal(
                tool="update_ticket",
                arguments={"ticket_id": ticket_id, "status": "in_progress"},
                approval_required=False,
                rationale="Record investigation progress on the support ticket.",
            ))

        if category_value == Category.BILLING or any(term in ticket_text for term in ("refund", "charged", "payment dispute", "unauthorized charge")):
            amount = self._refund_amount(ticket, context)
            if amount is not None and customer_id:
                actions.append(ActionProposal(
                    tool="create_refund_request",
                    arguments={"customer_id": customer_id, "amount": amount, "reason": "Approved simulated refund for support resolution"},
                    approval_required=True,
                    rationale="A refund changes billing state and requires human approval.",
                ))

        if any(term in ticket_text for term in ("reset setting", "reset demo setting", "restore default")):
            workspace_id = self._workspace_id(context)
            if workspace_id:
                actions.append(ActionProposal(
                    tool="reset_demo_setting",
                    arguments={"workspace_id": workspace_id, "setting_name": "default", "default_value": True},
                    approval_required=True,
                    rationale="Workspace setting changes require human approval.",
                ))

        return actions

    @staticmethod
    def _ground_response(reply: str, diagnosis: Diagnosis) -> str:
        text = " ".join(reply.split()).strip()
        if not text:
            text = "Please try the recommended support steps and contact us if the issue continues."

        missing_steps = [
            step
            for step in diagnosis.steps[:3]
            if step.casefold() not in text.casefold()
        ]
        if missing_steps:
            cleaned = [re.sub(r"^\d+[.)]\s*", "", step).strip() for step in missing_steps]
            cleaned = [step for step in cleaned if step]
            if cleaned:
                text = f"{text.rstrip('.')} Please try: {'; '.join(cleaned)}."
        return text

    @staticmethod
    def _safe_fallback(diagnosis: Diagnosis) -> str:
        if diagnosis.steps:
            return f"Please try the following steps: {'; '.join(diagnosis.steps[:3])}."
        return "Please verify the relevant service configuration and contact support if the issue continues."

    @staticmethod
    def _category(category: Category | str | None, ticket: Mapping[str, Any] | str) -> Category:
        if isinstance(category, Category):
            return category
        if isinstance(category, str):
            try:
                return Category(category.lower())
            except ValueError:
                pass
        if isinstance(ticket, Mapping):
            raw = ticket.get("category")
            if isinstance(raw, str):
                try:
                    return Category(raw.lower())
                except ValueError:
                    pass
        return Category.OTHER

    @staticmethod
    def _ticket_text(ticket: Mapping[str, Any] | str) -> str:
        if isinstance(ticket, Mapping):
            subject = str(ticket.get("subject", "")).strip()
            body = str(ticket.get("body", "")).strip()
            return " ".join(part for part in (subject, body) if part) or str(ticket)
        return str(ticket).strip()

    @staticmethod
    def _ticket_id(ticket: Mapping[str, Any] | str) -> str:
        if isinstance(ticket, Mapping):
            return str(ticket.get("id") or ticket.get("ticket_id") or ticket.get("number") or "")
        return ""

    @staticmethod
    def _context_dict(context: CustomerContext | Mapping[str, Any] | None) -> dict[str, Any]:
        if isinstance(context, CustomerContext):
            return context.model_dump()
        if isinstance(context, Mapping):
            return dict(context)
        return {}

    @staticmethod
    def _allowed_customer(context: CustomerContext | Mapping[str, Any] | None) -> tuple[str | None, str | None]:
        data = ResolutionAgent._context_dict(context)
        customer = data.get("customer")
        if not isinstance(customer, Mapping):
            return None, None
        return str(customer.get("id") or "") or None, str(customer.get("name") or "") or None

    @staticmethod
    def _refund_amount(ticket: Mapping[str, Any] | str, context: Mapping[str, Any]) -> str | None:
        del context
        if isinstance(ticket, Mapping):
            for key in ("refund_amount", "amount", "requested_refund"):
                value = ticket.get(key)
                if value is not None:
                    return str(value)
        text = ResolutionAgent._ticket_text(ticket)
        match = re.search(r"\$\s*(\d+(?:\.\d{1,2})?)", text)
        return match.group(1) if match else None

    @staticmethod
    def _workspace_id(context: Mapping[str, Any]) -> str:
        workspaces = context.get("workspaces", [])
        if isinstance(workspaces, Sequence) and not isinstance(workspaces, (str, bytes)):
            for workspace in workspaces:
                if isinstance(workspace, Mapping):
                    value = workspace.get("id") or workspace.get("workspace_id")
                    if value:
                        return str(value)
        return ""

    @staticmethod
    def _diagnosis(diagnosis: Diagnosis | Mapping[str, Any] | None) -> Diagnosis:
        if isinstance(diagnosis, Diagnosis):
            return diagnosis
        if isinstance(diagnosis, Mapping):
            try:
                return Diagnosis.model_validate(diagnosis)
            except Exception:  # noqa: BLE001
                pass
        return Diagnosis()

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

    @staticmethod
    def _merge(*groups: Sequence[str]) -> list[str]:
        result: list[str] = []
        for group in groups:
            for value in group:
                cleaned = " ".join(str(value).split())
                if cleaned and cleaned not in result:
                    result.append(cleaned)
        return result


__all__ = ["ResolutionAgent"]
