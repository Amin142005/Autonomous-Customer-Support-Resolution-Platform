from __future__ import annotations

import json

from agents.specialists.escalation import EscalationAgent
from backend.app.schemas.common import Category, Severity


async def test_escalation_agent_applies_security_policy():
    agent = EscalationAgent()

    decision = await agent.run(
        "Suspicious logins indicate a possible breach",
        category=Category.SECURITY,
        severity=Severity.LOW,
    )

    assert decision.escalation_required is True
    assert decision.team == "security team"
    assert decision.severity == Severity.CRITICAL
    assert decision.confidence == 1.0


async def test_escalation_agent_applies_data_loss_policy():
    agent = EscalationAgent()

    decision = await agent.run(
        "Several project files disappeared and cannot recover",
        category=Category.OTHER,
        severity=Severity.MEDIUM,
    )

    assert decision.escalation_required is True
    assert decision.team == "data recovery team"
    assert decision.severity == Severity.CRITICAL


async def test_escalation_agent_distrusts_vague_model_escalation():
    agent = EscalationAgent()

    decision = await agent.run(
        "The Slack integration stopped",
        category=Category.INTEGRATION,
        severity=Severity.MEDIUM,
    )

    assert decision.escalation_required is False


class HighConfidenceEscalationLLM:
    async def ainvoke(self, messages: object) -> str:
        del messages
        return json.dumps({
            "escalation_required": True,
            "team": "incident response team",
            "reason": "The outage affects multiple users.",
            "severity": "critical",
            "confidence": 0.9,
        })


async def test_escalation_agent_accepts_confident_high_severity_judgement():
    agent = EscalationAgent(HighConfidenceEscalationLLM())

    decision = await agent.run(
        "Multiple users report an API outage during normal operations",
        category=Category.API_FAILURE,
        severity=Severity.CRITICAL,
    )

    assert decision.escalation_required is True
    assert decision.team == "incident response team"
    assert decision.confidence == 0.9
