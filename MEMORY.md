# MEMORY.md — CloudDesk Project 1

Durable facts for this repository. `CLAUDE.md` wins if this file drifts. Update this file when a decision, demo fact, or delivery status changes. Do not store secrets, customer payloads, or raw ticket bodies here.

## Product

- Fictional SaaS: **CloudDesk** (team collaboration, cloud file storage, billing, workspaces, API access).
- Users of this product are **support agents**. Customers do not use the console in v1.
- Pipeline for every ticket: Understand → Classify → Investigate → Retrieve → Troubleshoot → Decide → Resolve → Act → Escalate → Remember.
- v1 integrations are mocks. The product does not send real email and does not issue real refunds.
- v1 is English-only and has no customer-facing chat widget.
- Business metrics are tracked, never hard-coded: percent of tickets resolved without a human edit, median time to first response, escalation precision, refund approvals per week. Refunds are never zero-touch.

## Locked decisions

- Three tiers: Next.js 15 on `:3000`, FastAPI on `:8000`, then PostgreSQL/SQLite, Redis/fakeredis, Qdrant/in-memory, and `get_llm`.
- The workflow is a LangGraph graph in `agents/graph.py` with six specialists.
- Demo runtime is offline: `LLM_PROVIDER=fake`, `VECTOR_STORE=memory`, `USE_FAKE_REDIS=true`, SQLite, `InMemorySaver` when `CHECKPOINT_DB_PATH=:memory:`.
- SQLAlchemy models stay portable: JSON columns, `String(36)` UUIDs, same code on SQLite and Postgres.
- Postgres DDL in `database/schema.sql` is the cloud schema. SQLite tables are created at startup.
- The backend uses the service-role key on the server. The browser receives only the anon key.
- JWT is HS256. Demo tokens expire in 8 hours.
- Background workflows run in-process for v1.
- Image tags equal the git SHA once delivery exists. Nothing has been built or tagged yet.
- Stage 17 (Agentic DevOps) is optional and depends on stages 13–16. It is outside core Project 1 completion.
- 2026-10-25 — F14 / observability: process settings are `get_settings()` in `backend/app/core/config.py` (cached). JSON logs come from `setup_logging()` and `log_context()` in `backend/app/core/logging.py`. Every line includes `request_id` and `workflow_id` (`null` when unset). `model_dump()` redacts secrets and URL passwords; connection code reads the attributes.
- 2026-11-16 — P1-2 / N3: `RequestIdMiddleware` accepts only safe, bounded `X-Request-ID` values, otherwise assigns a UUID, binds `log_context`, and adds the ID to HTTP responses including preflight, 404, and 500. CORS exposes the response header. `/health` and `/health/live` do no dependency I/O. `/health/ready` checks configuration only until database, Redis, vector-store, and LLM clients are implemented; it never returns connection details or secrets.
- 2026-11-17 — P1-3 / F14: `tests/conftest.py` forces deterministic offline test settings before app imports, with in-memory SQLite/checkpoint storage, fake providers, and in-memory vector/Redis settings. Pytest config enables automatic asyncio mode with a session-scoped fixture loop.
- 2026-11-17 — P2-1 / data foundation: portable SQLAlchemy 2 entities are defined in `backend/app/models/entities.py`, with the ten-value `Category` enum plus shared severity, status, channel, and role enums in `backend/app/schemas/common.py`; SQLite table creation was verified locally.
- 2026-11-17 — P2-2 / PostgreSQL persistence: `database/schema.sql` and migration `0001_initial_schema.sql` define all 16 model tables and update-time triggers. `database/rls_policies.sql` and migration `0002_enable_rls.sql` grant authenticated support roles read-only access; writes remain server-side through `service_role`.
- 2026-11-17 — P2-3 / repository layer: async SQLAlchemy repositories cover all 16 mapped entities, keep transaction commits with their caller, and provide customer/ticket/workflow/catalog/audit queries. SQLite async CRUD and query behavior is covered by focused tests.
- 2026-11-18 — P2-4 / demo bootstrap: deterministic fixtures provide three demo profiles, eight customers and related records, thirteen scenario tickets/messages, products, and an active incident. Startup creates tables and seeds only an empty database when `DEMO_MODE=true`; PostgreSQL seed SQL is generated from the same fixtures.
- 2026-11-18 — P4-1 / support API contract: ticket creation and ticket/customer response shapes are defined in Pydantic schemas and mirrored in `docs/API_CONTRACT.md` and `frontend/lib/types.ts`. Ticket creation requires exactly one of `customer_id` or `customer`; P4-2 and P4-3 routes remain pending.
- 2026-11-18 — P4-2 / ticket API: repository-backed list, detail, and create routes are implemented with viewer/agent RBAC. Creation links or creates a customer, validates workspace ownership, creates the original customer message, assigns the next `CD-*` number, and commits atomically. P4-3 customer routes remain pending.
- 2026-11-18 — P4-3 / customer API: repository-backed viewer-readable customer list, detail/context, and ticket-history routes are implemented. Customer detail exposes subscriptions, workspaces, newest tickets, and up to ten memory notes with secret/card redaction; history uses customer-scoped pagination.
- 2026-11-18 — P5-2 / vector store and fake embeddings: deterministic 384-dimension hashed bag-of-words `FakeEmbeddings`, the async vector-store protocol, in-memory cosine-search storage, and a configurable Qdrant adapter are implemented. Focused tests cover deterministic vectors, document order, filtering, delete/count, explicit vectors, and memory/Qdrant factories.
- 2026-11-18 — P5-3 / hybrid retriever: semantic and BM25 keyword retrieval are combined with reciprocal-rank fusion (`k=60`), title/category heuristics, category filters, article-level deduplication, optional validated reranking, and a bounded 300-second cache. Its original tests used synthetic documents; P5-4 now exercises retrieval against the restored P5-1 fixtures. No live Qdrant or LLM reranker was used.
- 2026-11-18 — P5-1 and P5-4 / knowledge content and API: restored the chunker, tests, and 15 Markdown articles previously deleted by the P5-2 commit; added deterministic vector ingestion, startup initialization, the offline CLI, and viewer/admin-protected knowledge list/detail/search/reindex endpoints. The offline command indexed 15 articles into 45 chunks.
- 2026-11-21 — P10-3 / investigate graph nodes: implemented `customer_context`, `knowledge_retrieval`, and `troubleshooting` as resilient LangGraph partial-state nodes. The nodes load customer context and memory, retrieve cited evidence plus resolved cases, and produce numbered diagnosis state through existing specialists and registered tools. Focused workflow tests pass offline.
- 2026-11-21 — P10-4 / resolution and risk graph nodes: implemented `resolution_planning` and `risk_check` in `agents/nodes/resolution.py`. Resolution planning creates grounded plans and deterministic approval-gated actions through `ResolutionAgent`; risk checking raises high risk for consequential actions, policy matches, critical severity, prompt injection, or invalid customer output. Focused node and specialist tests pass offline.

