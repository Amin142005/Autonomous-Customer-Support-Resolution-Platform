from datetime import UTC, datetime, timedelta

import jwt
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.api.customers import router as customers_router
from backend.app.core.config import Settings
from backend.app.core.database import create_tables
from backend.app.models.entities import (
    Customer,
    CustomerMemory,
    Profile,
    Subscription,
    Ticket,
    Workspace,
)
from backend.app.schemas.common import Channel, TicketStatus


@pytest_asyncio.fixture
async def customers_app(monkeypatch):
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
                Customer(
                    id="customer-2",
                    name="Jordan Lee",
                    email="jordan.lee@example.test",
                    company="Cedar Design",
                    plan="business",
                ),
            ]
        )
        await session.flush()
        session.add_all(
            [
                Subscription(
                    customer_id="customer-1",
                    plan="enterprise",
                    status="active",
                    seats=25,
                    monthly_price=250,
                ),
                Workspace(
                    id="workspace-1",
                    customer_id="customer-1",
                    name="Northstar Main",
                    status="active",
                ),
                Ticket(
                    id="ticket-1",
                    number="CD-1001",
                    customer_id="customer-1",
                    workspace_id="workspace-1",
                    subject="SSO login fails",
                    body="The team cannot sign in.",
                    channel=Channel.EMAIL,
                    status=TicketStatus.NEW,
                    created_at=datetime(2026, 1, 1, tzinfo=UTC),
                ),
                Ticket(
                    id="ticket-2",
                    number="CD-1002",
                    customer_id="customer-1",
                    subject="Billing issue",
                    body="Please review the invoice.",
                    channel=Channel.WEB,
                    status=TicketStatus.RESOLVED,
                    created_at=datetime(2026, 1, 2, tzinfo=UTC),
                ),
                CustomerMemory(
                    customer_id="customer-1",
                    type="note",
                    content="Password=secret123 and API key=key123",
                    source_ticket_id="ticket-1",
                ),
            ]
        )
        await session.commit()

    app = FastAPI()
    app.include_router(customers_router, prefix="/api/v1")
    app.state.session_factory = session_factory

    yield app
    await engine.dispose()


def token_for(role: str) -> str:
    now = datetime.now(UTC)
    user_id = "viewer-id" if role == "viewer" else "agent-id"
    email = (
        "vic.viewer@clouddesk.demo"
        if role == "viewer"
        else "sam.agent@clouddesk.demo"
    )
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


async def test_customer_list_detail_and_history(customers_app):
    headers = {"Authorization": f"Bearer {token_for('viewer')}"}
    async with AsyncClient(
        transport=ASGITransport(app=customers_app),
        base_url="http://testserver",
    ) as client:
        listed = await client.get("/api/v1/customers", headers=headers)
        detail = await client.get(
            "/api/v1/customers/customer-1",
            headers=headers,
        )
        history = await client.get(
            "/api/v1/customers/customer-1/tickets",
            params={"limit": 10},
            headers=headers,
        )
        missing = await client.get(
            "/api/v1/customers/missing",
            headers=headers,
        )

    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 2
    assert detail.status_code == 200
    assert detail.json()["subscriptions"][0]["plan"] == "enterprise"
    assert detail.json()["workspaces"][0]["name"] == "Northstar Main"
    assert len(detail.json()["tickets"]) == 2
    assert "[REDACTED]" in detail.json()["memory"][0]["content"]
    assert "secret123" not in detail.json()["memory"][0]["content"]
    assert history.status_code == 200
    assert [ticket["number"] for ticket in history.json()["items"]] == [
        "CD-1002",
        "CD-1001",
    ]
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Customer not found"}


async def test_customer_routes_require_viewer(customers_app):
    async with AsyncClient(
        transport=ASGITransport(app=customers_app),
        base_url="http://testserver",
    ) as client:
        unauthorized = await client.get("/api/v1/customers")
        agent_access = await client.get(
            "/api/v1/customers",
            headers={"Authorization": f"Bearer {token_for('agent')}"},
        )

    assert unauthorized.status_code == 401
    assert agent_access.status_code == 200
