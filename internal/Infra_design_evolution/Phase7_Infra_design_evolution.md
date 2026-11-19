# Phase 7 — Infrastructure, Component Wiring, and Routing Evolution

This document explains how the Phase 7 rules and guardrail components connect
to the CloudDesk application process. It covers module dependencies, prompt
assembly boundaries, customer-memory routing, and test wiring. It also clearly
separates implemented in-process behavior from Docker and container networking,
which are not configured in this repository.

## Infrastructure status at the end of Phase 7

Phase 7 adds Python modules and in-process function calls. It does not add a
new server, API route, network listener, database table, queue, or external
service.

The guardrails are loaded as ordinary Python code in the FastAPI process or in
unit-test processes. The rules module, prompt module, guardrail module, customer
service, and future agents are all connected through imports and function calls.

| Component | Implemented Phase 7 connection |
|---|---|
| Deterministic policy | In-process functions in `agents/rules.py` |
| Injection and text guardrails | In-process functions in `backend/app/core/guardrails.py` |
| Shared prompt preamble | In-process constant exported by `agents/prompts.py` |
| Customer-memory scrub | In-process `scrub()` call from `CustomerService` |
| Workflow integration | Not mounted yet; functions are reusable library components |
| HTTP routes | Existing routes remain unchanged; no Phase 7 route was added |
| Database | No Phase 7 table or migration was added |
| External services | No real model or external guardrail provider is called |
| Docker / Compose | No Dockerfile or Compose network is present |

The Phase 7 components share one Python process and do not need network routing
to communicate.

## Wiring progression

```mermaid
flowchart LR
    P71["P7-1<br/>Policy rule modules"]
    P72["P7-2<br/>Prompt input guardrails"]
    P73["P7-3<br/>Customer output validation"]
    P74["P7-4<br/>Memory secret scrubbing"]

    P71 --> Final["Rules-first application boundary"]
    P72 --> Final
    P73 --> Final
    P74 --> Final
```

P7-1 supplies policy decisions. P7-2 protects prompt construction. P7-3 protects
generated output. P7-4 protects memory text before it is returned or reused.

## Starting point — Phase 6 application without the Phase 7 policy layer

Before Phase 7, the application process already contains middleware, API
routers, repositories, a knowledge service, a tool registry, and mock
integrations.

The future agent layer can call these components, but there is no shared policy
module or text-safety boundary among it.

```mermaid
flowchart LR
    Client["HTTP or future workflow caller"]
    Client --> FastAPI["FastAPI process"]
    FastAPI --> Routes["Existing API routes"]
    Routes --> Services["Ticket, customer, and knowledge services"]
    Services --> Repositories["Repositories"]
    Repositories --> Database["SQLite or PostgreSQL"]

    FutureAgent["Future support agent"] -. "No P7 policy module" .-> Decision["Proposed decision"]
    Decision -. "No P7 prompt boundary" .-> Text["Ticket or reply text"]
    Text -. "No P7 output gate" .-> Customer["Customer-facing output"]
    Text -. "No P7 scrubbing" .-> Memory["Customer memory"]
```

At this starting point, Phase 6 controls tool execution but does not provide
the complete rules and text-safety boundary needed by the future agent:

- escalation has no dedicated rule module;
- severity has no raise-only policy helper;
- ticket text has no shared wrapping helper;
- customer replies have no structured validation gate;
- memory display has no shared secret scrub API.

## P7-1 — Escalation and severity component wiring

P7-1 adds `agents/rules.py`. It is a library module, not a network service.
Future supervisor or escalation agents import its functions directly.

```mermaid
flowchart LR
    Agent["Future support agent"]
    Agent --> Rules["agents/rules.py"]

    TicketText["Ticket subject and body"] --> Rules
    ModelCategory["Optional model category"] --> Rules
    ModelSeverity["Optional model severity"] --> Rules

    Rules --> Escalation["matching_escalation_rules"]
    Rules --> Category["rule_category"]
    Rules --> Severity["rule_severity"]

    Escalation --> PolicyResult["Policy matches and named teams"]
    Category --> CategoryResult["Final category"]
    Severity --> SeverityResult["Raise-only severity"]
```

The functions share text-normalization and severity-ranking logic inside the
module. They do not open a database session, call an HTTP route, or depend on
FastAPI.

### P7-1 routing flow

```mermaid
sequenceDiagram
    participant Agent as Future specialist agent
    participant Rules as agents/rules.py
    participant Policy as ESCALATION_RULES

    Agent->>Rules: matching_escalation_rules(ticket_text)
    Rules->>Policy: Normalize and compare policy terms
    Policy-->>Rules: Matching rule, team, and severity
    Rules-->>Agent: Structured policy matches

    Agent->>Rules: rule_category(ticket_text, model_category)
    Rules-->>Agent: Deterministic category or valid model category

    Agent->>Rules: rule_severity(ticket_text, model_severity)
    Rules-->>Agent: Model severity raised only if policy requires
```

