from __future__ import annotations

import json
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from backend.app.core.config import get_settings
from backend.app.schemas.common import Category, Severity


@dataclass(frozen=True)
class LLMUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0

    def as_dict(self) -> dict[str, int | float]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost": self.cost,
        }


class FakeLLM:
    """Deterministic offline provider used for demos and tests."""

    def __init__(self, model: str = "fake") -> None:
        self.model = model

    async def ainvoke(self, messages: Sequence[Any]) -> str:
        text = _message_text(messages)
        lowered = text.casefold()

        if "classification" in lowered:
            category = _detect_category(lowered)
            summary = _subject_summary(lowered)
            return json.dumps({"category": category.value, "summary": summary})

        if "severityassessment" in lowered or "severity assessment" in lowered:
            severity = _detect_severity(lowered)
            reason = f"Policy and ticket context indicate {severity.value} severity."
            return json.dumps({"severity": severity.value, "reason": reason})

        if "diagnosis" in lowered:
            return json.dumps(
                {
                    "probable_causes": ["Review the configured service settings."],
                    "hypotheses": ["Review the configured service settings."],
                    "steps": [
                        "Check the relevant service status.",
                        "Reproduce the issue and verify the configuration.",
                    ],
                    "checks": [],
                    "root_cause": None,
                    "confidence": 0.6,
                }
            )

        if "resolutionplan" in lowered or "resolution plan" in lowered:
            return json.dumps(
                {
                    "summary": "Apply the verified troubleshooting steps.",
                    "customer_reply": "Please try the recommended troubleshooting steps.",
                    "reply": "Please try the recommended troubleshooting steps.",
                    "internal_notes": "Follow the approved support playbook.",
                    "steps": [
                        "Check the relevant service status.",
                        "Reproduce the issue and verify the configuration.",
                    ],
                    "actions": [],
                }
            )

        if "escalationdecision" in lowered or "escalation decision" in lowered:
            return json.dumps(
                {
                    "escalation_required": False,
                    "team": None,
                    "reason": "No policy escalation is indicated.",
                    "severity": "low",
                    "confidence": 0.7,
                }
            )

        if "customercontext" in lowered:
            return json.dumps(
                {
                    "customer": {},
                    "subscription": None,
                    "subscriptions": [],
                    "workspaces": [],
                    "previous_tickets": [],
                    "memory_notes": [],
                }
            )

        if "previouscase" in lowered:
            return json.dumps(
                {
                    "ticket_number": "",
                    "number": "",
                    "subject": "",
                    "category": None,
                    "resolution": "",
                    "summary": "",
                    "similarity": 0.0,
                }
            )

        if "evidence" in lowered:
            return json.dumps(
                {
                    "id": "",
                    "title": "",
                    "source": "",
                    "snippet": "",
                    "score": 0.0,
                    "url": "",
                    "article_id": "",
                }
            )

        return "{}"


class LLMProvider:
    def __init__(self, llm: Any, provider: str, model: str) -> None:
        self.llm = llm
        self.provider = provider
        self.model = model


def get_llm() -> LLMProvider:
    settings = get_settings()
    provider = settings.llm_provider.strip().lower()
    model = settings.llm_model
    if provider == "fake":
        return LLMProvider(FakeLLM(model), provider, model)
    raise ValueError(
        f"Unsupported LLM_PROVIDER '{provider}'. P9-1 provides the offline fake provider."
    )


async def call_structured[T: BaseModel](
    response_model: type[T],
    messages: Sequence[Any] | str,
    *,
    retries: int = 1,
    llm: Any | None = None,
    prompt: str | None = None,
) -> tuple[T, LLMUsage, int]:
    """Call the configured provider and validate a Pydantic structured result."""
    if prompt is not None:
        messages = prompt
    if isinstance(messages, str):
        prompt_messages: list[Any] = [{"role": "user", "content": messages}]
    else:
        prompt_messages = list(messages)

    provider = llm if llm is not None else get_llm()
    client = getattr(provider, "llm", provider)

    if hasattr(client, "ainvoke"):
        prompt_messages.append(
            {
                "role": "system",
                "content": (
                    f"Return only valid JSON matching the {response_model.__name__} "
                    "Pydantic schema."
                ),
            }
        )
    started = time.monotonic()
    last_error: Exception | None = None
    for _attempt in range(max(1, retries)):
        try:
            raw = await client.ainvoke(prompt_messages)
            if isinstance(raw, str):
                payload = json.loads(raw)
            elif isinstance(raw, BaseModel):
                payload = raw.model_dump()
            elif hasattr(raw, "content"):
                payload = json.loads(str(raw.content))
            else:
                payload = raw
            parsed = response_model.model_validate(payload)
            last_error = None
            break
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    duration_ms = int((time.monotonic() - started) * 1000)
    usage = LLMUsage(input_tokens=0, output_tokens=0, cost=0.0)
    return parsed, usage, duration_ms


def _message_text(messages: Sequence[Any]) -> str:
    parts: list[str] = []
    for message in messages:
        if isinstance(message, dict):
            parts.append(str(message.get("content", "")))
        elif isinstance(message, tuple) and len(message) > 1:
            parts.append(str(message[1]))
        elif hasattr(message, "content"):
            parts.append(str(message.content))
        else:
            parts.append(str(message))
    return "\n".join(parts)


def _detect_category(text: str) -> Category:
    if any(term in text for term in ("possible breach", "suspicious login", "security breach")):
        return Category.SECURITY
    if any(term in text for term in ("delete workspace", "erase data", "gdpr")):
        return Category.ACCOUNT
    if any(term in text for term in ("refund", "unauthorized charge", "payment dispute")):
        return Category.BILLING
    if any(term in text for term in ("sso", "mfa", "locked out", "cannot sign in")):
        return Category.LOGIN_ISSUE
    if any(term in text for term in ("429", "rate limit", "nightly sync")):
        return Category.API_FAILURE
    if any(term in text for term in ("storage quota", "upload")):
        return Category.STORAGE_QUOTA
    if any(term in text for term in ("slack integration", "integration stopped")):
        return Category.INTEGRATION
    if any(term in text for term in ("share folder", "external collaborator")):
        return Category.WORKSPACE_PERMISSIONS
    if any(term in text for term in ("dark mode", "dark theme")):
        return Category.FEATURE_REQUEST
    return Category.OTHER


def _detect_severity(text: str) -> Severity:
    if any(
        term in text
        for term in (
            "security breach",
            "suspicious login",
            "possible breach",
            "enterprise outage",
            "data loss",
            "files disappeared",
            "ignore instructions",
            "export all customer",
        )
    ):
        return Severity.CRITICAL
    if any(term in text for term in ("unauthorized charge", "delete workspace", "gdpr")):
        return Severity.HIGH
    if any(term in text for term in ("429", "quota", "cannot", "fail")):
        return Severity.MEDIUM
    return Severity.LOW


def _subject_summary(text: str) -> str:
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if stripped and "classification" not in stripped.casefold():
            return stripped[:200]
    return "Support ticket requires classification."


__all__ = [
    "FakeLLM",
    "LLMProvider",
    "LLMUsage",
    "call_structured",
    "get_llm",
]
