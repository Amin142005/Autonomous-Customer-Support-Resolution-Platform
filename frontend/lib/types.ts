export type Role = "viewer" | "agent" | "admin";
export type Category =
  | "login_issue"
  | "billing"
  | "api_failure"
  | "workspace_permissions"
  | "storage_quota"
  | "integration"
  | "feature_request"
  | "account"
  | "security"
  | "other";
export type Severity = "low" | "medium" | "high" | "critical";
export type TicketStatus =
  | "new"
  | "in_progress"
  | "waiting_on_customer"
  | "waiting_on_approval"
  | "escalated"
  | "resolved"
  | "closed";
export type Channel = "email" | "chat" | "web" | "api";

export interface TicketCustomerInput {
  name: string;
  email: string;
  company?: string;
  plan?: string;
}

export interface TicketCreateRequest {
  subject: string;
  body: string;
  channel: Channel;
  customer_id?: string;
  customer?: TicketCustomerInput;
  workspace_id?: string;
}

export interface TicketSummary {
  id: string;
  number: string;
  customer_id: string;
  workspace_id: string | null;
  subject: string;
  body: string;
  channel: Channel;
  category: Category | null;
  severity: Severity | null;
  status: TicketStatus;
  summary: string | null;
  assignee_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface TicketCustomerSummary {
  id: string;
  name: string;
  email: string;
  company: string | null;
  plan: string | null;
}

export interface TicketWorkspaceSummary {
  id: string;
  name: string;
  status: string;
}

export interface TicketMessage {
  id: string;
  ticket_id: string;
  author_type: string;
  author_id: string | null;
  body: string;
  created_at: string;
}

export interface TicketDetail extends TicketSummary {
  customer: TicketCustomerSummary;
  workspace: TicketWorkspaceSummary | null;
  messages: TicketMessage[];
}

export interface TicketListResponse {
  items: TicketSummary[];
}

export interface Subscription {
  id: string;
  customer_id: string;
  plan: string;
  status: string;
  seats: number;
  monthly_price: number | null;
  created_at: string;
  updated_at: string;
}

export interface Workspace {
  id: string;
  customer_id: string;
  name: string;
  status: string;
  settings: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface CustomerMemory {
  id: string;
  type: string;
  content: string;
  source_ticket_id: string | null;
  created_at: string;
}

export interface CustomerSummary {
  id: string;
  name: string;
  email: string;
  company: string | null;
  plan: string | null;
}

export interface CustomerDetail extends CustomerSummary {
  subscriptions: Subscription[];
  workspaces: Workspace[];
  tickets: TicketSummary[];
  memory: CustomerMemory[];
}

export interface CustomerListResponse {
  items: CustomerSummary[];
}
