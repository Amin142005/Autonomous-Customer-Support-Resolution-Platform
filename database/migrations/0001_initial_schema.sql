-- Initial PostgreSQL schema. Apply once to a new database.
-- This migration is immutable after application; add a new numbered migration
-- for all future schema changes.

CREATE TABLE profiles (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'viewer'
        CHECK (role IN ('viewer', 'agent', 'admin')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE customers (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    company VARCHAR(255),
    plan VARCHAR(50),
    data JSON,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE subscriptions (
    id VARCHAR(36) PRIMARY KEY,
    customer_id VARCHAR(36) NOT NULL REFERENCES customers(id),
    plan VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    seats INTEGER NOT NULL DEFAULT 0,
    monthly_price DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE workspaces (
    id VARCHAR(36) PRIMARY KEY,
    customer_id VARCHAR(36) NOT NULL REFERENCES customers(id),
    name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    settings JSON,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE products (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    metadata_json JSON,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tickets (
    id VARCHAR(36) PRIMARY KEY,
    number VARCHAR(20) NOT NULL UNIQUE,
    customer_id VARCHAR(36) NOT NULL REFERENCES customers(id),
    workspace_id VARCHAR(36) REFERENCES workspaces(id),
    subject VARCHAR(500) NOT NULL,
    body TEXT NOT NULL,
    channel VARCHAR(20) NOT NULL
        CHECK (channel IN ('email', 'chat', 'web', 'api')),
    category VARCHAR(32)
        CHECK (category IS NULL OR category IN (
            'login_issue', 'billing', 'api_failure', 'workspace_permissions',
            'storage_quota', 'integration', 'feature_request', 'account',
            'security', 'other'
        )),
    severity VARCHAR(20)
        CHECK (severity IS NULL OR severity IN ('low', 'medium', 'high', 'critical')),
    status VARCHAR(30) NOT NULL DEFAULT 'new'
        CHECK (status IN (
            'new', 'in_progress', 'waiting_on_customer', 'waiting_on_approval',
            'escalated', 'resolved', 'closed'
        )),
    summary TEXT,
    assignee_id VARCHAR(36) REFERENCES profiles(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ticket_messages (
    id VARCHAR(36) PRIMARY KEY,
    ticket_id VARCHAR(36) NOT NULL REFERENCES tickets(id),
    author_type VARCHAR(20) NOT NULL,
    author_id VARCHAR(36),
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE support_articles (
    id VARCHAR(36) PRIMARY KEY,
    slug VARCHAR(255) NOT NULL UNIQUE,
    title VARCHAR(500) NOT NULL,
    category VARCHAR(32)
        CHECK (category IS NULL OR category IN (
            'login_issue', 'billing', 'api_failure', 'workspace_permissions',
            'storage_quota', 'integration', 'feature_request', 'account',
            'security', 'other'
        )),
    summary TEXT,
    content TEXT NOT NULL,
    metadata_json JSON,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE incidents (
    id VARCHAR(36) PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    status VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL
        CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMPTZ,
    details JSON,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE workflow_runs (
    id VARCHAR(36) PRIMARY KEY,
    ticket_id VARCHAR(36) NOT NULL REFERENCES tickets(id),
    status VARCHAR(50) NOT NULL DEFAULT 'running',
    state JSON,
    thread_id VARCHAR(36),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE workflow_events (
    id VARCHAR(36) PRIMARY KEY,
    ticket_id VARCHAR(36) NOT NULL REFERENCES tickets(id),
    workflow_id VARCHAR(36) REFERENCES workflow_runs(id),
    event_type VARCHAR(50) NOT NULL,
    node_name VARCHAR(100),
    payload JSON,
    duration_ms INTEGER,
    token_usage JSON,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE resolution_actions (
    id VARCHAR(36) PRIMARY KEY,
    ticket_id VARCHAR(36) NOT NULL REFERENCES tickets(id),
    workflow_id VARCHAR(36) REFERENCES workflow_runs(id),
    tool_name VARCHAR(100) NOT NULL,
    args JSON,
    status VARCHAR(50) NOT NULL,
    result JSON,
    approved_by VARCHAR(36) REFERENCES profiles(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE approval_requests (
    id VARCHAR(36) PRIMARY KEY,
    ticket_id VARCHAR(36) NOT NULL REFERENCES tickets(id),
    workflow_id VARCHAR(36) REFERENCES workflow_runs(id),
    action_name VARCHAR(100) NOT NULL,
    action_args JSON,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    decided_by VARCHAR(36) REFERENCES profiles(id),
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE escalations (
    id VARCHAR(36) PRIMARY KEY,
    ticket_id VARCHAR(36) NOT NULL REFERENCES tickets(id),
    team VARCHAR(255) NOT NULL,
    reason TEXT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE customer_memory (
    id VARCHAR(36) PRIMARY KEY,
    customer_id VARCHAR(36) NOT NULL REFERENCES customers(id),
    type VARCHAR(50) NOT NULL
        CHECK (type IN ('preference', 'past_issue', 'troubleshooting', 'note')),
    content TEXT NOT NULL,
    source_ticket_id VARCHAR(36) REFERENCES tickets(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE audit_logs (
    id VARCHAR(36) PRIMARY KEY,
    actor_id VARCHAR(36) REFERENCES profiles(id),
    method VARCHAR(10) NOT NULL,
    path VARCHAR(1000) NOT NULL,
    status_code INTEGER,
    request_id VARCHAR(128),
    data JSON,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

CREATE TRIGGER profiles_set_updated_at BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER customers_set_updated_at BEFORE UPDATE ON customers
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER subscriptions_set_updated_at BEFORE UPDATE ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER workspaces_set_updated_at BEFORE UPDATE ON workspaces
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER products_set_updated_at BEFORE UPDATE ON products
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER tickets_set_updated_at BEFORE UPDATE ON tickets
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER ticket_messages_set_updated_at BEFORE UPDATE ON ticket_messages
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER support_articles_set_updated_at BEFORE UPDATE ON support_articles
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER incidents_set_updated_at BEFORE UPDATE ON incidents
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER workflow_runs_set_updated_at BEFORE UPDATE ON workflow_runs
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER workflow_events_set_updated_at BEFORE UPDATE ON workflow_events
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER resolution_actions_set_updated_at BEFORE UPDATE ON resolution_actions
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER approval_requests_set_updated_at BEFORE UPDATE ON approval_requests
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER escalations_set_updated_at BEFORE UPDATE ON escalations
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER customer_memory_set_updated_at BEFORE UPDATE ON customer_memory
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER audit_logs_set_updated_at BEFORE UPDATE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
