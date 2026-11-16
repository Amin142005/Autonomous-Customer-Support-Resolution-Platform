# CloudDesk Support — Architecture

This document describes the intended system boundaries and runtime flow. The normative
requirements are in `../CLAUDE.md`; phase exit criteria are in `../PLAN_PHASE.md`.
This is target architecture, not a claim that every component is implemented.

## System context

```text
Support agent browser
        |
      HTTPS
        v
Next.js 15 console (:3000)
        | REST /api/v1, Bearer JWT, X-Request-ID
        v
FastAPI backend (:8000)
        |
        +-- API / auth / middleware
        +-- Services --> Repositories --> PostgreSQL or SQLite
        +-- LangGraph workflow --> specialist agents
        |       +-- registered tools --> mock integrations
        |       +-- RAG --> Qdrant or in-memory vector store
        |       +-- short-term memory --> Redis or fakeredis
        |       +-- long-term memory --> customer_memory table
        +-- LLM provider factory (fake by default; external providers optional)
        +-- Workflow tracer --> workflow_events
```

In the offline demo, SQLite, fakeredis, the in-memory vector store, and the fake LLM
avoid external service and API-key requirements. Production-compatible providers are
selected through configuration. The browser never receives a service-role key.

## Layer ownership

| Layer | Owns | Must not |
|---|---|---|
| `frontend/` | App Router UI, typed API client, role-aware controls | Call backend outside `lib/api.ts` or hold service credentials |
| `backend/app/api/` | HTTP parsing, validation, authentication, RBAC, response codes | Own business rules or call SQL directly |
| `backend/app/services/` | Orchestration of repositories, graph, and integrations | Depend on HTTP request/response behavior |
| `backend/app/repositories/` | SQLAlchemy persistence and queries | Call LLMs |
| `backend/app/core/` | Settings, auth, logging, middleware, database, cache, guardrails, observability | Import `agents/` |
| `backend/app/tools/` | Async tools, registry, permission and approval policy | Execute outside `ToolRegistry` |
| `agents/` | Workflow state, graph, nodes, specialist decisions and prompts | Write SQL directly or bypass registered tools |
| `rag/` | Article loading, chunking, vector stores, hybrid retrieval | Depend on ticket-domain services |
| `memory/` | Short- and long-term memory facades | Persist secrets or raw ticket bodies |
| `integrations/` | Protocols, mock adapters, and MCP interfaces | Be imported by core |

## Ticket workflow

```text
Ticket API
  -> create workflow run (202 + workflow_id)
  -> background workflow
     understand_ticket
     -> classify_severity
     -> customer_context
     -> knowledge_retrieval
     -> troubleshooting
     -> resolution_planning
     -> risk_check
        -> escalation (policy/risk)
        -> human_approval (consequential action)
        -> execute_resolution (low risk)
     -> ticket_summary
     -> memory_update
  -> END
```

The workflow saves state after each node. A pending approval interrupts the graph and
records an approval request; an agent decision resumes the same run. Rejection routes
to escalation. The customer-facing reply is sent only through the separate reply
endpoint after output validation. All integrations remain mocks in v1.

## Request and trust boundaries

- CORS wraps request-ID, rate-limit, and audit middleware in the order specified by
  `CLAUDE.md`. Every response exposes `X-Request-ID`.
- API routes enforce `viewer < agent < admin` server-side. UI controls are not an
  authorization boundary.
- Ticket text and retrieved content are untrusted data, even when they contain
  instruction-like language. Prompt injection must not change policy or tool access.
- Policy rules decide disputes, deletion, security, data loss, legal cases, and
  enterprise outages. The model supplies judgment only for non-policy ambiguity.
- Tool calls execute through the registry. Unknown tools and consequential actions
  require approval.
- Customer output is validated before display/send. Logs, workflow events, and memory
  must not expose secrets, raw prompts, hidden reasoning, or another customer's data.

## Persistence and observability

- SQLAlchemy models use portable JSON and `String(36)` UUIDs for SQLite/Postgres.
- PostgreSQL DDL, RLS policies, and additive migrations live in `database/`.
- `workflow_runs` store resumable workflow state; `workflow_events` expose node, tool,
  model, approval, error, and completion metadata.
- Redis/fakeredis stores short-lived conversation/workflow state and retrieval cache;
  long-term, scrubbed notes live in `customer_memory`.
- Provider-specific implementations sit behind the vector-store, integration, and LLM
  provider interfaces.

## Deployment shape

The intended container stack is the Next.js frontend and FastAPI backend, with Redis
and Qdrant as optional services. Cloud roots in `deployment/aws/`, `deployment/azure/`,
and `deployment/gcp/` compose shared infrastructure modules. Cloud credentials and
live deployment are outside offline validation; do not claim an apply or deployment
until it has actually happened.