## Roles

Enforced by `require_role` in `backend/app/core/security.py` (`viewer 1 < agent 2 < admin 3`).

| Role     | Access                                                                 |
| -------- | ---------------------------------------------------------------------- |
| `viewer` | Read tickets, customers, knowledge, and audit                          |
| `agent`  | Viewer access, plus run workflows, reply, approve/reject, and escalate |
| `admin`  | Agent access, plus reindex knowledge and settings                      |

Demo users: `admin@clouddesk.demo`, `sam.agent@clouddesk.demo`, `vic.viewer@clouddesk.demo`.

## Domain constants

Categories, exactly these ten, defined first in `backend/app/schemas/common.py`:

`login_issue`, `billing`, `api_failure`, `workspace_permissions`, `storage_quota`, `integration`, `feature_request`, `account`, `security`, `other`.

- Statuses: `new`, `in_progress`, `waiting_on_customer`, `waiting_on_approval`, `escalated`, `resolved`, `closed`.
- Severity: `low`, `medium`, `high`, `critical`.
- Channels: `email`, `chat`, `web`, `api`.
- Plans in the demo set: free, pro, business, enterprise. Eight customers. Thirteen tickets.

| Ticket  | What it must exercise                                    |
| ------- | -------------------------------------------------------- |
| CD-1001 | Login issue, active incident, enterprise                 |
| CD-1002 | Billing refund; approval gate on `create_refund_request` |
| CD-1003 | API 429; rate-limit docs                                 |
| CD-1004 | Storage quota and subscription limits                    |
| CD-1005 | Security; policy escalation                              |
| CD-1006 | Data loss; policy escalation                             |
| CD-1007 | Workspace permissions                                    |
| CD-1008 | Integration failure                                      |
| CD-1009 | Account deletion / GDPR; policy escalation               |
| CD-1010 | Feature request; low severity by policy                  |
| CD-1011 | Payment dispute; policy escalation                       |
| CD-1012 | MFA recovery article                                     |
| CD-1013 | Prompt injection; ticket text stays data                 |

Policy cases that rules decide, and the model must not override: dispute, deletion, security, data loss, legal, enterprise outage.

## Workflow facts

Graph order:

`understand_ticket` → `classify_severity` → `customer_context` → `knowledge_retrieval` → `troubleshooting` → `resolution_planning` → `risk_check`, then either `escalation`, `human_approval`, or `execute_resolution`, then `ticket_summary` → `memory_update` → END.

