from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from integrations.protocols import (
    EmailReceipt,
    RefundRequestReceipt,
    ServiceStatus,
    WorkspaceSettingReset,
)

_DEFAULT_SERVICE_STATUSES = {
    "identity": ServiceStatus(
        service_name="identity",
        state="degraded",
        summary="Intermittent single sign-on failures are under investigation.",
        incident_ids=("50000000-0000-4000-8000-000000000001",),
    ),
    "collaboration": ServiceStatus(
        service_name="collaboration",
        state="operational",
        summary="No active collaboration service incidents.",
    ),
    "storage": ServiceStatus(
        service_name="storage",
        state="operational",
        summary="No active storage service incidents.",
    ),
    "api": ServiceStatus(
        service_name="api",
        state="operational",
        summary="No active API service incidents.",
    ),
    "billing": ServiceStatus(
        service_name="billing",
        state="operational",
        summary="No active billing service incidents.",
    ),
}


class MockBillingService:
    def __init__(self) -> None:
        self._requests: list[RefundRequestReceipt] = []

    @property
    def requests(self) -> tuple[RefundRequestReceipt, ...]:
        return tuple(self._requests)

    async def create_refund_request(
        self,
        customer_id: str,
        amount: Decimal,
        reason: str,
    ) -> RefundRequestReceipt:
        del reason
        if not customer_id.strip():
            raise ValueError("customer_id must not be empty")
        if not isinstance(amount, Decimal) or not amount.is_finite() or amount <= 0:
            raise ValueError("amount must be a positive finite Decimal")

        receipt = RefundRequestReceipt(
            request_id=f"mock-refund-{len(self._requests) + 1:04d}",
            customer_id=customer_id,
            amount=amount,
            status="simulated",
            simulated=True,
        )
        self._requests.append(receipt)
        return receipt


class MockWorkspaceAdminService:
    def __init__(
        self,
        initial_settings: Mapping[tuple[str, str], object] | None = None,
    ) -> None:
        self._settings = dict(initial_settings or {})

    @property
    def settings(self) -> Mapping[tuple[str, str], object]:
        return dict(self._settings)

    async def reset_setting(
        self,
        workspace_id: str,
        setting_name: str,
        default_value: object,
    ) -> WorkspaceSettingReset:
        if not workspace_id.strip():
            raise ValueError("workspace_id must not be empty")
        if not setting_name.strip():
            raise ValueError("setting_name must not be empty")

        self._settings[(workspace_id, setting_name)] = default_value
        return WorkspaceSettingReset(
            workspace_id=workspace_id,
            setting_name=setting_name,
            value=default_value,
            simulated=True,
        )


class MockServiceStatusService:
    def __init__(
        self,
        statuses: Mapping[str, ServiceStatus] | None = None,
    ) -> None:
        selected_statuses = (
            _DEFAULT_SERVICE_STATUSES if statuses is None else statuses
        )
        self._statuses = {
            name.casefold(): status for name, status in selected_statuses.items()
        }

    async def check_service_status(self, service_name: str) -> ServiceStatus:
        normalized_name = service_name.strip().casefold()
        if not normalized_name:
            raise ValueError("service_name must not be empty")
        return self._statuses.get(
            normalized_name,
            ServiceStatus(
                service_name=service_name.strip(),
                state="unknown",
                summary="No mock status is configured for this service.",
            ),
        )


class MockEmailService:
    def __init__(self) -> None:
        self._simulated_count = 0

    @property
    def simulated_count(self) -> int:
        return self._simulated_count

    async def send_email(
        self,
        recipient: str,
        subject: str,
        body: str,
    ) -> EmailReceipt:
        del subject, body
        if not recipient.strip():
            raise ValueError("recipient must not be empty")

        self._simulated_count += 1
        return EmailReceipt(
            message_id=f"mock-message-{self._simulated_count:04d}",
            recipient=recipient,
            status="simulated",
            simulated=True,
        )