No service discovery or network address is involved. This module can be tested
with Python text fixtures and runs entirely inside the caller process.

## P7-2 — Injection wrapping and prompt routing

P7-2 adds `backend/app/core/guardrails.py` helpers and
`agents/prompts.py`.

The prompt input path is:

```mermaid
flowchart LR
    Ticket["Ticket text"]
    Ticket --> Scanner["scan_for_injection"]
    Scanner -->|"Detected"| InjectionFlag["Injection flag"]
    Scanner -->|"Not detected"| Normal["Normal support text"]

    Ticket --> Wrapper["wrap_untrusted"]
    Wrapper --> Escaped["Escaped untrusted block"]

    Preamble["SECURITY_PREAMBLE"]
    Preamble --> Prompt["Future prompt builder"]
    Escaped --> Prompt
    Normal --> Prompt
    InjectionFlag --> Prompt
    Prompt --> Model["Future AI model provider"]
```

The preamble and wrapper do not configure or call a model themselves. They
produce text for a future prompt builder.

### P7-2 process boundary

```mermaid
sequenceDiagram
    participant Agent as Future agent
    participant Guard as guardrails.py
    participant Prompt as prompts.py
    participant Model as Future model provider

    Agent->>Guard: scan_for_injection(ticket_text)
    Guard-->>Agent: True or False
    Agent->>Guard: wrap_untrusted(ticket_text)
    Guard-->>Agent: Escaped untrusted-content block
    Agent->>Prompt: Read SECURITY_PREAMBLE
    Prompt-->>Agent: Shared security instructions
    Agent->>Model: Preamble + untrusted block + application data
    Model-->>Agent: Proposed structured result
```

The delimiter escape happens inside `wrap_untrusted()` before text reaches the
prompt. A ticket attempt to close or open `<untrusted_content>` tags is escaped
to text rather than becoming part of the real prompt structure.

P7-2 is an in-process defense. It is not a network firewall or a hosted prompt
injection service.

## P7-3 — Customer output validation routing

P7-3 adds `validate_customer_output()` to the guardrails module.

The intended routing boundary is after a future resolution agent creates a reply
draft and before any HTTP reply or email action is allowed.

```mermaid
flowchart LR
    Resolution["Future resolution agent"]
    Resolution --> Draft["Generated customer reply"]
    Draft --> Validator["validate_customer_output"]

    Context["Allowed and disallowed customer context"]
    Context --> Validator

    Validator -->|"Valid"| Reply["Customer-reply screen or API"]
    Validator -->|"Invalid"| Codes["Structured violation codes"]
    Codes --> Risk["Raise workflow risk"]
    Risk --> Review["Block or route for review"]
```

The validator returns reason codes rather than raising an HTTP exception.
This allows future graph nodes to make explicit routing decisions.

### P7-3 validation sequence

```mermaid
sequenceDiagram
    participant Agent as Future resolution agent
    participant Guard as validate_customer_output()
    participant Workflow as Future risk or reply node

    Agent->>Guard: validate_customer_output(reply, customer context)
    Guard->>Guard: Check empty text
    Guard->>Guard: Check internal URL and private host patterns
    Guard->>Guard: Check secrets and card numbers
    Guard->>Guard: Check other-customer IDs and names
    Guard-->>Agent: is_valid, violation_codes
    alt Valid
        Agent->>Workflow: Allow reply preparation
    else Invalid
        Agent->>Workflow: Block reply and raise risk
    end
```

P7-3 does not currently connect to a route that sends replies. It provides the
library gate that later `POST /tickets/{id}/reply` and workflow code will use.

## P7-4 — Secret scrubbing and memory routing

P7-4 extends `backend/app/core/guardrails.py` with `scrub()` and
`SECRET_PATTERNS`. It also replaces local memory scrubbing in
`backend/app/services/customer_service.py`.

The current route-level integration is the customer detail API:

```mermaid
flowchart LR
    Caller["Support API caller"]
    Caller -->|"GET /api/v1/customers/{id}"| Router["Customer API router"]
    Router --> Middleware["Request, audit, rate limit, CORS"]
    Middleware --> Service["CustomerService"]
    Service --> MemoryRepo["CustomerMemoryRepository"]
    MemoryRepo --> DB["Relational database"]
    DB --> MemoryRepo
    MemoryRepo --> Service
    Service --> Scrub["scrub(note.content)"]
    Scrub --> SafeMemory["[REDACTED] memory text"]
    SafeMemory --> Service
    Service --> Router
    Router --> Caller
```

