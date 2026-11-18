# CloudDesk Support — Phase plan

This is the phase exit-criteria plan required by `CLAUDE.md`. The specification in
`CLAUDE.md` takes precedence over this file; `TASK.md` is the execution checklist and
may split or reorder implementation tasks to satisfy dependencies. Update `MEMORY.md`
when a phase's status changes.

## Status

| Phase | Name | Status |
|---|---|---|
| 1 | Runtime skeleton | In progress |
| 2 | Persistence and demo data | Complete |
| 3 | Identity and request guards | Not started |
| 4 | Support API | Complete |
| 5 | Knowledge pipeline | In progress |
| 6 | Tools and policy | In progress |
| 7 | Rules and guardrails | Not started |
| 8 | Specialist agents | Not started |
| 9 | Workflow graph and trace | Not started |
| 10 | Approval and escalation | Not started |
| 11 | Memory | Not started |
| 12 | Agent console | Not started |
| 13 | Evaluation and delivery | Not started |

Statuses describe verified repository work, not planned or locally claimed work. Keep
the status table in this file and the honest-status section of `MEMORY.md` synchronized.

## Phase 1 — Runtime skeleton

**Goal:** Establish configuration, logging, health checks, request IDs, and a fully
offline test entry point.

- **Dependencies:** None.
- **Scope:** `backend/app/core/`, `backend/app/middleware/`, health routes, `tests/`,
  `Makefile`, `.env.example`, and `pyproject.toml`.
- **Requirements:** F14, N3.
- **Tests:** Configuration and log redaction; health liveness/readiness; request ID
  propagation including error responses; offline test harness.
- **Demo checkpoint:** `make test` works offline. A full ticket demo is not available
  until the workflow is implemented.
- **Exit criteria:** Settings load from environment, JSON logs omit secrets and carry
  request/workflow context, `/health` and `/health/live` do no dependency I/O,
  `/health/ready` reports degraded dependencies, and every response carries
  `X-Request-ID`.

## Phase 2 — Persistence and demo data

**Goal:** Define portable entities, repositories, database DDL, migrations, and the
offline demo data bootstrap.

- **Dependencies:** Phase 1.
- **Scope:** `backend/app/models/`, `backend/app/repositories/`, `database/`,
  `sample_data/`, database startup and seed services.
- **Requirements:** Data foundations for F1, F4, F11, N6, N7.
- **Tests:** SQLite model/repository tests; schema and migration checks; bootstrap
  idempotence and expected sample counts.
- **Demo checkpoint:** Seed and inspect the demo database without network access.
- **Exit criteria:** SQLAlchemy models work on SQLite and Postgres, DDL and models
  agree, migrations are additive, and demo bootstrap loads the specified customers,
  tickets, and related records only when appropriate.

## Phase 3 — Identity and request guards

**Goal:** Protect APIs with role-based JWT authentication, rate limiting, and audit
logging.

- **Dependencies:** Phases 1 and 2.
- **Scope:** `backend/app/core/security.py`, authentication routes, middleware, and
  associated tests.
- **Requirements:** N1, N2, N6.
- **Tests:** Token validation/expiry; viewer, agent, and admin permissions; fixed-window
  rate-limit behavior; audit rows for state-changing requests.
- **Demo checkpoint:** Demo users can authenticate locally; viewer write attempts
  receive 403.
- **Exit criteria:** HS256 JWTs are validated, role ordering is enforced server-side,
  the demo tokens expire after eight hours, and middleware ordering matches
  `CLAUDE.md`.

## Phase 4 — Support API

**Goal:** Publish the ticket and customer APIs against the shared contract.

- **Dependencies:** Phases 2 and 3.
- **Scope:** `docs/API_CONTRACT.md`, `backend/app/api/`, `backend/app/schemas/`,
  `frontend/lib/types.ts`, and repository-backed services.
- **Requirements:** F1, F4; read permissions for F12.
- **Tests:** Ticket creation and retrieval, customer detail/history, validation,
  missing-resource responses, and role access.