- `human_approval` calls `interrupt()`. Resume uses `Command(resume=…)`.
- Rejection of an approval routes to escalation.
- Node ids are the `completed_nodes` values the UI renders.
- `GET /api/v1/agents` is fed by `GRAPH_NODES` / `GRAPH_EDGES`.
- A second run while status is `waiting_on_approval` returns 409. Resuming a run that is not paused returns 409.
- `WorkflowTracer` never raises. Event names: `node_started`, `node_completed`, `tool_called`, `llm_called`, `approval_requested`, `approval_resolved`, `error`, `workflow_completed`.
- Exposed to operators: decisions, tool calls and results, evidence with scores, node timings, token counts, errors.
- Hidden: raw prompts, hidden chain-of-thought, other customers’ data, secrets.

Tools:

| Tool                                                     | Writes          | Approval |
| -------------------------------------------------------- | --------------- | -------- |
| `get_customer`, `get_subscription`, `get_ticket_history` | no              | no       |
| `search_docs`, `check_service_status`                    | no              | no       |
| `update_ticket`                                          | tickets         | no       |
| `reset_demo_setting`                                     | workspace admin | yes      |
| `create_refund_request`                                  | billing         | yes      |
| `create_escalation`                                      | escalations     | no       |

Unknown tools require approval. Timeout is `TOOL_TIMEOUT_SECONDS`.

## RAG and memory facts

- Knowledge source: `sample_data/knowledge_base/*.md` (15 articles) with YAML front-matter `title`, `category`, `tags`, `summary`.
- Chunk on headings, then 900-character windows with 150-character overlap. Prefix each chunk with `"{title} - {heading}"`.
- Retrieval: semantic ∪ BM25 → reciprocal rank fusion (`k=60`) → heuristic rerank → optional LLM rerank → one hit per article.
- Modes: `hybrid` (default), `semantic`, `keyword`.
- Fake embeddings: hashed bag-of-words, 384 dimensions. Changing the embedding model requires admin `POST /knowledge/reindex`, which recreates the collection.
- Evidence fields: `id`, `title`, `source` (`kb://slug#section`), `snippet`, `score`, `url` (`/knowledge/<id>`), `article_id`.
- Customer-facing policy claims cite knowledge articles.
- Short-term memory TTL is 24 hours. Retrieval cache TTL is 300 seconds. Cache key shape: `rag:{mode}:{category}:{top_k}:{query}`.
- Long-term note types: `preference`, `past_issue`, `troubleshooting`, `note`. Recall up to 10 notes. After a run, store the past issue, the first three troubleshooting steps, and a resolution note.
- `SECRET_PATTERNS` covers card numbers, API keys, and passwords.

## Evaluation bar

These fail the build: classification accuracy ≥ 0.80, retrieval hit-rate@3 ≥ 0.75, escalation correctness ≥ 0.90, citation rate ≥ 0.90, grounding rate ≥ 0.90.

Cases live in `datasets/eval_cases.json` and each case needs a valid `expected_category`.

## Environment defaults worth remembering

- `APPROVAL_REQUIRED_FOR_REFUNDS=true`, `MAX_REFUND_WITHOUT_APPROVAL=0`.
- Demo rate limit: `RATE_LIMIT_PER_MINUTE=120`.
- `QDRANT_COLLECTION=clouddesk_knowledge`.
- `get_settings()` is cached. A `.env` change requires a server restart.
- RequestIdMiddleware wraps the CORS-enabled FastAPI app so request IDs also cover preflight/error responses; rate-limit and audit middleware remain inside that wrapper.
- Health: `/health`, `/health/live` (no I/O), `/health/ready` (db, redis, vector store, llm).

## Honest status

Update each row in place. Do not mark a row done from intention.

