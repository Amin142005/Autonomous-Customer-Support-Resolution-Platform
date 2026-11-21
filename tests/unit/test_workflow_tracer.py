from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from agents.tracer import WorkflowTracer
from backend.app.core.database import create_tables


async def test_workflow_tracer_persists_safe_events():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await create_tables(engine)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        from backend.app.models.entities import Customer, Ticket
        from backend.app.schemas.common import Channel, TicketStatus

        customer = Customer(
            id="customer-tracer",
            name="Trace Customer",
            email="trace@example.test",
        )
        ticket = Ticket(
            id="ticket-tracer",
            number="CD-TRACE",
            customer_id=customer.id,
            subject="Trace workflow",
            body="Verify tracing.",
            channel=Channel.EMAIL,
            status=TicketStatus.NEW,
        )
        session.add_all([customer, ticket])
        await session.flush()

        tracer = WorkflowTracer(
            session,
            ticket_id=ticket.id,
            workflow_id="workflow-tracer",
        )
        await tracer.node_started("understand_ticket")
        await tracer.llm_called(
            node_name="understand_ticket",
            usage={"input_tokens": 12, "output_tokens": 5, "cost": 0.0},
            duration_ms=9,
        )
        await tracer.node_completed(
            "understand_ticket",
            duration_ms=9,
            payload={"status": "completed", "prompt": "never persist"},
        )
        await tracer.workflow_completed()
        await session.commit()

        from backend.app.repositories.workflow import WorkflowEventRepository

        events = await WorkflowEventRepository(session).list_for_workflow("workflow-tracer")

    assert [event.event_type for event in events] == [
        "node_started",
        "llm_called",
        "node_completed",
        "workflow_completed",
    ]
    assert events[1].token_usage == {
        "input_tokens": 12,
        "output_tokens": 5,
        "cost": 0.0,
    }
    assert "prompt" not in (events[2].payload or {})

    await engine.dispose()
