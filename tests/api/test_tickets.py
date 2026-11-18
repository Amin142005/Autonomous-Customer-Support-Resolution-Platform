from datetime import UTC, datetime, timedelta

import jwt
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.api.tickets import router as tickets_router
from backend.app.core.config import Settings
from backend.app.core.database import create_tables
from backend.app.models.entities import (
    Customer,
    Profile,
    Ticket,
    TicketMessage,
    Workspace,
)
from backend.app.schemas.common import (
    Category,
    Channel,
    TicketStatus,
)


@pytest_asyncio.fixture
async def tickets_app(monkeypatch):
    settings = Settings(
        _env_file=None,
        demo_mode=True,
        jwt_secret="test-secret-with-at-least-32-characters",
    )
    monkeypatch.setattr(
        "backend.app.core.security.get_settings",
        lambda: settings,
    )

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await create_tables(engine)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        session.add_all(
            [
                Profile(
                    id="viewer-id",
                    email="vic.viewer@clouddesk.demo",
                    full_name="Vic Chen",
                    role="viewer",
                ),
                Profile(
                    id="agent-id",
                    email="sam.agent@clouddesk.demo",
                    full_name="Sam Rivera",
                    role="agent",
                ),
                Customer(
                    id="customer-1",
                    name="Avery Morgan",
                    email="avery.morgan@example.test",
                    company="Northstar Labs",
                    plan="enterprise",
                ),
                Workspace(
                    id="workspace-1",
                    customer_id="customer-1",
                    name="Northstar Main",
                    status="active",
                ),
            ]
        )
        await session.flush()
        ticket = Ticket(
            id="ticket-1",
            number="CD-1001",
            customer_id="customer-1",
            workspace_id="workspace-1",
            subject="SSO login fails",
            body="The whole team cannot sign in.",
            channel=Channel.EMAIL,
            category=Category.LOGIN_ISSUE,
            status=TicketStatus.NEW,
        )
        session.add(ticket)
        await session.flush()
        session.add(
            TicketMessage(
                ticket_id=ticket.id,
                author_type="customer",
                body=ticket.body,
            )
        )
        await session.commit()

    app = FastAPI()
    app.include_router(tickets_router, prefix="/api/v1")
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


async def test_list_and_detail_require_viewer(tickets_app):
    viewer_token = token_for(
        "viewer-id",
        "vic.viewer@clouddesk.demo",
        "viewer",
    )
    headers = {"Authorization": f"Bearer {viewer_token}"}

    async with AsyncClient(
        transport=ASGITransport(app=tickets_app),
        base_url="http://testserver",
    ) as client:
        listed = await client.get("/api/v1/tickets", headers=headers)
        detail = await client.get("/api/v1/tickets/ticket-1", headers=headers)
        missing = await client.get("/api/v1/tickets/missing", headers=headers)

    assert listed.status_code == 200
    assert [item["number"] for item in listed.json()["items"]] == ["CD-1001"]
    assert detail.status_code == 200
    assert detail.json()["customer"]["email"] == "avery.morgan@example.test"
    assert detail.json()["messages"][0]["body"] == "The whole team cannot sign in."
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Ticket not found"}


async def test_list_filters_and_pagination(tickets_app):
    viewer_token = token_for(
        "viewer-id",
        "vic.viewer@clouddesk.demo",
        "viewer",
    )
    async with AsyncClient(
        transport=ASGITransport(app=tickets_app),
        base_url="http://testserver",
    ) as client:
        matched = await client.get(
            "/api/v1/tickets",
            params={"status": "new", "category": "login_issue", "limit": 10, "offset": 0},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        empty = await client.get(
            "/api/v1/tickets",
            params={"status": "resolved"},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )

    assert matched.status_code == 200
    assert len(matched.json()["items"]) == 1
    assert empty.json()["items"] == []


async def test_create_requires_agent_and_creates_ticket_with_customer(tickets_app):
    viewer_token = token_for(
        "viewer-id",
        "vic.viewer@clouddesk.demo",
        "viewer",
    )
    agent_token = token_for(
        "agent-id",
        "sam.agent@clouddesk.demo",
        "agent",
    )
    payload = {
        "subject": "API integration stopped",
        "body": "Slack messages are no longer syncing.",
        "channel": "chat",
        "customer": {
            "name": "Test Customer",
            "email": "test.customer@example.test",
            "company": "Test Co",
            "plan": "pro",
        },
    }

    async with AsyncClient(
        transport=ASGITransport(app=tickets_app),
        base_url="http://testserver",
    ) as client:
        forbidden = await client.post(
            "/api/v1/tickets",
            json=payload,
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        created = await client.post(
            "/api/v1/tickets",
            json=payload,
            headers={"Authorization": f"Bearer {agent_token}"},
        )

    assert forbidden.status_code == 403
    assert created.status_code == 201
    body = created.json()["ticket"]
    assert body["number"] == "CD-1002"
    assert body["status"] == "new"
    assert body["customer"]["email"] == "test.customer@example.test"
    assert body["messages"][0]["body"] == payload["body"]


async def test_create_rejects_missing_customer_and_mismatched_workspace(tickets_app):
    agent_token = token_for(
        "agent-id",
        "sam.agent@clouddesk.demo",
        "agent",
    )
    headers = {"Authorization": f"Bearer {agent_token}"}

    async with AsyncClient(
        transport=ASGITransport(app=tickets_app),
        base_url="http://testserver",
    ) as client:
        missing_source = await client.post(
            "/api/v1/tickets",
            json={
                "subject": "Issue",
                "body": "Details",
                "channel": "email",
            },
            headers=headers,
        )
        missing_customer = await client.post(
            "/api/v1/tickets",
            json={
                "subject": "Issue",
                "body": "Details",
                "channel": "email",
                "customer_id": "missing",
            },
            headers=headers,
        )
        mismatched_workspace = await client.post(
            "/api/v1/tickets",
            json={
                "subject": "Issue",
                "body": "Details",
                "channel": "email",
                "customer_id": "customer-1",
                "workspace_id": "missing",
            },
            headers=headers,
        )

    assert missing_source.status_code == 422
    assert missing_customer.status_code == 404
    assert mismatched_workspace.status_code == 404
