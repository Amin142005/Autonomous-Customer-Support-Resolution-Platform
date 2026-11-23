import type {
  ApprovalDecisionRequest,
  ApprovalResponse,
  CustomerDetail,
  CustomerListFilters,
  CustomerListResponse,
  CustomerTicketFilters,
  DemoTokenRequest,
  DemoTokenResponse,
  EscalationFilters,
  EscalationListResponse,
  EscalationResponse,
  HealthResponse,
  KnowledgeArticle,
  KnowledgeArticleListResponse,
  KnowledgeReindexResponse,
  KnowledgeSearchRequest,
  KnowledgeSearchResponse,
  MeResponse,
  TicketActionRequest,
  TicketActionResponse,
  TicketCreateRequest,
  TicketCreateResponse,
  TicketDetail,
  TicketFilters,
  TicketListResponse,
  WorkflowEventsResponse,
  WorkflowRunResponse,
  WorkflowStatusResponse,
} from "./types";

export const ACCESS_TOKEN_KEY = "clouddesk_access_token";
export const REQUEST_ID_HEADER = "X-Request-ID";

const DEFAULT_API_BASE_URL = "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export class NetworkError extends Error {
  constructor(message = "Unable to reach the CloudDesk API") {
    super(message);
    this.name = "NetworkError";
  }
}

export interface ApiClientOptions {
  baseUrl?: string;
  getToken?: () => string | null;
  setToken?: (token: string | null) => void;
  fetchImpl?: typeof fetch;
}

