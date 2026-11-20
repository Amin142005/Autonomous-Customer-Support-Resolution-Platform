from __future__ import annotations

from agents.specialists.resolution import ResolutionAgent
from backend.app.schemas.common import Category
from backend.app.schemas.workflow import CustomerContext, Diagnosis, Evidence


async def test_resolution_agent_creates_grounded_plan():
    agent = ResolutionAgent()
    diagnosis = Diagnosis(
        probable_causes=["MFA session is stale"],
        steps=["Check MFA status", "Restart the SSO session"],
        root_cause="MFA session is stale",
        confidence=0.8,
    )

    plan = await agent.run(
        {
            "id": "ticket-123",
            "subject": "Locked out after MFA attempts",
            "body": "The team cannot complete MFA login.",
        },
        diagnosis,
        category=Category.LOGIN_ISSUE,
        evidence=[Evidence(
            id="mfa",
            title="MFA recovery",
            source="kb://mfa-recovery#steps",
            snippet="Verify enrollment and restart the session.",
            score=0.95,
        )],
        customer_context=CustomerContext(
            customer={"id": "customer-123", "name": "Avery Morgan"},
        ),
    )

    assert plan.summary
    assert plan.customer_reply
    assert plan.reply == plan.customer_reply
    assert plan.steps
    assert "Check MFA status" in plan.steps
    assert plan.actions[0].tool == "update_ticket"
    assert plan.actions[0].approval_required is False


async def test_resolution_agent_proposes_approval_gated_refund():
    agent = ResolutionAgent()

    plan = await agent.run(
        {
            "id": "ticket-1002",
            "number": "CD-1002",
            "subject": "Refund charged for 8 seats",
            "body": "Please refund $25.00 for the extra seats.",
            "category": "billing",
            "refund_amount": "25.00",
        },
        Diagnosis(steps=["Compare active seats", "Verify the invoice"]),
        category=Category.BILLING,
        customer_context=CustomerContext(
            customer={"id": "customer-8", "name": "Refund Customer"},
        ),
    )

    refund_actions = [action for action in plan.actions if action.tool == "create_refund_request"]
    assert len(refund_actions) == 1
    assert refund_actions[0].approval_required is True
    assert refund_actions[0].arguments["amount"] == "25.00"


def test_resolution_plan_actions_determine_setting_reset():
    agent = ResolutionAgent()

    actions = agent.plan_actions(
        {"id": "ticket-42", "subject": "Reset demo setting", "body": "Restore the default setting."},
        Category.OTHER,
        Diagnosis(),
        CustomerContext(workspaces=[{"id": "workspace-1"}]),
    )

    reset_actions = [action for action in actions if action.tool == "reset_demo_setting"]
    assert len(reset_actions) == 1
    assert reset_actions[0].approval_required is True
