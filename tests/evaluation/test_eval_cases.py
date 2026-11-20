from __future__ import annotations

import json
from pathlib import Path

from backend.app.schemas.common import Category, Severity


DATASET = Path(__file__).resolve().parents[2] / "datasets" / "eval_cases.json"
VALID_CATEGORIES = {category.value for category in Category}
VALID_SEVERITIES = {severity.value for severity in Severity}


def load_cases() -> list[dict[str, object]]:
    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    return [case for case in payload if isinstance(case, dict)]


def test_eval_dataset_contains_demo_cases():
    cases = load_cases()

    assert len(cases) == 13
    assert len({str(case["ticket_number"]) for case in cases}) == 13


def test_eval_cases_have_valid_categories_and_severities():
    cases = load_cases()

    for case in cases:
        assert case["expected_category"] in VALID_CATEGORIES
        assert case["expected_severity"] in VALID_SEVERITIES
        assert isinstance(case["expected_escalation"], bool)
        assert isinstance(case["expected_article_id"], str)
        assert case["expected_article_id"]


def test_eval_dataset_covers_all_categories():
    cases = load_cases()
    categories = {str(case["expected_category"]) for case in cases}

    assert categories == VALID_CATEGORIES


def test_eval_cases_include_policy_escalation_and_injection():
    cases = load_cases()
    escalations = [case for case in cases if case["expected_escalation"] is True]

    assert len(escalations) >= 5
    assert any(case["ticket_number"] == "CD-1013" for case in cases)
