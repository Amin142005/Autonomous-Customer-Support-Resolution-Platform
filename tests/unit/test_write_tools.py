from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from backend.app.core.database import create_tables
from backend.app.models.entities import Customer, Ticket
from backend.app.schemas.common import Channel, TicketStatus
from backend.app.tools.registry import ToolRegistry
from backend.app.tools.result import ToolErrorCode
from backend.app.tools.write_tools import register_write_tools
from integrations.factory import IntegrationBundle, create_integrations

CUSTOMER_ID = "customer-write-1"
TICKET_ID = "ticket-write-1"


@pytest_asyncio.fixture
async def write_context(
    tmp_path: Path,
) -> AsyncIterator[
    tuple[ToolRegistry, async_sessionmaker, AsyncEngine, IntegrationBundle]
]:
    del tmp_path
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await create_tables(engine)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        session.add(
            Customer(
                id=CUSTOMER_ID,
                name="Avery Morgan",
                email="avery-write@example.test",
                plan="enterprise",
            )
        )
        session.add(
            Ticket(
                id=TICKET_ID,
                number="CD-9101",
                customer_id=CUSTOMER_ID,
                subject="Original subject",
                body="Original ticket body",
                channel=Channel.EMAIL,
                status=TicketStatus.NEW,
            )
        )
        await session.commit()

    integrations = create_integrations()
    registry = ToolRegistry(timeout_seconds=2)
    register_write_tools(
        registry,
        session_factory=session_factory,
        integrations=integrations,
    )

    try:
        yield registry, session_factory, engine, integrations
    finally:
        await engine.dispose()


async def test_write_tools_are_registered_with_expected_names(write_context):
    registry, _, _, _ = write_context

    assert registry.tool_names == (
        "create_refund_request",
        "reset_demo_setting",
        "update_ticket",
    )


async def test_update_ticket_changes_supported_fields(write_context):
    registry, session_factory, _, _ = write_context

    result = await registry.execute(
        "update_ticket",
        {
            "ticket_id": TICKET_ID,
            "status": "in_progress",
            "summary": "Support is investigating the issue.",
            "severity": "high",
            "category": "login_issue",
        },
    )

    assert result.ok
    assert result.output["status"] == "in_progress"
    assert result.output["summary"] == "Support is investigating the issue."
    assert result.output["severity"] == "high"
    assert result.output["category"] == "login_issue"

    async with session_factory() as session:
        ticket = await session.get(Ticket, TICKET_ID)
        assert ticket is not None
        assert ticket.status == TicketStatus.IN_PROGRESS


async def test_reset_demo_setting_requires_approval_before_mock_side_effect(
    write_context,
):
    registry, _, _, integrations = write_context
    args = {
        "workspace_id": "workspace-1",
        "setting_name": "mfa_required",
        "default_value": True,
    }

    blocked = await registry.execute("reset_demo_setting", args)
    approved = await registry.execute(
        "reset_demo_setting",
        args,
        approved=True,
    )

    assert blocked.error_code == ToolErrorCode.APPROVAL_REQUIRED
    assert blocked.requires_approval
    assert approved.ok
    assert approved.output["value"] is True
    assert integrations.workspace_admin.settings == {
        ("workspace-1", "mfa_required"): True
    }


async def test_refund_requires_approval_and_runs_as_mock_when_approved(
    write_context,
):
    registry, _, _, integrations = write_context
    args = {
        "customer_id": CUSTOMER_ID,
        "amount": "25.50",
        "reason": "Duplicate seat charge",
    }

    blocked = await registry.execute("create_refund_request", args)
    approved = await registry.execute(
        "create_refund_request",
        args,
        approved=True,
    )

    assert blocked.error_code == ToolErrorCode.APPROVAL_REQUIRED
    assert blocked.requires_approval
    assert approved.ok
    assert approved.output["amount"] == "25.50"
    assert approved.output["simulated"] is True
    assert len(integrations.billing.requests) == 1


async def test_missing_ticket_returns_explicit_registry_failure(write_context):
    registry, _, _, _ = write_context

    result = await registry.execute(
        "update_ticket",
        {"ticket_id": "missing-ticket", "status": "resolved"},
    )

    assert not result.ok
    assert result.error_code == ToolErrorCode.EXECUTION_FAILED
    assert result.error == "Tool execution failed (LookupError)"
