from __future__ import annotations

from agents.specialists.troubleshooting import TroubleshootingAgent
from backend.app.schemas.common import Category
from backend.app.schemas.workflow import CustomerContext, Evidence
from backend.app.tools.registry import ToolRegistry


class StatusTool:
    name = "check_service_status"

    async def ainvoke(self, input: dict[str, object]) -> object:
        service_name = str(input.get("service_name", ""))
        return {
            "service_name": service_name,
            "state": "degraded",
            "summary": "Intermittent service failures are under investigation.",
            "incident_ids": ["incident-123"],
        }


async def test_troubleshooting_agent_returns_numbered_diagnosis():
    registry = ToolRegistry(timeout_seconds=1)
    registry.register(StatusTool())
    agent = TroubleshootingAgent(registry)

    diagnosis = await agent.run(
        {
            "subject": "SSO login fails for the whole team",
            "body": "Users cannot complete identity provider login.",
        },
        category=Category.LOGIN_ISSUE,
        evidence=[
            Evidence(
                id="sso",
                title="SSO login troubleshooting",
                source="kb://sso-login#login",
                snippet="Verify identity provider settings.",
                score=0.9,
            )
        ],
        customer_context=CustomerContext(
            subscription={"plan": "enterprise", "seats": 25},
            memory_notes=["Use the MFA recovery playbook."],
        ),
    )

    assert diagnosis.steps
    assert diagnosis.probable_causes
    assert diagnosis.checks
    assert diagnosis.checks[0]["state"] == "degraded"
    assert diagnosis.confidence >= 0.75
    assert diagnosis.steps[0].startswith("1. ")


async def test_troubleshooting_agent_handles_missing_status_tool():
    agent = TroubleshootingAgent(ToolRegistry(timeout_seconds=1))

    diagnosis = await agent.run(
        "The API returns HTTP 429 during nightly sync",
        category=Category.API_FAILURE,
    )

    assert diagnosis.steps
    assert diagnosis.checks == []
    assert all(isinstance(step, str) and step for step in diagnosis.steps)