| Surface                   | State on 2026-11-19                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Repository contents       | P1 through P5 implementations plus P6-1, P6-2, and P6-4 are present locally. P5 includes the restored article/chunk implementation, vector stores, hybrid retrieval, ingest command, and knowledge API. P6-1 provides tool registry and approval policy; P6-2 provides registered read-only support tools; P6-4 provides mock integration protocols, adapters, and factory.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| Implemented               | P1 provides settings, logging, health, request IDs, offline pytest, Makefile and environment template work. P2 provides SQLAlchemy entities, PostgreSQL schema/RLS/migrations, repositories, fixtures and demo seeding. P3 provides JWT/RBAC, demo auth, Redis/fakeredis limiting and audit middleware. P4 provides ticket/customer contracts and repository-backed APIs. P5 provides 15 knowledge articles and chunking, fake embeddings and in-memory/Qdrant vector stores, semantic/BM25 retrieval, ingestion, and knowledge list/detail/search/reindex routes. P6-1 provides asynchronous registry-only tool execution, timeout/error results, and approval policy for unknown, reset, and refund actions. P6-2 provides registry-backed customer, subscription, ticket-history, knowledge-search, and service-status tools. P6-4 provides mock billing, email, service-status, and workspace-admin integrations. P6-3 remains unimplemented. |
| Validated locally         | Full offline suite: 125 passed. Focused Ruff checks and Pylance diagnostics pass for the new tool and integration code; Pylance resolves `langchain_core` in the project environment. The `python -m backend.app.cli.ingest_knowledge` command indexed 15 articles into 45 chunks. Qdrant reset behavior was tested with a stub; no live Qdrant service, LLM reranker, or PostgreSQL database was used. The P5 retrieval hit-rate threshold has not been measured because no evaluation dataset/suite is present. `.env.example` contains every `Settings` field. GNU Make is unavailable in this environment, so targets were validated by running underlying commands directly rather than invoking `make`. `make demo` does not exist yet.                                                                                                                                                                                                     |
| Cloud credentials         | None used.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| Applied to a real account | Nothing.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| GitHub Actions            | Workflow files are not in the repo. None have been executed.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| Phase plan                | Phase 1 remains in progress pending GNU Make invocation verification. Phase 2 persistence and demo data is complete locally (P2-1 through P2-4). Phase 3 and Phase 4 tasks are implemented locally. P5-1 through P5-4 are implemented locally; Phase 5 remains in progress until its retrieval hit-rate threshold is evaluated. P6-1, P6-2, and P6-4 are implemented and validated locally; Phase 6 remains in progress pending P6-3 and its exit criteria.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| Repository contents       | P1 through P5 implementations, P6-1, and P6-4 are present locally. P5 includes the restored article/chunk implementation, vector stores, hybrid retrieval, ingest command, and knowledge API. P6-1 adds the tool registry and approval policy; P6-4 adds mock integration protocols, adapters, and factory. The current P6-4 changes are local; no merge or deployment is claimed.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| Implemented               | P1 provides settings, logging, health, request IDs, offline pytest, Makefile and environment template work. P2 provides SQLAlchemy entities, PostgreSQL schema/RLS/migrations, repositories, fixtures and demo seeding. P3 provides JWT/RBAC, demo auth, Redis/fakeredis limiting and audit middleware. P4 provides ticket/customer contracts and repository-backed APIs. P5 provides 15 knowledge articles and chunking, fake embeddings and in-memory/Qdrant vector stores, semantic/BM25 retrieval, ingestion, and knowledge list/detail/search/reindex routes. P6-1 provides asynchronous registry-only tool execution, timeout/error results, and approval policy for unknown, reset, and refund actions. P6-4 provides asynchronous protocols and isolated mock adapters for billing requests, workspace settings, service status, and email; all effects remain local simulations. P6-2 and P6-3 remain unimplemented.                     |
| Validated locally         | Full offline suite: 120 passed with one third-party deprecation warning. Ruff checks pass for the tool and integration implementations and their tests. The `python -m backend.app.cli.ingest_knowledge` command indexed 15 articles into 45 chunks. Qdrant reset behavior was tested with a stub; no live Qdrant service, LLM reranker, or PostgreSQL database was used. The P5 retrieval hit-rate threshold has not been measured because no evaluation dataset/suite is present. `.env.example` contains every `Settings` field. GNU Make is unavailable in this environment, so targets were validated by running underlying commands directly rather than invoking `make`. `make demo` does not exist yet.                                                                                                                                                                                                                                   |
| Cloud credentials         | None used.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| Applied to a real account | Nothing.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| GitHub Actions            | Workflow files are not in the repo. None have been executed.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| Phase plan                | Phase 1 remains in progress pending GNU Make invocation verification. Phase 2 persistence and demo data is complete locally (P2-1 through P2-4). Phase 3 and Phase 4 tasks are implemented locally. P5-1 through P5-4 are implemented locally; Phase 5 remains in progress until its retrieval hit-rate threshold is evaluated. P6-1 and P6-4 are implemented and validated locally; Phase 6 remains in progress pending P6-2, P6-3, and its exit criteria.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |

## Open questions from `CLAUDE.md` §20

- A Project 1 `README.md` was referenced by the course and was not supplied. Command names in `CLAUDE.md` §14 still need to be checked against it when it appears.
- Course paths `../docs/`, `../deployment-agent/`, and `../shared-infrastructure/` sit outside this repo. They are not copied in yet.
- Table counts disagree across the course notes (16 in the database doc, 15 data tables in the RLS note). `database/schema.sql` becomes the authority once it is written.
- Stage documents 00–17 are not in this repo. `PLAN_PHASE.md` is derived from `CLAUDE.md`, not from those missing files.

## Update protocol

- Record a new locked decision with the date and the requirement id it serves.
- When a phase exits, set its status in `PLAN_PHASE.md` and add one line here under Honest status.
- When a demo ticket’s expected behaviour changes, change the ticket table above and the matching test together.
- Leave secrets, tokens, connection strings, and ticket bodies out of this file.
