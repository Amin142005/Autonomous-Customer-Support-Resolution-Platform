from sqlalchemy import create_engine, inspect

from backend.app.models.entities import (
    Base,
    Ticket,
)
from backend.app.schemas.common import Category, Channel, Severity, TicketStatus


def test_category_enum_contains_exact_shared_values():
    assert {value.value for value in Category} == {
        "login_issue",
        "billing",
        "api_failure",
        "workspace_permissions",
        "storage_quota",
        "integration",
        "feature_request",
        "account",
        "security",
        "other",
    }


def test_sqlalchemy_models_create_in_sqlite():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    table_names = set(inspect(engine).get_table_names())
    assert "customers" in table_names
    assert "tickets" in table_names
    assert "workflow_runs" in table_names
    assert "customer_memory" in table_names


def test_domain_enums_and_string_uuid_columns():
    assert Ticket.__table__.c.id.type.length == 36
    assert Ticket.__table__.c.category.type.length == 32
    assert Ticket.__table__.c.severity.type.length == 20
    assert Ticket.__table__.c.channel.type.length == 20
    assert Ticket.__table__.c.status.type.length == 30
    assert Channel.API.value == "api"
    assert Severity.CRITICAL.value == "critical"
    assert TicketStatus.WAITING_ON_APPROVAL.value == "waiting_on_approval"