- **Demo checkpoint:** Create and read a ticket through the API using seeded data.
- **Exit criteria:** Implemented route payloads match the contract, API handlers contain
  no business rules or direct SQL, and contract/schema/frontend types are synchronized.

## Phase 5 — Knowledge pipeline

**Goal:** Ingest support articles and provide offline-capable hybrid retrieval.

- **Dependencies:** Phase 2.
- **Scope:** `rag/`, `sample_data/knowledge_base/`, knowledge API, and reindex command.
- **Requirements:** F5, F6.
- **Tests:** Article parsing/chunking; vector-store behavior; retrieval modes, fusion,
  reranking, caching, and article-level deduplication; retrieval hit-rate@3 >= 0.75.
- **Demo checkpoint:** Ingest and retrieve articles with fake embeddings and no external
  services.
- **Exit criteria:** Chunks carry article/section provenance, hybrid retrieval combines
  semantic and keyword results, evidence matches the contract, and reindex requires
  admin access.

## Phase 6 — Tools and policy

**Goal:** Establish the single registry path for read and write tools, including
approval policy and mock integrations.

- **Dependencies:** Phase 2.
- **Scope:** `backend/app/tools/`, `integrations/`, and tool tests.
- **Requirements:** F9 and the action controls in F8/F10.
- **Tests:** Registry-only execution, unknown-tool approval, timeout/error results,
  mock adapter behavior, and approval-required write actions.
- **Demo checkpoint:** Exercise tools against mocks with no real email, refund, or
  account changes.
- **Exit criteria:** Every tool is asynchronous and registered; consequential actions
  require approval; failures are explicit `ToolResult` failures and do not crash the
  graph.

## Phase 7 — Rules and guardrails

**Goal:** Make deterministic policy and safe handling of untrusted content available
before model-assisted decisions.

- **Dependencies:** Phase 2.
- **Scope:** `agents/rules.py`, `backend/app/core/guardrails.py`, prompt security
helpers, and focused tests.
- **Requirements:** F3, F10, N4, N5, N7.
- **Tests:** Severity rules only raise severity; policy escalation cases override model
judgment; injection containment; customer-output validation; secret scrubbing.
- **Demo checkpoint:** Verify policy outcomes for the specified security, data-loss,
deletion, dispute, and injection tickets using deterministic fixtures.
- **Exit criteria:** Policy cases are decided by rules; ticket-supplied content remains
untrusted data; invalid customer output raises risk; secrets are scrubbed before
memory persistence.

## Phase 8 — Specialist agents

**Goal:** Implement structured, testable specialist agents and an offline fake LLM.

- **Dependencies:** Phases 5, 6, and 7; repository-backed customer context from Phase 2.
- **Scope:** `agents/specialists/`, `agents/prompts.py`, workflow schemas, fake LLM
  provider, and evaluation cases.
- **Requirements:** F2–F8, F10.
- **Tests:** One focused test per specialist; structured output validation; fake-provider
  behavior; initial classification, escalation, citation, and grounding evaluations.
- **Demo checkpoint:** Run specialists individually in offline tests. The complete
  `make demo` remains an exit gate for Phase 10.
- **Exit criteria:** Agents return their Pydantic output models, call models only via
  `call_structured`, use registered tools, and add no SQL or side effects in the agent
  layer.

## Phase 9 — Workflow graph and trace

**Goal:** Compose the ticket pipeline into a resumable graph and make node/tool/model
activity inspectable.

- **Dependencies:** Phase 8.
- **Scope:** `agents/state.py`, `agents/graph.py`, `agents/nodes/`,
  `agents/checkpointer.py`, workflow services and events API.
- **Requirements:** F11, F13; workflow execution for F14.
- **Tests:** Graph shape and routing; reducer behavior; node persistence; event shape,
  timing and token aggregation; offline low-risk workflow.
- **Demo checkpoint:** Run a low-risk ticket through the graph and inspect workflow
  state and events.
