import pytest

from backend.app.core.llm import FakeLLM, call_structured, get_llm
from backend.app.schemas.common import Category, Severity
from backend.app.schemas.workflow import (
    Classification,
    Diagnosis,
    EscalationDecision,
    ResolutionPlan,
    SeverityAssessment,
)


@pytest.mark.asyncio
async def test_fake_llm_provider_is_available_offline():
    provider = get_llm()

    assert provider.provider == "fake"
    assert isinstance(provider.llm, FakeLLM)


@pytest.mark.asyncio
async def test_fake_llm_returns_valid_classification():
    result, usage, duration_ms = await call_structured(
        Classification,
        [{"role": "user", "content": "Classification: SSO login fails for the whole team"}],
    )

    assert result.category == Category.LOGIN_ISSUE
    assert result.summary
    assert usage.cost == 0.0
    assert duration_ms >= 0


@pytest.mark.asyncio
async def test_fake_llm_returns_valid_severity():
    result, _, _ = await call_structured(
        SeverityAssessment,
        [{"role": "user", "content": "Severity assessment: possible breach and suspicious logins"}],
    )

    assert result.severity == Severity.CRITICAL
    assert result.reason


@pytest.mark.asyncio
async def test_fake_llm_returns_diagnosis_resolution_and_escalation():
    diagnosis, _, _ = await call_structured(
        Diagnosis,
        "Diagnosis: the API is failing and returns 429.",
    )
    resolution, _, _ = await call_structured(
        ResolutionPlan,
        "Resolution plan: provide recovery steps.",
    )
    escalation, _, _ = await call_structured(
        EscalationDecision,
        "Escalation decision: suspicious logins were reported.",
    )

    assert diagnosis.steps
    assert resolution.customer_reply
    assert isinstance(escalation.escalation_required, bool)
