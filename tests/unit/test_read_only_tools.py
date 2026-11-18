from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.app.core.database import create_tables
from backend.app.models.entities import Customer, Subscription, Ticket
from backend.app.schemas.common import Channel, TicketStatus
from backend.app.services.knowledge_service import KnowledgeService
from backend.app.tools.read_only import register_read_only_tools
from backend.app.tools.registry import ToolRegistry
from backend.app.tools.result import ToolErrorCode
from integrations.factory import IntegrationBundle, create_integrations
from rag.ingest import KnowledgeIndex
from rag.vector_store import InMemoryVectorStore

CUSTOMER_ID = "customer-read-only-1"
TICKET_ID = "ticket-read-only-1"


@pytest_asyncio.fixture
async def read_only_context(
    tmp_path: Path,
) -> AsyncIterator[
    tuple[
        ToolRegistry,
        async_sessionmaker[AsyncSession],
        AsyncEngine,
        IntegrationBundle,
    ]
]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await create_tables(engine)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        session.add(
            Customer(
                id=CUSTOMER_ID,
                name="Avery Morgan",
                email="avery@example.test",
                company="Northstar Labs",
                plan="enterprise",
            )
        )
        await session.flush()
        session.add(
            Subscription(
                customer_id=CUSTOMER_ID,
                plan="enterprise",
                status="active",
                seats=25,
                monthly_price=250,
            )
        )
        session.add(
            Ticket(
                id=TICKET_ID,
                number="CD-9001",
                customer_id=CUSTOMER_ID,
                subject="SSO access is failing",
                body="Sensitive original message content",
                channel=Channel.EMAIL,
                status=TicketStatus.RESOLVED,
                summary="The customer could not sign in.",
            )
        )
        await session.commit()

    article_dir = tmp_path / "knowledge_base"
    article_dir.mkdir()
    (article_dir / "storage-quota.md").write_text(
        "---\n"
        "title: Storage quota\n"
        "category: storage_quota\n"
        "tags: [storage, quota]\n"
        "summary: Resolve upload failures caused by storage limits.\n"
        "---\n"
        "# Upload limits\n"
        "Check the workspace storage usage and remove unneeded files.\n",
        encoding="utf-8",
    )
    index = KnowledgeIndex(article_dir, InMemoryVectorStore())
    await index.initialize()
    knowledge_service = KnowledgeService(index)
    integrations = create_integrations()
    registry = ToolRegistry(timeout_seconds=2)
    register_read_only_tools(
        registry,
        session_factory=session_factory,
        knowledge_service=knowledge_service,
        integrations=integrations,
    )

    try:
        yield registry, session_factory, engine, integrations
    finally:
        await engine.dispose()


async def test_read_only_tools_are_registered_with_expected_names(read_only_context):
    registry, _, _, _ = read_only_context

    assert registry.tool_names == (
        "check_service_status",
        "get_customer",
        "get_subscription",
        "get_ticket_history",
        "search_docs",
    )


async def test_get_customer_returns_only_basic_profile(read_only_context):
    registry, _, _, _ = read_only_context

    result = await registry.execute("get_customer", {"customer_id": CUSTOMER_ID})

    assert result.ok
    assert result.output == {
        "id": CUSTOMER_ID,
        "name": "Avery Morgan",
        "email": "avery@example.test",
        "company": "Northstar Labs",
        "plan": "enterprise",
    }


async def test_get_subscription_returns_customer_subscriptions(read_only_context):
    registry, _, _, _ = read_only_context

    result = await registry.execute(
        "get_subscription",
        {"customer_id": CUSTOMER_ID},
    )

    assert result.ok
    assert len(result.output) == 1
    assert result.output[0]["plan"] == "enterprise"
    assert result.output[0]["seats"] == 25


async def test_get_ticket_history_omits_raw_ticket_body(read_only_context):
    registry, _, _, _ = read_only_context

    result = await registry.execute(
        "get_ticket_history",
        {"customer_id": CUSTOMER_ID},
    )

    assert result.ok
    assert len(result.output) == 1
    assert result.output[0]["number"] == "CD-9001"
    assert "body" not in result.output[0]
    assert "Sensitive original message content" not in repr(result.output)


async def test_get_ticket_history_supports_exclusion_and_pagination(
    read_only_context,
):
    registry, session_factory, _, _ = read_only_context
    async with session_factory() as session:
        session.add(
            Ticket(
                id="ticket-read-only-2",
                number="CD-9002",
                customer_id=CUSTOMER_ID,
                subject="A second issue",
                body="Second message",
                channel=Channel.WEB,
                status=TicketStatus.NEW,
            )
        )
        await session.commit()

    result = await registry.execute(
        "get_ticket_history",
        {
            "customer_id": CUSTOMER_ID,
            "limit": 1,
            "offset": 0,
            "exclude_ticket_id": TICKET_ID,
        },
    )

    assert result.ok
    assert [ticket["number"] for ticket in result.output] == ["CD-9002"]


async def test_search_docs_returns_cited_knowledge_evidence(read_only_context):
    registry, _, _, _ = read_only_context

    result = await registry.execute(
        "search_docs",
        {
            "query": "workspace storage quota upload limits",
            "category": "storage_quota",
            "mode": "hybrid",
            "top_k": 3,
        },
    )

    assert result.ok
    assert result.output
    assert result.output[0]["source"].startswith("kb://storage-quota#")
    assert result.output[0]["article_id"] == "storage-quota"


async def test_check_service_status_uses_mock_integration(read_only_context):
    registry, _, _, _ = read_only_context

    result = await registry.execute(
        "check_service_status",
        {"service_name": "identity"},
    )

    assert result.ok
    assert result.output["state"] == "degraded"
    assert result.output["incident_ids"]


async def test_missing_customer_returns_registry_failure(read_only_context):
    registry, _, _, _ = read_only_context

    result = await registry.execute(
        "get_customer",
        {"customer_id": "missing-customer"},
    )

    assert not result.ok
    assert result.error_code == ToolErrorCode.EXECUTION_FAILED
    assert result.error == "Tool execution failed (LookupError)"


async def test_read_only_tools_leave_database_records_unchanged(read_only_context):
    registry, session_factory, _, _ = read_only_context
    async with session_factory() as session:
        initial_counts = (
            await session.scalar(select(func.count()).select_from(Customer)),
            await session.scalar(select(func.count()).select_from(Subscription)),
            await session.scalar(select(func.count()).select_from(Ticket)),
        )

    for tool_name, args in (
        ("get_customer", {"customer_id": CUSTOMER_ID}),
        ("get_subscription", {"customer_id": CUSTOMER_ID}),
        ("get_ticket_history", {"customer_id": CUSTOMER_ID}),
    ):
        result = await registry.execute(tool_name, args)
        assert result.ok

    async with session_factory() as session:
        final_counts = (
            await session.scalar(select(func.count()).select_from(Customer)),
            await session.scalar(select(func.count()).select_from(Subscription)),
            await session.scalar(select(func.count()).select_from(Ticket)),
        )
    assert final_counts == initial_counts
