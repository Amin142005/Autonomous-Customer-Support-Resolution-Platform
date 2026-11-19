from collections.abc import AsyncIterator

import fakeredis.aioredis
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from backend.app.core.database import create_tables
from backend.app.models.entities import Customer, Ticket
from backend.app.schemas.common import Channel
from memory.memory_service import MemoryService

CUSTOMER_ID = "memory-service-customer"
TICKET_ID = "memory-service-ticket"


@pytest_asyncio.fixture
async def memory_service_context() -> AsyncIterator[
    tuple[async_sessionmaker, AsyncEngine]
]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await create_tables(engine)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        session.add(
            Customer(
                id=CUSTOMER_ID,
                name="Avery Morgan",
                email="avery-memory-service@example.test",
            )
        )
        session.add(
            Ticket(
                id=TICKET_ID,
                number="CD-8802",
                customer_id=CUSTOMER_ID,
                subject="MFA recovery",
                body="Raw ticket body that must never enter memory",
                channel=Channel.CHAT,
            )
        )
        await session.commit()

    try:
        yield session_factory, engine
    finally:
        await engine.dispose()


async def test_recall_customer_reads_long_term_memory(memory_service_context):
    session_factory, _ = memory_service_context
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async with session_factory() as session:
        service = MemoryService(session, redis_client=redis)
        await service.record_resolution(
            CUSTOMER_ID,
            ticket_id=TICKET_ID,
            past_issue="Recurring MFA login issue",
            troubleshooting_steps=["Verify MFA enrollment", "Reset MFA session"],
            resolution_note="Customer access restored",
        )

    async with session_factory() as session:
        service = MemoryService(session, redis_client=redis)
        recalled = await service.recall_customer(CUSTOMER_ID, limit=10)

    assert len(recalled) == 4
    assert {note.type for note in recalled} == {
        "past_issue",
        "troubleshooting",
        "note",
    }


async def test_record_resolution_writes_first_three_steps_and_resolution(
    memory_service_context,
):
    session_factory, _ = memory_service_context

    async with session_factory() as session:
        service = MemoryService(
            session,
            redis_client=fakeredis.aioredis.FakeRedis(decode_responses=True),
        )
        records = await service.record_resolution(
            CUSTOMER_ID,
            ticket_id=TICKET_ID,
            past_issue="MFA login issue",
            troubleshooting_steps=[
                "Step 1",
                "Step 2",
                "Step 3",
                "Step 4 must not be stored",
            ],
            resolution_note="Password=secret123 and API key=key123",
        )

    assert len(records) == 5
    types = [note.type for note, _ in records]
    assert types == [
        "past_issue",
        "troubleshooting",
        "troubleshooting",
        "troubleshooting",
        "note",
    ]
    all_created = [created for _, created in records]
    assert all(all_created)
    assert "secret123" not in records[-1][0].content
    assert "key123" not in records[-1][0].content


async def test_record_resolution_is_exact_duplicate_safe(memory_service_context):
    session_factory, _ = memory_service_context

    async with session_factory() as session:
        service = MemoryService(
            session,
            redis_client=fakeredis.aioredis.FakeRedis(decode_responses=True),
        )
        first = await service.record_resolution(
            CUSTOMER_ID,
            ticket_id=TICKET_ID,
            past_issue="MFA login issue",
            troubleshooting_steps=["Verify MFA"],
            resolution_note="Access restored",
        )
        second = await service.record_resolution(
            CUSTOMER_ID,
            ticket_id=TICKET_ID,
            past_issue="MFA login issue",
            troubleshooting_steps=["Verify MFA"],
            resolution_note="Access restored",
        )

    assert all(created for _, created in first)
    assert not any(created for _, created in second)


async def test_memory_service_keeps_short_term_and_long_term_separate(
    memory_service_context,
):
    session_factory, _ = memory_service_context
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async with session_factory() as session:
        service = MemoryService(session, redis_client=redis)
        await service.set_workflow_state(
            "workflow-1",
            {"current_node": "memory_update"},
        )
        await service.append_conversation(
            "ticket-1",
            {"role": "agent", "body": "Temporary context"},
        )

    async with session_factory() as session:
        service = MemoryService(session, redis_client=redis)
        assert await service.get_workflow_state("workflow-1") == {
            "current_node": "memory_update"
        }
        assert await service.get_conversation("ticket-1") == [
            {"role": "agent", "body": "Temporary context"}
        ]
