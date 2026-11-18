# CloudDesk Support — API contract

This document is the route and payload contract for the v1 console. Routes are mounted
under `/api/v1` unless marked as health routes. `CLAUDE.md` is the product specification.
When implementing or changing a route, keep this contract, `backend/app/schemas/`, and
`frontend/lib/types.ts` synchronized.

> These routes and shapes define the intended API. A contract entry is not evidence that
> its implementation exists or has been validated.

## Conventions

- JSON request and response bodies use `application/json`.
- Protected routes require `Authorization: Bearer <JWT>`. Roles are `viewer`, `agent`,
  and `admin`; the server enforces access.
- Send `X-Request-ID` to correlate a request. The server echoes or creates it on every
  response. CORS exposes the response header.
- Errors use `{ "detail": "<message>" }`. Use 401 for missing/invalid authentication,
  403 for insufficient role, 404 for missing resources, 409 for conflicting workflow
  state, 422 for invalid input, 429 for rate limiting, and 5xx for server errors.
- List endpoints return `{ "items": [...] }`; pagination parameters and metadata must
  be documented by the endpoint before implementation if introduced.
- IDs are opaque strings. Ticket identifiers may be UUIDs; human-readable ticket
  numbers use values such as `CD-1001`.

## Shared domain values

```text
Role:      viewer | agent | admin
Category:  login_issue | billing | api_failure | workspace_permissions |
           storage_quota | integration | feature_request | account | security | other
Severity:  low | medium | high | critical
Status:    new | in_progress | waiting_on_customer | waiting_on_approval |
           escalated | resolved | closed
Channel:   email | chat | web | api
```

## Health (no authentication)

| Method and path | Purpose | Response |
|---|---|---|
| `GET /health` | Basic service health | `200 { "status": "ok" }` |
| `GET /health/live` | Liveness probe; no dependency I/O | `200 { "status": "ok" }` |
| `GET /health/ready` | Configuration readiness for database, Redis, vector store, and LLM; replace with live probes when clients exist | `200 { "status": "ready" }` or `503 { "status": "degraded", "checks": {...} }` |

Readiness details must not contain credentials, connection strings, or secret values.

## Authentication

| Method and path | Role | Purpose |
|---|---|---|
| `POST /api/v1/auth/demo-token` | Public in demo mode | Issue an eight-hour token for a configured demo user |
| `GET /api/v1/auth/me` | Any authenticated role | Return the current profile and role |

Demo-token request:

```json
{ "email": "sam.agent@clouddesk.demo" }
```

Demo-token response:

```json
{ "access_token": "<token>", "token_type": "bearer", "expires_in": 28800, "user": { "id": "<id>", "email": "<email>", "role": "agent" } }
```

Demo token issuance is disabled outside demo mode. Production authentication validates
the configured Supabase-compatible HS256 JWT; the browser never receives a service-role
key.

## Tickets

| Method and path | Minimum role | Purpose |
|---|---|---|
| `GET /api/v1/tickets` | viewer | List tickets; supports documented status/category/severity filters |
| `POST /api/v1/tickets` | agent | Create a ticket from email, chat, web, or API |
| `GET /api/v1/tickets/{ticket_id}` | viewer | Ticket detail, messages, and customer reference |
| `POST /api/v1/tickets/{ticket_id}/run` | agent | Start a workflow; returns 202 |
| `GET /api/v1/tickets/{ticket_id}/workflow` | viewer | Current run status and safe workflow state |
| `GET /api/v1/tickets/{ticket_id}/events` | viewer | Inspect workflow events |
| `POST /api/v1/tickets/{ticket_id}/reply` | agent | Submit a validated customer reply |
| `POST /api/v1/tickets/{ticket_id}/request-info` | agent | Request information from the customer |
| `POST /api/v1/tickets/{ticket_id}/escalate` | agent | Escalate a ticket |

Ticket creation accepts `subject`, `body`, `channel`, and either a customer identifier
or the customer fields required to create/link one. The channel must be one of the
shared values. The response includes the created ticket.

Ticket creation request:

```json
{
  "subject": "<subject>",
  "body": "<ticket body>",
  "channel": "email",
  "customer_id": "<customer id>",
  "workspace_id": "<optional workspace id>"
}
```

Alternatively, provide `customer` instead of `customer_id`:

```json
{
  "subject": "<subject>",
  "body": "<ticket body>",
  "channel": "web",
  "customer": {
    "name": "<customer name>",
    "email": "<customer email>",
    "company": "<optional company>",
    "plan": "<optional plan>"
  }
}
```

Exactly one customer source (`customer_id` or `customer`) is required. `subject`,
`body`, and `channel` are required; unknown or empty required values return `422`.
Ticket creation succeeds with `201 Created` and returns
`{ "ticket": { ...TicketDetail... } }`. Missing customers or workspaces return
`404`; mismatched workspaces are rejected as a missing customer workspace.

Ticket list items and ticket detail use these fields:

