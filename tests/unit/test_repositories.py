from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.models.entities import (
    Base,
    Customer,
    CustomerMemory,
    Ticket,
    TicketMessage,
    WorkflowEvent,
)
from backend.app.repositories import (
    ApprovalRequestRepository,
    CustomerMemoryRepository,
    CustomerRepository,
    TicketMessageRepository,
    TicketRepository,
    WorkflowEventRepository,
    WorkflowRunRepository,
)
from backend.app.schemas.common import Category, Channel, Severity, TicketStatus


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as test_session:
        yield test_session
    await engine.dispose()


async def create_customer(session, email: str = "customer@example.com") -> Customer:
    return await CustomerRepository(session).create(
        name="Example Customer", email=email, company="Example Co"
    )


async def create_ticket(
    session,
    customer_id: str,
    number: str,
    *,
    category: Category | None = None,
    severity: Severity | None = None,
    status: TicketStatus = TicketStatus.NEW,
) -> Ticket:
    return await TicketRepository(session).create(
        number=number,
        customer_id=customer_id,
        subject=f"Subject {number}",
        body="Ticket body",
        channel=Channel.EMAIL,
        category=category,
        severity=severity,
        status=status,
    )


async def test_base_repository_crud_and_validation(session):
    customers = CustomerRepository(session)
    customer = await customers.create(name="Ada", email="ada@example.com")

    assert customer.id is not None
    assert await customers.get_by_id(customer.id) == customer
    assert await customers.get_by_email("ada@example.com") == customer
    assert await customers.update_by_id(customer.id, {"name": "Ada Lovelace"}) == customer
    assert customer.name == "Ada Lovelace"
    assert await customers.list(limit=1) == [customer]

    with pytest.raises(ValueError, match="primary-key"):
        await customers.update(customer, {"id": "new-id"})
    with pytest.raises(ValueError, match="limit"):
        await customers.list(limit=0)
    with pytest.raises(ValueError, match="offset"):
        await customers.list(offset=-1)

    assert await customers.delete_by_id(customer.id) is True
    assert await customers.get_by_id(customer.id) is None
    assert await customers.delete_by_id(customer.id) is False


async def test_ticket_repository_filters_history_and_eager_detail(session):
    customer = await create_customer(session)
    resolved = await create_ticket(
        session,
        customer.id,
        "CD-1001",
        category=Category.BILLING,
        severity=Severity.MEDIUM,
        status=TicketStatus.RESOLVED,
    )
    await create_ticket(
        session,
        customer.id,
        "CD-1002",
        category=Category.LOGIN_ISSUE,
        severity=Severity.HIGH,
    )
    first_message_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    session.add(
        TicketMessage(
            ticket_id=resolved.id,
            author_type="customer",
            body="Original message",
            created_at=first_message_time,
        )
    )
    session.add(
        TicketMessage(
            ticket_id=resolved.id,
            author_type="agent",
            body="Response",
            created_at=first_message_time + timedelta(minutes=1),
        )
    )
    await session.flush()

    tickets = TicketRepository(session)
    filtered = await tickets.list_tickets(
        status=TicketStatus.RESOLVED,
        category=Category.BILLING,
        severity=Severity.MEDIUM,
    )
    assert [ticket.number for ticket in filtered] == ["CD-1001"]
    assert await tickets.get_by_number("CD-1001") == resolved
    assert await tickets.list_for_customer(
        customer.id, exclude_ticket_id=resolved.id
    ) == [await tickets.get_by_number("CD-1002")]

    detail = await tickets.get_detail(resolved.id)
    assert detail is not None
    assert detail.customer.email == "customer@example.com"
    assert {message.body for message in detail.messages} == {"Original message", "Response"}
    assert [
        message.body
        for message in await TicketMessageRepository(session).list_for_ticket(resolved.id)
    ] == ["Original message", "Response"]
    assert await CustomerRepository(session).get_with_context(customer.id) is not None


async def test_workflow_and_memory_repositories_query_by_domain_keys(session):
    customer = await create_customer(session)
    ticket = await create_ticket(session, customer.id, "CD-2001")
    runs = WorkflowRunRepository(session)
    workflow = await runs.create(ticket_id=ticket.id, status="paused", state={"step": 1})
    session.add(
        WorkflowEvent(
            ticket_id=ticket.id,
            workflow_id=workflow.id,
            event_type="node_started",
            node_name="understand_ticket",
        )
    )
    session.add(
        WorkflowEvent(
            ticket_id=ticket.id,
            workflow_id=workflow.id,
            event_type="node_completed",
            node_name="understand_ticket",
        )
    )
    approval = await ApprovalRequestRepository(session).create(
        ticket_id=ticket.id,
        workflow_id=workflow.id,
        action_name="create_refund_request",
        status="pending",
    )
    session.add_all(
        [
            CustomerMemory(
                customer_id=customer.id,
                type="note",
                content="First note",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
            CustomerMemory(
                customer_id=customer.id,
                type="preference",
                content="Second note",
                created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            ),
        ]
    )
    await session.flush()

    assert await runs.get_latest_for_ticket(ticket.id) == workflow
    assert await ApprovalRequestRepository(session).get_pending_for_ticket(
        ticket.id
    ) == approval
    events = await WorkflowEventRepository(session).list_for_workflow(workflow.id)
    assert [event.event_type for event in events] == [
        "node_started",
        "node_completed",
    ]
    memory = await CustomerMemoryRepository(session).list_for_customer(
        customer.id, limit=1
    )
    assert len(memory) == 1
    assert memory[0].content == "Second note"

