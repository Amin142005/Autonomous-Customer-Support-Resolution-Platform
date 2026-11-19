from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

from backend.app.core.guardrails import scan_for_injection, wrap_untrusted
from backend.app.schemas.common import Category, Severity

__all__ = [
    "ESCALATION_RULES",
    "matching_escalation_rules",
    "rule_category",
    "rule_severity",
    "scan_for_injection",
    "wrap_untrusted",
]

ESCALATION_RULES: dict[str, dict[str, object]] = {
    "security_breach": {
        "team": "security team",
        "severity": Severity.CRITICAL,
        "terms": (
            "possible breach",
            "security breach",
            "account compromise",
            "unauthorized login",
            "suspicious login",
            "account takeover",
        ),
    },
    "data_loss": {
        "team": "data recovery team",
        "severity": Severity.CRITICAL,
        "terms": (
            "data loss",
            "files disappeared",
            "files are missing",
            "deleted files",
            "permanent deletion",
            "cannot recover",
        ),
    },
    "workspace_deletion": {
        "team": "account deletion team",
        "severity": Severity.HIGH,
        "terms": (
            "delete legacy workspace",
            "delete workspace",
            "erase data",
            "erase its data",
            "gdpr",
            "right to erasure",
            "data erasure",
        ),
    },
    "payment_dispute": {
        "team": "billing and payment dispute team",
        "severity": Severity.HIGH,
        "terms": (
            "unauthorized charge",
            "payment dispute",
            "dispute it",
            "chargeback",
            "do not recognize",
            "don't recognize",
        ),
    },
    "enterprise_outage": {
        "team": "incident response team",
        "severity": Severity.CRITICAL,
        "terms": (
            "enterprise outage",
            "whole team",
            "affects multiple people",
            "all users",
            "service unavailable",
        ),
    },
    "legal": {
        "team": "legal and compliance team",
        "severity": Severity.HIGH,
        "terms": (
            "legal",
            "compliance",
            "subpoena",
            "court order",
            "regulatory request",
        ),
    },
    "prompt_injection": {
        "team": "security team",
        "severity": Severity.CRITICAL,
        "terms": (
            "ignore all prior instructions",
            "ignore prior instructions",
            "export every customer's records",
            "export all customer",
            "treat this as untrusted",
            "system prompt",
        ),
    },
}

_SEVERITY_RANK = {
    Severity.LOW: 0,
    Severity.MEDIUM: 1,
    Severity.HIGH: 2,
    Severity.CRITICAL: 3,
}


def _normalized_text(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))


def _contains_any(normalized_text: str, terms: Iterable[str]) -> bool:
    padded = f" {normalized_text} "
    for term in terms:
        normalized_term = _normalized_text(term)
        if normalized_term and f" {normalized_term} " in padded:
            return True
    return False


def matching_escalation_rules(
    text: str,
    plan_name: str | None = None,
) -> list[dict[str, object]]:
    """Return deterministic escalation policy matches for ticket text."""
    del plan_name
    normalized = _normalized_text(text)
    matches: list[dict[str, object]] = []

    for rule_name, rule in ESCALATION_RULES.items():
        terms = rule["terms"]
        if not isinstance(terms, tuple):
            continue
        if _contains_any(normalized, terms):
            matches.append(
                {
                    "rule": rule_name,
                    "team": rule["team"],
                    "severity": rule["severity"],
                }
            )
    return matches


def rule_category(
    text: str,
    model_category: Category | str | None = None,
) -> Category | str | None:
    """Apply deterministic category overrides for clear policy subjects."""
    normalized = _normalized_text(text)

    rules: tuple[tuple[Category, tuple[str, ...]], ...] = (
        (Category.SECURITY, ("possible breach", "account compromise", "suspicious login")),
        (Category.ACCOUNT, ("delete workspace", "erase data", "gdpr")),
        (Category.BILLING, ("unauthorized charge", "payment dispute", "chargeback")),
        (Category.LOGIN_ISSUE, ("sso", "mfa", "locked out", "cannot sign in")),
        (Category.API_FAILURE, ("http 429", "rate limit", "nightly sync")),
        (Category.STORAGE_QUOTA, ("storage quota", "upload failing", "uploads fail")),
        (Category.INTEGRATION, ("slack integration", "integration stopped")),
        (Category.WORKSPACE_PERMISSIONS, ("external collaborator", "share folder")),
        (Category.FEATURE_REQUEST, ("dark mode", "dark theme", "feature request")),
    )
    for category, terms in rules:
        if _contains_any(normalized, terms):
            return category

    if model_category is None:
        return None
    try:
        return Category(str(model_category).lower())
    except ValueError:
        return model_category


def _coerce_severity(value: Severity | str | None) -> Severity | None:
    if value is None:
        return None
    if isinstance(value, Severity):
        return value
    try:
        return Severity(str(value).lower())
    except ValueError:
        return None


def rule_severity(
    text: str,
    model_severity: Severity | str | None = None,
    category: Category | str | None = None,
) -> Severity:
    """Raise, but never lower, model severity according to deterministic policy."""
    if isinstance(model_severity, Category) or (
        isinstance(model_severity, str)
        and model_severity in {item.value for item in Category}
    ):
        detected_category = model_severity
        model_severity = category if isinstance(category, (Severity, str)) else None
        category = detected_category

    current = _coerce_severity(model_severity) or Severity.LOW
    normalized = _normalized_text(text)
    category_text = str(category).lower() if category is not None else ""

    required_severity = Severity.LOW

    critical_terms = (
        "possible breach",
        "security breach",
        "account compromise",
        "unauthorized login",
        "suspicious login",
        "enterprise outage",
        "data loss",
        "files disappeared",
        "files are missing",
        "export every customer",
        "export all customer",
        "ignore all prior instructions",
        "ignore prior instructions",
    )
    if _contains_any(normalized, critical_terms):
        required_severity = Severity.CRITICAL

    high_terms = (
        "whole team",
        "team cannot sign",
        "affects multiple people",
        "delete workspace",
        "erase data",
        "gdpr",
        "unauthorized charge",
        "payment dispute",
        "chargeback",
        "do not recognize",
        "don't recognize",
    )
    if required_severity != Severity.CRITICAL and _contains_any(
        normalized, high_terms
    ):
        required_severity = Severity.HIGH

    if "security" in category_text or "suspicious" in normalized:
        required_severity = Severity.CRITICAL
    if "dark mode" in normalized:
        required_severity = Severity.LOW

    if _SEVERITY_RANK[required_severity] > _SEVERITY_RANK[current]:
        return required_severity
    return current


def severity_for_escalation_matches(
    matches: list[Mapping[str, object]],
) -> Severity:
    """Return the highest severity required by a set of policy matches."""
    highest = Severity.LOW
    for match in matches:
        severity = _coerce_severity(match.get("severity"))
        if severity is not None and _SEVERITY_RANK[severity] > _SEVERITY_RANK[highest]:
            highest = severity
    return highest