```text
TicketSummary: id, number, customer_id, workspace_id, subject, body, channel,
category, severity, status, summary, assignee_id, created_at, updated_at
```

Ticket detail additionally includes `customer`, `workspace`, and `messages`.
Messages contain `id`, `ticket_id`, `author_type`, `author_id`, `body`, and
`created_at`. List endpoints return `{ "items": [...] }`; filters are `status`,
`category`, and `severity`, with `limit` and `offset` pagination parameters.

Workflow run response (`202 Accepted`):

```json
{ "workflow_id": "<id>" }
```

Starting a second run while the ticket is `waiting_on_approval` returns 409. Workflow
responses expose decisions, evidence, tool results, node progress, usage, and errors
needed by the console; they never expose raw prompts, hidden reasoning, secrets, or
other customers' data.

Reply request:

```json
{ "body": "<customer-facing reply>" }
```

The server validates customer-facing output before accepting it. Replying does not
execute real email delivery in v1.

## Approvals

| Method and path | Minimum role | Purpose |
|---|---|---|
| `GET /api/v1/approvals/{approval_id}` | viewer | Read pending/decided approval details |
| `POST /api/v1/approvals/{approval_id}/approve` | agent | Record approval and resume the paused workflow |
| `POST /api/v1/approvals/{approval_id}/reject` | agent | Record rejection and route the workflow to escalation |

Decision request:

```json
{ "comment": "<optional reason>" }
```

Approval responses identify the approval and resulting workflow state. A run that is not
paused cannot be resumed and returns 409. Refund requests and account/workspace changes
must have an approval record before execution.

## Customers

| Method and path | Minimum role | Purpose |
|---|---|---|
| `GET /api/v1/customers` | viewer | List customers |
| `GET /api/v1/customers/{customer_id}` | viewer | Customer, subscription, workspace, ticket-history, and safe memory context |
| `GET /api/v1/customers/{customer_id}/tickets` | viewer | Customer ticket history |

Customer responses include only fields needed by support workflows and the console.
Memory responses contain scrubbed notes and never secrets or raw ticket bodies.
Customer list and history support `limit` (1–100) and `offset` query parameters.

Customer detail fields:

```text
CustomerDetail: id, name, email, company, plan, subscriptions, workspaces,
tickets, memory
```

Subscriptions include `id`, `customer_id`, `plan`, `status`, `seats`,
`monthly_price`, `created_at`, and `updated_at`. Workspaces include `id`,
`customer_id`, `name`, `status`, `settings`, `created_at`, and `updated_at`.
Safe memory items include `id`, `type`, `content`, `source_ticket_id`, and
`created_at`. Customer list and history endpoints return `{ "items": [...] }`;
history is ordered newest first.

## Knowledge

| Method and path | Minimum role | Purpose |
|---|---|---|
| `GET /api/v1/knowledge` | viewer | List knowledge articles |
| `GET /api/v1/knowledge/{article_id}` | viewer | Read an article |
| `POST /api/v1/knowledge/search` | viewer | Retrieve cited evidence |
| `POST /api/v1/knowledge/reindex` | admin | Rebuild the configured vector index |

Search request:

```json
{ "query": "<question>", "category": "<optional category>", "mode": "hybrid", "top_k": 5 }
```

`mode` is `hybrid`, `semantic`, or `keyword`; `top_k` is between 1 and 20.

The list response is `{ "items": [KnowledgeArticleSummary, ...] }`. A summary
contains `id`, `slug`, `title`, `category`, `tags`, and `summary`. The article
detail route returns those fields plus the Markdown `content`. Search returns
`{ "items": [Evidence, ...] }`; each evidence item contains `id`, `title`,
`source` (`kb://slug#section`), `snippet`, `score`, `url`, and `article_id`.
`POST /api/v1/knowledge/reindex` is admin-only and returns
`{ "articles_indexed": number, "chunks_indexed": number }`. Article content is
treated as untrusted input.

## Escalations, agents, audit, settings, and MCP

| Method and path | Minimum role | Purpose |
|---|---|---|
| `GET /api/v1/escalations` | viewer | List escalations and assigned teams |
| `GET /api/v1/agents` | viewer | Return graph node and edge metadata |
| `GET /api/v1/audit` | viewer | Read audit records |
| `GET /api/v1/settings` | admin | Read safe application settings |
| `PATCH /api/v1/settings` | admin | Update supported settings |
| `GET /api/v1/mcp/tools` | admin | List tools exposed through the MCP interface |

Settings responses must omit secrets. MCP tools use the same registry and authorization
policy as application calls; exposing a tool does not bypass approval requirements.

## Dashboard

| Method and path | Minimum role | Purpose |
|---|---|---|
| `GET /api/v1/dashboard/summary` | viewer | Return aggregate ticket and workflow counts for the dashboard |

## Contract maintenance

When a route, authorization rule, request/response field, enum, or status code changes:

1. Update this document.
2. Update the corresponding Pydantic schema and route implementation.
3. Update `frontend/lib/types.ts` and API-client behavior.
4. Add or update an API test for the changed contract and role behavior.
