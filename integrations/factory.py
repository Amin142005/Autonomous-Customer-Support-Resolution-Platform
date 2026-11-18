from __future__ import annotations

from dataclasses import dataclass

from integrations.mock.services import (
    MockBillingService,
    MockEmailService,
    MockServiceStatusService,
    MockWorkspaceAdminService,
)
from integrations.protocols import (
    BillingIntegration,
    EmailIntegration,
    ServiceStatusIntegration,
    WorkspaceAdminIntegration,
)


@dataclass(frozen=True, slots=True)
class IntegrationBundle:
    billing: BillingIntegration
    email: EmailIntegration
    service_status: ServiceStatusIntegration
    workspace_admin: WorkspaceAdminIntegration


def create_integrations() -> IntegrationBundle:
    return IntegrationBundle(
        billing=MockBillingService(),
        email=MockEmailService(),
        service_status=MockServiceStatusService(),
        workspace_admin=MockWorkspaceAdminService(),
    )
