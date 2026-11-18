from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.app.schemas.customers import (
    CustomerDetail,
    CustomerListResponse,
)
from backend.app.schemas.tickets import (
    TicketCreateRequest,
    TicketDetail,
    TicketListResponse,
)


def test_ticket_create_requires_exactly_one_customer_source():
    with pytest.raises(ValidationError):
        TicketCreateRequest(
            subject="Login problem",
            body="The team cannot sign in",
            channel="chat",
        )

    with pytest.raises(ValidationError):
        TicketCreateRequest(
            subject="Login problem",
            body="The team cannot sign in",
            channel="chat",
            customer_id="customer-1",
            customer={"name": "Example", "email": "example@example.com"},
        )


def test_ticket_contract_accepts_customer_id_and_valid_enums():
    request = TicketCreateRequest(
        subject="Login problem",
        body="The team cannot sign in",
        channel="email",
        customer_id="customer-1",
    )
    assert request.channel == "email"


def test_ticket_detail_and_list_contract_shapes():
    now = datetime.now(UTC)
    detail = TicketDetail(
        id="ticket-1",
        number="CD-1001",
        customer_id="customer-1",
        subject="SSO fails",
        body="SSO fails for the whole team",
        channel="web",
        status="new",
        created_at=now,
        updated_at=now,
        customer={
            "id": "customer-1",
            "name": "Example",
            "email": "example@example.com",
        },
    )
    response = TicketListResponse(items=[detail])
    assert response.items[0].number == "CD-1001"


def test_customer_detail_contract_has_safe_context_collections():
    detail = CustomerDetail(
        id="customer-1",
        name="Example",
        email="example@example.com",
    )
    response = CustomerListResponse(items=[detail])
    assert response.items[0].id == "customer-1"
