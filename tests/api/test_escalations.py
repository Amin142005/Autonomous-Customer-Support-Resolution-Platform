from datetime import UTC, datetime, timedelta

import jwt
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.api.escalations import router as escalations_router
from backend.app.core.config import Settings
from backend.app.core.database import create_tables
from backend.app.models.entities import Customer, Escalation, Profile, Ticket
from backend.app.schemas.common import Channel, Role, TicketStatus


@pytest_asyncio.fixture
async def escalations_app(monkeypatch):
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
            Customer(id="customer-1", name="Avery", email="avery@example.test", plan="enterprise"),
        ])
        await session.flush()
        ticket = Ticket(
            id="ticket-1005",
            number="CD-1005",
            customer_id="customer-1",
            subject="Suspicious logins indicate a possible breach",
            body="The account may be compromised.",
            channel=Channel.EMAIL,
            status=TicketStatus.ESCALATED,
        )
        session.add(ticket)
        await session.flush()
        session.add(Escalation(
            id="escalation-1",
            ticket_id=ticket.id,
            team="security team",
            reason="Deterministic policy matched.",
            status="open",
        ))
        await session.commit()

    app = FastAPI()
    app.include_router(escalations_router, prefix="/api/v1")
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


async def test_escalation_routes_are_viewer_readable(escalations_app):
    viewer = token_for("viewer-id", "vic.viewer@clouddesk.demo", "viewer")
    headers = {"Authorization": f"Bearer {viewer}"}

    async with AsyncClient(transport=ASGITransport(app=escalations_app), base_url="http://testserver") as client:
        listed = await client.get("/api/v1/escalations", headers=headers)
        detail = await client.get("/api/v1/escalations/escalation-1", headers=headers)
        missing = await client.get("/api/v1/escalations/missing", headers=headers)

    assert listed.status_code == 200
    assert listed.json()["items"][0]["team"] == "security team"
    assert detail.status_code == 200
    assert detail.json()["ticket_id"] == "ticket-1005"
    assert missing.status_code == 404
