from enum import StrEnum


class Category(StrEnum):
    LOGIN_ISSUE = "login_issue"
    BILLING = "billing"
    API_FAILURE = "api_failure"
    WORKSPACE_PERMISSIONS = "workspace_permissions"
    STORAGE_QUOTA = "storage_quota"
    INTEGRATION = "integration"
    FEATURE_REQUEST = "feature_request"
    ACCOUNT = "account"
    SECURITY = "security"
    OTHER = "other"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketStatus(StrEnum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    WAITING_ON_CUSTOMER = "waiting_on_customer"
    WAITING_ON_APPROVAL = "waiting_on_approval"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Channel(StrEnum):
    EMAIL = "email"
    CHAT = "chat"
    WEB = "web"
    API = "api"


class Role(StrEnum):
    VIEWER = "viewer"
    AGENT = "agent"
    ADMIN = "admin"
