from datetime import UTC, datetime, timedelta

import jwt
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.api.approvals import router as approvals_router
from backend.app.core.config import Settings
from backend.app.core.database import create_tables
from backend.app.models.entities import (
    ApprovalRequest,
    Customer,
    Profile,
    Ticket,
    WorkflowRun,
)
from backend.app.schemas.common import Channel, Role, TicketStatus


@pytest_asyncio.fixture
async def approvals_app(monkeypatch):
    settings = Settings(
        _env_file=None,
        demo_mode=True,
        jwt_secret="test-secret-with-at-least-32-characters",
    )
    monkeypatch.setattr("backend.app.core.security.get_settings", lambda: settings)

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await create_tables(engine)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        session.add_all([
            Profile(id="viewer-id", email="vic.viewer@clouddesk.demo", full_name="Vic", role=Role.VIEWER),
            Profile(id="agent-id", email="sam.agent@clouddesk.demo", full_name="Sam", role=Role.AGENT),
            Customer(id="customer-1", name="Avery", email="avery@example.test", plan="pro"),
            Ticket(
                id="ticket-1",
                number="CD-1002",
                customer_id="customer-1",
                subject="Refund charged for extra seats",
                body="Please refund $25.",
                channel=Channel.EMAIL,
                status=TicketStatus.WAITING_ON_APPROVAL,
            ),
        ])
        await session.flush()
        run = WorkflowRun(
            id="workflow-1",
            ticket_id="ticket-1",
            status="paused",
            state={"approval_status": "pending", "paused": True},
            thread_id="workflow-1",
        )
        session.add(run)
        await session.flush()
        session.add(ApprovalRequest(
            id="approval-1",
            ticket_id="ticket-1",
            workflow_id=run.id,
            action_name="create_refund_request",
            action_args={"customer_id": "customer-1", "amount": "25.00"},
            status="pending",
        ))
        await session.commit()

    app = FastAPI()
    app.include_router(approvals_router, prefix="/api/v1")
    app.state.session_factory = session_factory

    yield app
    await engine.dispose()


def token_for(user_id: str, email: str, role: str) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "role": role,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        "test-secret-with-at-least-32-characters",
        algorithm="HS256",
    )


async def test_approval_detail_is_viewer_readable(approvals_app):
    viewer = token_for("viewer-id", "vic.viewer@clouddemo.test", "viewer")
    async with AsyncClient(transport=ASGITransport(app=approvals_app), base_url="http://testserver") as client:
        response = await client.get(
            "/api/v1/approvals/approval-1",
            headers={"Authorization": f"Bearer {viewer}"},
        )
        missing = await client.get(
            "/api/v1/approvals/missing",
            headers={"Authorization": f"Bearer {viewer}"},
        )

    assert response.status_code == 200
    assert response.json()["action_name"] == "create_refund_request"
    assert response.json()["status"] == "pending"
    assert missing.status_code == 404


async def test_approval_decisions_require_agent(approvals_app):
    viewer = token_for("viewer-id", "vic.viewer@clouddemo.test", "viewer")
    async with AsyncClient(transport=ASGITransport(app=approvals_app), base_url="http://testserver") as client:
        forbidden = await client.post(
            "/api/v1/approvals/approval-1/approve",
            json={"comment": "Approved for test"},
            headers={"Authorization": f"Bearer {viewer}"},
        )

    assert forbidden.status_code == 403


async def test_reject_records_actor_and_escalates_ticket(approvals_app):
    agent = token_for("agent-id", "sam.agent@clouddesk.demo", "agent")

    async with AsyncClient(transport=ASGITransport(app=approvals_app), base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/approvals/approval-1/reject",
            json={"comment": "Not enough evidence"},
            headers={"Authorization": f"Bearer {agent}"},
        )
        duplicate = await client.post(
            "/api/v1/approvals/approval-1/approve",
            json={"comment": "Duplicate decision"},
            headers={"Authorization": f"Bearer {agent}"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert response.json()["decided_by"] == "agent-id"
    assert response.json()["reason"] == "Not enough evidence"
    assert duplicate.status_code == 409


async def test_approve_records_actor_and_resumes_paused_run(approvals_app):
    agent = token_for("agent-id", "sam.agent@clouddesk.demo", "agent")

    async with AsyncClient(transport=ASGITransport(app=approvals_app), base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/approvals/approval-1/approve",
            json={"comment": "Refund approved"},
            headers={"Authorization": f"Bearer {agent}"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["decided_by"] == "agent-id"
    assert response.json()["reason"] == "Refund approved"
    assert response.json()["workflow"] is not None
