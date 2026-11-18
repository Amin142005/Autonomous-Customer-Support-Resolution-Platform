from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol

ServiceState = Literal["operational", "degraded", "outage", "unknown"]


@dataclass(frozen=True, slots=True)
class RefundRequestReceipt:
    request_id: str
    customer_id: str
    amount: Decimal
    status: str
    simulated: bool


@dataclass(frozen=True, slots=True)
class WorkspaceSettingReset:
    workspace_id: str
    setting_name: str
    value: object
    simulated: bool


@dataclass(frozen=True, slots=True)
class ServiceStatus:
    service_name: str
    state: ServiceState
    summary: str
    incident_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EmailReceipt:
    message_id: str
    recipient: str
    status: str
    simulated: bool


class BillingIntegration(Protocol):
    async def create_refund_request(
        self,
        customer_id: str,
        amount: Decimal,
        reason: str,
    ) -> RefundRequestReceipt:
        ...


class WorkspaceAdminIntegration(Protocol):
    async def reset_setting(
        self,
        workspace_id: str,
        setting_name: str,
        default_value: object,
    ) -> WorkspaceSettingReset:
        ...


class ServiceStatusIntegration(Protocol):
    async def check_service_status(self, service_name: str) -> ServiceStatus:
        ...


class EmailIntegration(Protocol):
    async def send_email(
        self,
        recipient: str,
        subject: str,
        body: str,
    ) -> EmailReceipt:
        ...