- **Exit criteria:** Every node returns partial state, reducers append/sum as specified,
  state persists after every node, and telemetry never breaks the workflow.

## Phase 10 — Approval and escalation

**Goal:** Pause consequential workflows for human decisions and route policy cases to
named teams.

- **Dependencies:** Phases 6, 7, and 9.
- **Scope:** Approval and escalation services/routes, graph interrupt/resume paths,
  shared resolution execution, and demo command.
- **Requirements:** F9, F10, F14.
- **Tests:** Refund pause/approve, rejection-to-escalation, policy auto-escalation,
  duplicate-run and invalid-resume 409s, and end-to-end demo behavior.
- **Demo checkpoint:** `make demo` pauses on CD-1002 for approval and escalates CD-1005
  by policy, fully offline.
- **Exit criteria:** No consequential action runs without recorded approval, rejection
  follows the escalation path, policy rules win over model judgment, and all actions
  use the shared registry path.

## Phase 11 — Memory

**Goal:** Provide short-term workflow storage and safe, de-duplicated customer memory.

- **Dependencies:** Phases 2 and 7; graph integration in Phase 9.
- **Scope:** `memory/`, `customer_memory` repository operations, and graph memory nodes.
- **Requirements:** F4, F11, N7.
- **Tests:** Redis/fakeredis TTL and cache keys; recall limits; de-duplication; secret
  scrubbing; memory update after completed workflows.
- **Demo checkpoint:** Complete a demo run and verify a safe summary is recalled on a
  subsequent run.
- **Exit criteria:** Short-term TTLs match the spec, up to 10 long-term notes are
  recalled, each completed run records only scrubbed permitted notes, and raw ticket
  bodies or other customers' data are never stored.

## Phase 12 — Agent console

**Goal:** Deliver the role-aware support console and ticket workflow screen.

- **Dependencies:** Phases 3 and 4 for the shell; Phases 9–11 for workflow detail and
  actions.
- **Scope:** `frontend/`, typed API client, navigation, ticket/customer/knowledge
  screens, and frontend tests.
- **Requirements:** F12 and read-side UI for F5/F6/F13.
- **Tests:** API helpers, role-aware controls, polling and workflow steps, action
  visibility, and a browser pass of the ticket screen.
- **Demo checkpoint:** An agent can inspect a ticket, run its workflow, review evidence
  and actions, and approve/reject or reply as permitted.
- **Exit criteria:** Backend access goes through the typed API client; viewers cannot
  perform agent actions; approval buttons appear only for pending approvals; the screen
  exposes workflow progress without exposing prompts, secrets, or other customers'
  data.

## Phase 13 — Evaluation and delivery

**Goal:** Enforce quality thresholds and provide reproducible container and deployment
scaffolding.

- **Dependencies:** Phases 1–12.
- **Scope:** `tests/evaluation/`, `tests/deployment/`, Docker/Compose, CI workflows,
  Terraform roots/modules, deployment scripts, and operational documentation.
- **Requirements:** N8 and project-wide acceptance criteria.
- **Tests:** Evaluation thresholds; Docker/Compose hygiene; environment coverage;
  Terraform validation; no committed secrets; offline backend and frontend suites.
- **Demo checkpoint:** Repeat `make test`, `make demo`, frontend checks, and
  `docker compose config -q` where tooling is available.
- **Exit criteria:** Classification >= 0.80, retrieval hit-rate@3 >= 0.75, escalation
  correctness >= 0.90, citation rate >= 0.90, grounding rate >= 0.90; delivery checks
  pass locally. Cloud apply and GitHub CI status remain explicitly unclaimed until
  actually performed.

## Cross-phase gates

- Every F/N requirement in `PLAN.md` maps to at least one test before project completion.
- API changes update `docs/API_CONTRACT.md`, backend schemas, and frontend types together.
- Offline tests use the fake LLM, memory vector store, fake Redis, and temporary SQLite.
- `make demo` must remain functional after Phase 10; Phase 13 repeats it as a final gate.
- Never describe a cloud deployment or CI run as successful until it has actually run.
