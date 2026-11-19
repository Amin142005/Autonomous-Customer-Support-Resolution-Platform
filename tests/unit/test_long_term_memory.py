from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from backend.app.core.database import create_tables
from backend.app.models.entities import Customer, Ticket
from backend.app.schemas.common import Channel
from memory.long_term import LongTermMemory, LongTermMemoryError

CUSTOMER_ID = "memory-customer-1"
OTHER_CUSTOMER_ID = "memory-customer-2"
TICKET_ID = "memory-ticket-1"


@pytest_asyncio.fixture
async def memory_context() -> AsyncIterator[
    tuple[async_sessionmaker, AsyncEngine]
]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await create_tables(engine)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        session.add_all(
            [
                Customer(
                    id=CUSTOMER_ID,
                    name="Avery Morgan",
                    email="avery-memory@example.test",
                ),
                Customer(
                    id=OTHER_CUSTOMER_ID,
                    name="Jordan Lee",
                    email="jordan-memory@example.test",
                ),
                Ticket(
                    id=TICKET_ID,
                    number="CD-8801",
                    customer_id=CUSTOMER_ID,
                    subject="MFA issue",
                    body="Raw ticket body with MFA setup instructions",
                    channel=Channel.EMAIL,
                ),
            ]
        )
        await session.commit()

    try:
        yield session_factory, engine
    finally:
        await engine.dispose()


async def test_record_scrubs_and_recalls_permitted_memory(memory_context):
    session_factory, _ = memory_context
    async with session_factory() as session:
        memory = LongTermMemory(session)

        note, created = await memory.record(
            CUSTOMER_ID,
            type="preference",
            content="Uses Password=secret123 for this demo",
            source_ticket_id=TICKET_ID,
        )

        assert created
        assert note.type == "preference"
        assert "secret123" not in note.content
        assert "[REDACTED]" in note.content
        assert await memory.recall(CUSTOMER_ID, limit=10) == [note]


async def test_exact_duplicate_is_not_created_twice(memory_context):
    session_factory, _ = memory_context
    async with session_factory() as session:
        memory = LongTermMemory(session)

        first, created_first = await memory.record(
            CUSTOMER_ID,
            type="past_issue",
            content="MFA login issue",
            source_ticket_id=TICKET_ID,
        )
        second, created_second = await memory.record(
            CUSTOMER_ID,
            type="past_issue",
            content="MFA login issue",
            source_ticket_id=TICKET_ID,
        )

        assert created_first
        assert not created_second
        assert first.id == second.id
        assert len(await memory.recall(CUSTOMER_ID)) == 1


async def test_invalid_memory_type_is_rejected(memory_context):
    session_factory, _ = memory_context
    async with session_factory() as session:
        memory = LongTermMemory(session)

        with pytest.raises(LongTermMemoryError, match="type must be one of"):
            await memory.record(
                CUSTOMER_ID,
                type="raw_ticket",
                content="Unsafe memory",
            )


async def test_missing_customer_is_rejected(memory_context):
    session_factory, _ = memory_context
    async with session_factory() as session:
        memory = LongTermMemory(session)

        with pytest.raises(LookupError, match="was not found"):
            await memory.recall("missing-customer")
        with pytest.raises(LookupError, match="was not found"):
            await memory.record(
                "missing-customer",
                type="note",
                content="A safe note",
            )


async def test_source_ticket_must_belong_to_customer(memory_context):
    session_factory, _ = memory_context
    async with session_factory() as session:
        memory = LongTermMemory(session)

        with pytest.raises(LongTermMemoryError, match="belong to the customer"):
            await memory.record(
                OTHER_CUSTOMER_ID,
                type="note",
                content="A safe note",
                source_ticket_id=TICKET_ID,
            )


async def test_raw_ticket_body_is_rejected(memory_context):
    session_factory, _ = memory_context
    async with session_factory() as session:
        memory = LongTermMemory(session)

        with pytest.raises(LongTermMemoryError, match="raw ticket body"):
            await memory.record(
                CUSTOMER_ID,
                type="past_issue",
                content="Raw ticket body with MFA setup instructions",
                source_ticket_id=TICKET_ID,
            )


async def test_recall_limit_is_bounded(memory_context):
    session_factory, _ = memory_context
    async with session_factory() as session:
        memory = LongTermMemory(session)

        with pytest.raises(LongTermMemoryError, match="between 1 and 10"):
            await memory.recall(CUSTOMER_ID, limit=11)
