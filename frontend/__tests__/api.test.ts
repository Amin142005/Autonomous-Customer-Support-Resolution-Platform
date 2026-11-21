import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiClient, ApiError, NetworkError } from "@/lib/api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("ApiClient", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("stores a demo token and sends a request id", async () => {
    let storedToken: string | null = null;
    const fetchImpl = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const request = new Request(input, init);
        expect(request.headers.get("Authorization")).toBeNull();
        expect(request.headers.get("X-Request-ID")).toBeTruthy();
        return jsonResponse({
          access_token: "demo-token",
          token_type: "bearer",
          expires_in: 28800,
          user: {
            id: "profile-1",
            email: "sam.agent@clouddesk.demo",
            full_name: "Sam Agent",
            role: "agent",
          },
        });
      },
    );

    const client = new ApiClient({
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchImpl as typeof fetch,
      getToken: () => storedToken,
      setToken: (token) => {
        storedToken = token;
      },
    });

    const response = await client.issueDemoToken({
      email: "sam.agent@clouddesk.demo",
    });

    expect(response.access_token).toBe("demo-token");
    expect(storedToken).toBe("demo-token");
  });

  it("adds ticket filters to list request query strings", async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      expect(String(input)).toBe(
        "http://localhost:8000/api/v1/tickets?status=waiting_on_approval&category=billing&limit=20&offset=10",
      );
      return jsonResponse({ items: [] });
    });

    const client = new ApiClient({
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchImpl as typeof fetch,
      getToken: () => null,
      setToken: () => undefined,
    });

    await client.listTickets({
      status: "waiting_on_approval",
      category: "billing",
      limit: 20,
      offset: 10,
    });
  });

  it("returns ApiError detail for unsuccessful responses", async () => {
    const client = new ApiClient({
      baseUrl: "http://localhost:8000",
      fetchImpl: vi.fn(async () =>
        jsonResponse({ detail: "Ticket not found" }, 404),
      ) as typeof fetch,
      getToken: () => null,
      setToken: () => undefined,
    });

    await expect(client.getTicket("missing")).rejects.toMatchObject<
      Partial<ApiError>
    >({
      name: "ApiError",
      status: 404,
      message: "Ticket not found",
    });
  });

  it("returns NetworkError for fetch failures", async () => {
    const client = new ApiClient({
      baseUrl: "http://localhost:8000",
      fetchImpl: vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }) as typeof fetch,
      getToken: () => null,
      setToken: () => undefined,
    });

    await expect(client.me()).rejects.toBeInstanceOf(NetworkError);
  });

  it("sends approval decisions and workflow actions", async () => {
    const fetchImpl = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const request = new Request(input, init);
        expect(request.method).toBe("POST");
        expect(request.url).toContain("/api/v1/approvals/ap-1/approve");
        expect(await request.json()).toEqual({ comment: "Approved for demo" });
        return jsonResponse({
          id: "ap-1",
          ticket_id: "ticket-1",
          workflow_id: "workflow-1",
          action_name: "create_refund_request",
          action_args: {},
          status: "approved",
          decided_by: "agent-1",
          reason: "Approved for demo",
          decided_at: "2026-11-21T00:00:00Z",
          workflow: null,
        });
      },
    );

    const client = new ApiClient({
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchImpl as typeof fetch,
      getToken: () => "agent-token",
      setToken: () => undefined,
    });

    const response = await client.approve("ap-1", {
      comment: "Approved for demo",
    });

    expect(response.status).toBe("approved");
  });
});