This means P7-4 scrubbing happens before memory text is placed in the customer
detail response. It is not a database migration or persistent update to stored
notes.

### P7-4 scrubbing sequence

```mermaid
sequenceDiagram
    participant Router as Customer router
    participant Service as CustomerService
    participant Repo as CustomerMemoryRepository
    participant DB as SQLite or PostgreSQL
    participant Guard as scrub()

    Router->>Service: get_detail(customer_id)
    Service->>Repo: list_for_customer(limit=10)
    Repo->>DB: SELECT memory notes
    DB-->>Repo: Raw note content
    Repo-->>Service: Memory records
    loop Each note
        Service->>Guard: scrub(note.content)
        Guard-->>Service: Redacted text
    end
    Service-->>Router: CustomerDetail
    Router-->>Router: Pydantic response serialization
```

The persistent database still may contain the original memory note. P7-4
currently applies scrubbing at the read/display boundary. Later memory-write
code must also call `scrub()` before persistence.

The secret patterns handled in one shared module are:

- private-key blocks;
- password and credential assignments;
- bearer tokens and JWT values;
- URL credentials;
- sensitive query values;
- AWS-style access keys;
- card numbers.

## Test-time component wiring

Phase 7 tests run in isolated Python processes or pytest fixtures.

```mermaid
flowchart LR
    Pytest["pytest"]
    Pytest --> PolicyTest["test_policy_rules.py"]
    Pytest --> InjectionTest["test_guardrail_injection.py"]
    Pytest --> OutputTest["test_customer_output_validation.py"]
    Pytest --> ScrubTest["test_secret_scrub.py"]
    Pytest --> APITest["tests/api/test_customers.py"]

    PolicyTest --> Rules["agents/rules.py"]
    InjectionTest --> Guardrails["backend/app/core/guardrails.py"]
    InjectionTest --> Prompts["agents/prompts.py"]
    OutputTest --> Guardrails
    ScrubTest --> Guardrails
    APITest --> CustomerService["CustomerService"]
    CustomerService --> Guardrails

    Rules --> Assertions["Pass or fail assertions"]
    Guardrails --> Assertions
    Prompts --> Assertions
    CustomerService --> Assertions
```

The tests use in-memory SQLite for API behavior where needed. They do not start
Docker containers, call a live model, or call a real integration.

## Existing HTTP routing

Phase 7 does not add a route. The existing application router order remains:

```mermaid
flowchart LR
    Caller["HTTP client"]
    Caller --> RequestID["Request-ID middleware"]
    RequestID --> Audit["Audit middleware"]
    Audit --> Rate["Rate limit"]
    Rate --> CORS["CORS"]
    CORS --> FastAPI["FastAPI application"]

    FastAPI --> Health["Health routes"]
    FastAPI --> Auth["Auth routes"]
    FastAPI --> Tickets["Ticket routes"]
    FastAPI --> Customers["Customer routes"]
    FastAPI --> Knowledge["Knowledge routes"]

    Customers --> CustomerService["CustomerService"]
    CustomerService --> MemoryScrub["P7-4 scrub()"]
```

No Phase 7 route is mounted under `/api/v1/agents`, `/api/v1/rules`, or a
separate guardrail service. The code is available to future agent nodes and
existing services such as `CustomerService`.

## End-of-Phase 7 component and process view

The final Phase 7 design is a set of in-process policy and safety modules around
the future agent workflow.

```mermaid
flowchart TB
    subgraph Process["One Python/FastAPI or test process"]
        subgraph HTTP["Existing HTTP application"]
            Middleware["Request-ID, audit, rate limit, CORS"]
            Routers["Auth, tickets, customers, knowledge"]
            CustomerService["CustomerService"]
            Middleware --> Routers
            Routers --> CustomerService
        end

        subgraph Policy["P7-1 policy"]
            Rules["agents/rules.py"]
            Escalation["Escalation matches"]
            Category["Category policy"]
            Severity["Raise-only severity"]
            Rules --> Escalation
            Rules --> Category
            Rules --> Severity
        end

        subgraph Prompt["P7-2 prompt safety"]
            Preamble["SECURITY_PREAMBLE"]
            Injection["scan_for_injection"]
            Wrap["wrap_untrusted"]
        end

        subgraph Output["P7-3 output safety"]
            Validate["validate_customer_output"]
            Violation["Violation codes"]
            Validate --> Violation
        end

        subgraph Memory["P7-4 memory safety"]
            Scrub["scrub"]
            Patterns["SECRET_PATTERNS"]
            Scrub --> Patterns
        end

        FutureAgent["Future support and resolution agents"]
        FutureAgent --> Rules
        FutureAgent --> Injection
        FutureAgent --> Wrap
        Wrap --> Preamble
        FutureAgent --> Validate
        CustomerService --> Scrub
    end

    Database["SQLite or PostgreSQL"]
    Model["Future external model provider"]
    Customer["Support caller or customer-facing reply"]

    CustomerService --> Database
    Database --> CustomerService
    Preamble -. "Future prompt content" .-> Model
    Validate -->|"Valid reply"| Customer
    Violation -->|"Invalid reply, future routing"| FutureAgent
```

