-- Authenticated console users have read-only access. All writes go through the
-- FastAPI service, which uses the server-side service_role key.

CREATE OR REPLACE FUNCTION public.current_support_role()
RETURNS TEXT
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT p.role
    FROM public.profiles AS p
    WHERE p.id = (SELECT auth.uid()::text)
    LIMIT 1
$$;

REVOKE ALL ON FUNCTION public.current_support_role() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.current_support_role() TO authenticated;

REVOKE ALL ON TABLE
    profiles, customers, subscriptions, workspaces, products, tickets,
    ticket_messages, support_articles, incidents, workflow_runs, workflow_events,
    resolution_actions, approval_requests, escalations, customer_memory, audit_logs
FROM anon, authenticated;
GRANT USAGE ON SCHEMA public TO authenticated, service_role;
GRANT SELECT ON TABLE
    profiles, customers, subscriptions, workspaces, products, tickets,
    ticket_messages, support_articles, incidents, workflow_runs, workflow_events,
    resolution_actions, approval_requests, escalations, customer_memory, audit_logs
TO authenticated;
GRANT ALL ON TABLE
    profiles, customers, subscriptions, workspaces, products, tickets,
    ticket_messages, support_articles, incidents, workflow_runs, workflow_events,
    resolution_actions, approval_requests, escalations, customer_memory, audit_logs
TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE ticket_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE resolution_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE approval_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE escalations ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY profiles_read ON profiles FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('viewer', 'agent', 'admin'));
CREATE POLICY customers_read ON customers FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('viewer', 'agent', 'admin'));
CREATE POLICY subscriptions_read ON subscriptions FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('viewer', 'agent', 'admin'));
CREATE POLICY workspaces_read ON workspaces FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('viewer', 'agent', 'admin'));
CREATE POLICY products_read ON products FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('viewer', 'agent', 'admin'));
CREATE POLICY tickets_read ON tickets FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('viewer', 'agent', 'admin'));
CREATE POLICY ticket_messages_read ON ticket_messages FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('viewer', 'agent', 'admin'));
CREATE POLICY support_articles_read ON support_articles FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('viewer', 'agent', 'admin'));
CREATE POLICY incidents_read ON incidents FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('viewer', 'agent', 'admin'));
CREATE POLICY workflow_runs_read ON workflow_runs FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('viewer', 'agent', 'admin'));
CREATE POLICY workflow_events_read ON workflow_events FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('viewer', 'agent', 'admin'));
CREATE POLICY resolution_actions_read ON resolution_actions FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('viewer', 'agent', 'admin'));
CREATE POLICY approval_requests_read ON approval_requests FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('viewer', 'agent', 'admin'));
CREATE POLICY escalations_read ON escalations FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('viewer', 'agent', 'admin'));
CREATE POLICY customer_memory_read ON customer_memory FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('viewer', 'agent', 'admin'));
CREATE POLICY audit_logs_read ON audit_logs FOR SELECT TO authenticated
    USING (public.current_support_role() IN ('viewer', 'agent', 'admin'));
