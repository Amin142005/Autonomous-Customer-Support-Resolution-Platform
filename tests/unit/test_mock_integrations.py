from decimal import Decimal

import pytest

from integrations.factory import create_integrations
from integrations.mock.services import (
    MockBillingService,
    MockEmailService,
    MockServiceStatusService,
    MockWorkspaceAdminService,
)


async def test_factory_builds_isolated_mock_adapters():
    first = create_integrations()
    second = create_integrations()

    assert isinstance(first.billing, MockBillingService)
    assert isinstance(first.email, MockEmailService)
    assert isinstance(first.service_status, MockServiceStatusService)
    assert isinstance(first.workspace_admin, MockWorkspaceAdminService)
    assert first.billing is not second.billing
    assert first.workspace_admin is not second.workspace_admin


async def test_mock_refund_records_only_a_simulated_request():
    billing = MockBillingService()

    receipt = await billing.create_refund_request(
        "customer-1",
        Decimal("25.00"),
        "Duplicate charge",
    )

    assert receipt.request_id == "mock-refund-0001"
    assert receipt.amount == Decimal("25.00")
    assert receipt.status == "simulated"
    assert receipt.simulated
    assert billing.requests == (receipt,)


@pytest.mark.parametrize(
    "amount",
    [Decimal(0), Decimal(-1), Decimal("NaN"), Decimal("Infinity")],
)
async def test_mock_refund_rejects_non_positive_or_non_finite_amounts(amount):
    billing = MockBillingService()

    with pytest.raises(ValueError, match="positive finite Decimal"):
        await billing.create_refund_request("customer-1", amount, "test")

    assert billing.requests == ()


async def test_mock_workspace_reset_changes_only_local_adapter_state():
    workspace = MockWorkspaceAdminService(
        {("workspace-1", "external_sharing"): True}
    )

    result = await workspace.reset_setting(
        "workspace-1",
        "external_sharing",
        False,
    )

    assert result.simulated
    assert result.value is False
    assert workspace.settings[("workspace-1", "external_sharing")] is False


async def test_mock_service_status_returns_known_and_unknown_results():
    service_status = MockServiceStatusService()

    identity = await service_status.check_service_status("IDENTITY")
    missing = await service_status.check_service_status("unknown-service")

    assert identity.state == "degraded"
    assert identity.incident_ids == ("50000000-0000-4000-8000-000000000001",)
    assert missing.state == "unknown"


async def test_empty_status_configuration_does_not_restore_default_statuses():
    service_status = MockServiceStatusService({})

    identity = await service_status.check_service_status("identity")

    assert identity.state == "unknown"


async def test_mock_email_never_sends_or_retains_message_body():
    email = MockEmailService()
    body = "This body is accepted by the mock but not sent."

    receipt = await email.send_email(
        "agent@example.test",
        "Support reply",
        body,
    )

    assert receipt.message_id == "mock-message-0001"
    assert receipt.status == "simulated"
    assert receipt.simulated
    assert email.simulated_count == 1
    assert body not in repr(receipt)