The solid connections represent implemented imports and function calls.
The model and reply connections are future workflow boundaries, not active
Phase 7 HTTP integrations.

## Component routing summary

| Routing path | Implemented Phase 7 path |
|---|---|
| Ticket policy | Future agent -> `agents/rules.py` -> team/category/severity result |
| Prompt safety | Future agent -> injection scan -> untrusted wrapper -> preamble |
| Reply safety | Future resolution agent -> output validator -> valid or violation result |
| Memory safety | CustomerService -> repository -> database -> `scrub()` -> API response |
| HTTP middleware | Existing Request-ID, audit, rate limit, CORS wrapper |

## Docker networking — not implemented at end of Phase 7

There is no Dockerfile or Compose file in the repository. Phase 7 therefore
does not create or route:

- container service names;
- backend or frontend container ports;
- a Docker or Compose network;
- a guardrail sidecar;
- a separate rules service;
- a prompt-safety microservice;
- a secret-scrubbing worker;
- container volumes or health dependencies.

All guardrails run inside the application or test Python process.

A future container deployment might appear like this:

```mermaid
flowchart LR
    Browser["Browser"]
    Browser -->|"Future HTTPS"| Frontend["Next.js container"]
    Frontend -->|"Future /api/v1"| Backend["FastAPI container"]

    subgraph BackendProcess["Backend container"]
        Rules["P7 rules"]
        Guardrails["P7 guardrails"]
        Agents["Future agent workflow"]
        Rules --> Agents
        Guardrails --> Agents
    end

    Backend --> BackendProcess
    Backend --> Database["PostgreSQL or managed database"]
    Backend --> Redis["Redis"]
    Backend --> Qdrant["Qdrant"]
    Backend --> Model["External LLM provider"]
```

This is a planned topology only. It is not an implemented Docker network in
Phase 7. Container names, ports, health checks, volumes, secrets, and service
DNS should only be documented after Docker and Compose files exist.

## Infrastructure and honest status

Phase 7 is implemented as module-level Python behavior:

- rules and guardrails are importable library components;
- prompt preamble is a shared constant;
- customer memory content is scrubbed by `CustomerService`;
- no HTTP route exposes or bypasses the guardrails;
- no database or external service has been added.

The local offline suite passed 165 tests, and Ruff passed for the relevant
implementation and test files. No live model, live database, Docker container,
cloud service, or real customer data was used.

The future workflow will decide how to compose these modules during graph nodes.
Until that integration exists, there is no Phase 7 production request path
through a rules or guardrail route.

## Implementation references

| Responsibility | Source |
|---|---|
| Escalation, category, and severity rules | [rules.py](../../agents/rules.py) |
| Injection, output, and secret guardrails | [guardrails.py](../../backend/app/core/guardrails.py) |
| Shared prompt security preamble | [prompts.py](../../agents/prompts.py) |
| Memory API scrubbing | [customer_service.py](../../backend/app/services/customer_service.py) |
| FastAPI app and middleware routing | [main.py](../../backend/app/main.py) |
| Policy tests | [test_policy_rules.py](../../tests/unit/test_policy_rules.py) |
| Injection tests | [test_guardrail_injection.py](../../tests/unit/test_guardrail_injection.py) |
| Customer output tests | [test_customer_output_validation.py](../../tests/unit/test_customer_output_validation.py) |
| Secret scrub tests | [test_secret_scrub.py](../../tests/unit/test_secret_scrub.py) |
| Customer API tests | [tests/api/test_customers.py](../../tests/api/test_customers.py) |
| Phase task status | [TASK.md](../../TASK.md) |
| Phase exit criteria | [PLAN_PHASE.md](../../PLAN_PHASE.md) |
| Phase 7 system design evolution | [Phase7_Project_System_Design_Evolution.md](../design_evolution/Phase7_Project_System_Design_Evolution.md) |
| Plain-language Phase 7 explanation | [phase7_explained.md](../explain_codebase/phase7_explained.md) |