function createRequestId(): string {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }
  return `req-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function browserGetToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

function browserSetToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token === null) {
    window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  } else {
    window.localStorage.setItem(ACCESS_TOKEN_KEY, token);
  }
}

function buildQuery(parameters: object): string {
  const query = new URLSearchParams();
  Object.entries(parameters).forEach(([key, value]) => {
    if (
      (typeof value === "string" ||
        typeof value === "number" ||
        typeof value === "boolean") &&
      String(value).length > 0
    ) {
      query.set(key, String(value));
    }
  });
  const result = query.toString();
  return result ? `?${result}` : "";
}

function detailMessage(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (
    typeof detail === "object" &&
    detail !== null &&
    "detail" in detail &&
    typeof (detail as { detail?: unknown }).detail === "string"
  ) {
    return (detail as { detail: string }).detail;
  }
  return "The CloudDesk API returned an error";
}

export class ApiClient {
  readonly baseUrl: string;
  private readonly getToken: () => string | null;
  private readonly setToken: (token: string | null) => void;
  private readonly fetchImpl: typeof fetch;

  constructor(options: ApiClientOptions = {}) {
    this.baseUrl = (
      options.baseUrl ??
      process.env.NEXT_PUBLIC_API_BASE_URL ??
      DEFAULT_API_BASE_URL
    ).replace(/\/$/, "");
    this.getToken = options.getToken ?? browserGetToken;
    this.setToken = options.setToken ?? browserSetToken;
    // Wrap the global fetch: calling it as `this.fetchImpl(...)` would bind
    // `this` to ApiClient and browsers throw "Illegal invocation".
    this.fetchImpl =
      options.fetchImpl ?? ((input, init) => globalThis.fetch(input, init));
  }

  setAccessToken(token: string | null): void {
    this.setToken(token);
  }

  getAccessToken(): string | null {
    return this.getToken();
  }

  async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    headers.set(REQUEST_ID_HEADER, createRequestId());

    const token = this.getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    if (init.body !== undefined)
      headers.set("Content-Type", "application/json");

    let response: Response;
    try {
      response = await this.fetchImpl(`${this.baseUrl}${path}`, {
        ...init,
        headers,
        cache: "no-store",
      });
    } catch (error) {
      if (error instanceof TypeError) {
        throw new NetworkError();
      }
      throw error;
    }

    if (response.status === 401) {
      this.setToken(null);
      if (typeof window !== "undefined") {
        window.location.assign("/login?reason=expired");
      }
    }

    if (response.status === 204) return undefined as T;

    let body: unknown = null;
    const text = await response.text();
    if (text) {
      try {
        body = JSON.parse(text);
      } catch {
        body = text;
      }
    }

    if (!response.ok) {
      throw new ApiError(detailMessage(body), response.status, body);
    }

    return body as T;
  }

  async health(): Promise<HealthResponse> {
    return this.request<HealthResponse>("/health");
  }

  async liveHealth(): Promise<HealthResponse> {
    return this.request<HealthResponse>("/health/live");
  }

  async readyHealth(): Promise<HealthResponse> {
    return this.request<HealthResponse>("/health/ready");
  }

  async issueDemoToken(request: DemoTokenRequest): Promise<DemoTokenResponse> {
    const response = await this.request<DemoTokenResponse>(
      "/api/v1/auth/demo-token",
      {
        method: "POST",
        body: JSON.stringify(request),
      },
    );
    this.setToken(response.access_token);
    return response;
  }

  async me(): Promise<MeResponse> {
    return this.request<MeResponse>("/api/v1/auth/me");
  }

  async listTickets(filters: TicketFilters = {}): Promise<TicketListResponse> {
    return this.request<TicketListResponse>(
      `/api/v1/tickets${buildQuery({
        status: filters.status,
        category: filters.category,
        severity: filters.severity,
        limit: filters.limit,
        offset: filters.offset,
      })}`,
    );
  }

  async createTicket(
    request: TicketCreateRequest,
  ): Promise<TicketCreateResponse> {
    return this.request<TicketCreateResponse>("/api/v1/tickets", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  async getTicket(ticketId: string): Promise<TicketDetail> {
    return this.request<TicketDetail>(
      `/api/v1/tickets/${encodeURIComponent(ticketId)}`,
    );
  }

  async runTicket(ticketId: string): Promise<WorkflowRunResponse> {
    return this.request<WorkflowRunResponse>(
      `/api/v1/tickets/${encodeURIComponent(ticketId)}/run`,
      { method: "POST" },
    );
  }

  async getWorkflow(ticketId: string): Promise<WorkflowStatusResponse> {
    return this.request<WorkflowStatusResponse>(
      `/api/v1/tickets/${encodeURIComponent(ticketId)}/workflow`,
    );
  }

  async getWorkflowEvents(ticketId: string): Promise<WorkflowEventsResponse> {
    return this.request<WorkflowEventsResponse>(
      `/api/v1/tickets/${encodeURIComponent(ticketId)}/events`,
    );
  }

  async listCustomers(
    filters: CustomerListFilters = {},
  ): Promise<CustomerListResponse> {
    return this.request<CustomerListResponse>(
      `/api/v1/customers${buildQuery(filters)}`,
    );
  }

  async getCustomer(customerId: string): Promise<CustomerDetail> {
    return this.request<CustomerDetail>(
      `/api/v1/customers/${encodeURIComponent(customerId)}`,
    );
  }

  async getCustomerTickets(
    customerId: string,
    filters: CustomerTicketFilters = {},
  ): Promise<TicketListResponse> {
    return this.request<TicketListResponse>(
      `/api/v1/customers/${encodeURIComponent(customerId)}/tickets${buildQuery(filters)}`,
    );
  }

  async listKnowledge(): Promise<KnowledgeArticleListResponse> {
    return this.request<KnowledgeArticleListResponse>("/api/v1/knowledge");
  }

  async getKnowledgeArticle(articleId: string): Promise<KnowledgeArticle> {
    return this.request<KnowledgeArticle>(
      `/api/v1/knowledge/${encodeURIComponent(articleId)}`,
    );
  }

  async searchKnowledge(
    request: KnowledgeSearchRequest,
  ): Promise<KnowledgeSearchResponse> {
    return this.request<KnowledgeSearchResponse>("/api/v1/knowledge/search", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  async reindexKnowledge(): Promise<KnowledgeReindexResponse> {
    return this.request<KnowledgeReindexResponse>("/api/v1/knowledge/reindex", {
      method: "POST",
    });
  }

  async getApproval(approvalId: string): Promise<ApprovalResponse> {
    return this.request<ApprovalResponse>(
      `/api/v1/approvals/${encodeURIComponent(approvalId)}`,
    );
  }

  async approve(
    approvalId: string,
    request: ApprovalDecisionRequest = {},
  ): Promise<ApprovalResponse> {
    return this.request<ApprovalResponse>(
      `/api/v1/approvals/${encodeURIComponent(approvalId)}/approve`,
      { method: "POST", body: JSON.stringify(request) },
    );
  }

  async reject(
    approvalId: string,
    request: ApprovalDecisionRequest = {},
  ): Promise<ApprovalResponse> {
    return this.request<ApprovalResponse>(
      `/api/v1/approvals/${encodeURIComponent(approvalId)}/reject`,
      { method: "POST", body: JSON.stringify(request) },
    );
  }

  async listEscalations(
    filters: EscalationFilters = {},
  ): Promise<EscalationListResponse> {
    return this.request<EscalationListResponse>(
      `/api/v1/escalations${buildQuery(filters)}`,
    );
  }

  async getEscalation(escalationId: string): Promise<EscalationResponse> {
    return this.request<EscalationResponse>(
      `/api/v1/escalations/${encodeURIComponent(escalationId)}`,
    );
  }

  async replyToTicket(
    ticketId: string,
    request: TicketActionRequest,
  ): Promise<TicketActionResponse> {
    return this.request<TicketActionResponse>(
      `/api/v1/tickets/${encodeURIComponent(ticketId)}/reply`,
      { method: "POST", body: JSON.stringify(request) },
    );
  }

  async requestTicketInfo(
    ticketId: string,
    request: TicketActionRequest,
  ): Promise<TicketActionResponse> {
    return this.request<TicketActionResponse>(
      `/api/v1/tickets/${encodeURIComponent(ticketId)}/request-info`,
      { method: "POST", body: JSON.stringify(request) },
    );
  }

  async escalateTicket(
    ticketId: string,
    request: TicketActionRequest,
  ): Promise<TicketActionResponse> {
    return this.request<TicketActionResponse>(
      `/api/v1/tickets/${encodeURIComponent(ticketId)}/escalate`,
      { method: "POST", body: JSON.stringify(request) },
    );
  }
}

export const api = new ApiClient();
