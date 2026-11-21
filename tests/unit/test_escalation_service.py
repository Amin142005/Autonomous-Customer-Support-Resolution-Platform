from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.core.database import create_tables
from backend.app.models.entities import Customer, Ticket
from backend.app.schemas.common import Channel, TicketStatus
from backend.app.schemas.workflow import EscalationDecision
from backend.app.services.escalation_service import EscalationService


async def test_escalation_service_persists_open_policy_escalation_once():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await create_tables(engine)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        customer = Customer(
            id="customer-escalation",
            name="Security Customer",
            email="security@example.test",
        )
        ticket = Ticket(
            id="ticket-escalation",
            number="CD-1005",
            customer_id=customer.id,
            subject="Suspicious logins indicate a possible breach",
            body="The account may be compromised.",
            channel=Channel.EMAIL,
            status=TicketStatus.NEW,
        )
        session.add_all([customer, ticket])
        await session.commit()

        service = EscalationService(session)
        decision = EscalationDecision(
            escalation_required=True,
            team="security team",
            reason="Deterministic security policy matched.",
        )

        first = await service.route(
            ticket_id=ticket.id,
            workflow_id="workflow-escalation",
            decision=decision,
        )
        second = await service.route(
            ticket_id=ticket.id,
            workflow_id="workflow-escalation",
            decision=decision,
        )
        await session.commit()

        persisted_ticket = await service.tickets.get_by_id(ticket.id)
        open_escalation = await service.escalations.get_open_for_ticket(ticket.id)

    assert first.id == second.id
    assert open_escalation is not None
    assert open_escalation.team == "security team"
    assert open_escalation.status == "open"
    assert persisted_ticket is not None
    assert persisted_ticket.status == TicketStatus.ESCALATED

    await engine.dispose()


async def test_escalation_service_rejects_non_escalation_decision():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await create_tables(engine)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        from backend.app.services.escalation_service import EscalationServiceError

        try:
            await EscalationService(session).route(
                ticket_id="missing",
                workflow_id="missing",
                decision=EscalationDecision(escalation_required=False),
            )
        except EscalationServiceError as exc:
            assert exc.status_code == 409
        else:
            raise AssertionError("Non-escalation decision should be rejected")

    await engine.dispose()
