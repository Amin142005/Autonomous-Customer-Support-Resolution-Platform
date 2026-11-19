# Phase 8 — Infrastructure, Component Wiring, and Routing Evolution

This document explains how the Phase 8 memory components connect to the
CloudDesk application process and data stores. It covers the Redis/Fakeredis
selection path, async SQLAlchemy routing, memory service composition, test
wiring, and HTTP boundaries. It also clearly distinguishes this implemented
Python-process architecture from Docker networking, which is not present in
the repository.

## Infrastructure status at the end of Phase 8

Phase 8 adds two memory facades and a composition service. It does not add a
new server, HTTP route, Redis queue, database migration, or container.

The short-term implementation uses Redis or Fakeredis. The long-term
implementation uses the existing SQLAlchemy session and `customer_memory`
table. The memory service receives both dependencies through Python composition.

| Component | Implemented Phase 8 connection |
|---|---|
| Short-term memory | In-process `ShortTermMemory` facade |
| Redis factory | Fakeredis when fake mode or no URL; real Redis when configured |
| Conversations | Redis key `conversation:{ticket_id}` |
| Workflow state | Redis key `workflow:{workflow_id}` |
| Retrieval cache | Redis key `rag:{mode}:{category}:{top_k}:{query}` |
| Long-term memory | In-process `LongTermMemory` facade |
| SQL memory | Existing async SQLAlchemy session and `customer_memory` table |
| Memory repositories | `CustomerMemoryRepository`, `CustomerRepository`, `TicketRepository` |
| Memory service | In-process composition of short-term and long-term facades |
| HTTP routes | Existing customer routes only; no dedicated memory route |
| Docker / Compose | No Dockerfile or Compose network is present |

## Wiring progression

```mermaid
flowchart LR
    P81["P8-1<br/>Redis short-term facade"]
    P82["P8-2<br/>SQL long-term facade"]
    P83["P8-3<br/>Unified memory service"]

    P81 --> Final["Two-tier memory architecture"]
    P82 --> Final
    P83 --> Final
```

P8-1 establishes temporary key and TTL routing. P8-2 establishes SQL
customer-memory routing. P8-3 composes both and records resolution summaries.

## Starting point — Application with data stores but no memory service facade

Before P8-1, the application has a Redis client factory and SQLAlchemy session
factory. Redis is used by the rate limiter, and SQL stores tickets, customers,
and customer-memory records.

It does not yet have the dedicated memory modules that define conversation,
workflow, retrieval-cache, recall, or resolution-memory routing.

```mermaid
flowchart LR
    Caller["Future workflow or application service"]
    Caller -. "No memory facade" .-> Redis["Redis or Fakeredis"]
    Caller -. "No memory facade" .-> SQL["SQLite or PostgreSQL"]

    Redis -. "Used by rate limiter" .-> Rate["Fixed-window rate limiter"]
    SQL --> Tables["Tickets, customers, and customer_memory"]
    Tables --> Caller
```

The existing Redis client is reused only through the core factory. The memory
phase adds a second usage shape on top of that factory.

## P8-1 — Redis short-term component wiring

P8-1 adds `memory/short_term.py` and uses `backend/app/core/redis.py`.

```mermaid
flowchart LR
    Settings["Settings"]
    Settings --> Factory["create_redis_client"]

    Factory --> Choice{"Fake Redis or real Redis?"}
    Choice -->|"USE_FAKE_REDIS or blank URL"| Fake["Shared Fakeredis client"]
    Choice -->|"Configured REDIS_URL"| Real["redis.asyncio client"]

    STM["ShortTermMemory"]
    STM --> Factory
    STM --> Conversations["conversation keys"]
    STM --> Workflow["workflow keys"]
    STM --> Cache["RAG cache keys"]

    Conversations --> Fake
    Conversations --> Real
    Workflow --> Fake
    Workflow --> Real
    Cache --> Fake
    Cache --> Real
```

The client protocol now includes Redis operations used by memory:

- `get`;
- `set`;
- `delete`;
- `exists`;
- TTL and close operations.

The short-term facade selects the configured client only once and keeps it in
the facade object for subsequent calls.

### Conversation routing

```mermaid
sequenceDiagram
    participant Node as Future workflow node
    participant STM as ShortTermMemory
    participant Redis as Redis or Fakeredis

    Node->>STM: append_conversation(ticket_id, message)
    STM->>STM: Build conversation:{ticket_id}
    STM->>Redis: GET key
    Redis-->>STM: Existing JSON list or none
    STM->>STM: Append message and JSON encode
    STM->>Redis: SET key, JSON, EX=86400
    Redis-->>STM: OK
    STM-->>Node: Updated conversation
```

Conversation values expire after 24 hours. The value is not written to the
ticket database through this facade.

### Workflow-state routing

```mermaid
sequenceDiagram
    participant Node as Future workflow node
    participant STM as ShortTermMemory
    participant Redis as Redis or Fakeredis

    Node->>STM: set_workflow_state(workflow_id, state)
    STM->>STM: Build workflow:{workflow_id}
    STM->>STM: JSON encode state
    STM->>Redis: SET key, JSON, EX=86400
    Redis-->>STM: OK
    STM-->>Node: true
```

The workflow key is separate from the durable `workflow_runs` SQL table.
Redis is a temporary convenience store, not the system of record.

### Retrieval-cache routing

```mermaid
flowchart LR
    Retriever["Knowledge retrieval request"]
    Retriever --> STM["ShortTermMemory"]
    STM --> Key["rag:mode:category:top_k:query"]
    Key --> Redis["Redis or Fakeredis"]
    Redis -->|"Hit"| Value["Cached JSON result"]
    Redis -->|"Miss"| Compute["Future retrieval and cache write"]
    Compute --> STM
    STM -->|"SET EX=300"| Redis
    Value --> Retriever
```

The cache TTL is 300 seconds. The key normalizes mode, category, result count,
and whitespace in the query.

P8-1 does not integrate cache reads into the knowledge retriever itself yet.
The facade provides cache operations for a later RAG-memory integration.

## P8-2 — SQL long-term component wiring

P8-2 adds `memory/long_term.py` and repository support for exact memory lookup.

```mermaid
flowchart LR
    Caller["Memory service or future workflow"]
    Caller --> LTM["LongTermMemory"]

    LTM --> Customer["CustomerRepository"]
    LTM --> Ticket["TicketRepository"]
    LTM --> MemoryRepo["CustomerMemoryRepository"]
    LTM --> Guard["scrub()"]

    Customer --> Session["Async SQLAlchemy session"]
    Ticket --> Session
    MemoryRepo --> Session
    Session --> DB["SQLite or PostgreSQL"]
    Guard --> LTM
```

The long-term facade shares the same SQLAlchemy session rather than creating
an independent database connection per operation.

### Recall route

```mermaid
sequenceDiagram
    participant Caller
    participant LTM as LongTermMemory
    participant Customer as CustomerRepository
    participant Memory as CustomerMemoryRepository
    participant DB as SQL database

    Caller->>LTM: recall(customer_id, limit)
    LTM->>LTM: Validate ID and limit 1–10
    LTM->>Customer: get_by_id(customer_id)
    Customer->>DB: SELECT customer
    DB-->>Customer: Customer or missing
    alt Missing
        LTM-->>Caller: LookupError
    else Found
        LTM->>Memory: list_for_customer(customer_id, limit)
        Memory->>DB: Customer-scoped newest-first SELECT
        DB-->>Memory: Up to 10 notes
        Memory-->>LTM: CustomerMemory objects
        LTM-->>Caller: Recalled notes
    end
```

The query begins with `customer_id`. It does not load every customer and filter
afterward.

### Record route

```mermaid
sequenceDiagram
    participant Caller
    participant LTM as LongTermMemory
    participant Customer as CustomerRepository
    participant Ticket as TicketRepository
    participant Guard as scrub()
    participant Memory as CustomerMemoryRepository
    participant DB as SQL database

    Caller->>LTM: record(customer, type, content, ticket)
    LTM->>Customer: verify customer
    opt Source ticket supplied
        LTM->>Ticket: get source ticket
        Ticket->>DB: SELECT ticket
        DB-->>Ticket: Ticket
        LTM->>LTM: Verify ticket customer ownership
        LTM->>LTM: Reject raw ticket body
    end
    LTM->>Guard: scrub(content)
    Guard-->>LTM: Safe content
    LTM->>Memory: find_exact(customer, type, content, ticket)
    Memory->>DB: Exact duplicate SELECT
    DB-->>Memory: Existing note or none
    alt Duplicate
        Memory-->>LTM: Existing note
        LTM-->>Caller: note, created=false
    else New
        LTM->>Memory: create
        Memory->>DB: INSERT
        DB-->>LTM: New note
        LTM-->>Caller: note, created=true
    end
```

P8-2 does not commit automatically in every helper. `record()` flushes through
the repository. P8-3 owns the resolution transaction commit or rollback.

## P8-3 — Unified memory service wiring

P8-3 adds `memory/memory_service.py`.

```mermaid
flowchart LR
    FutureNode["Future workflow or agent node"]
    FutureNode --> MS["MemoryService"]

    MS --> STM["ShortTermMemory"]
    MS --> LTM["LongTermMemory"]

    STM --> Redis["Redis or Fakeredis"]
    LTM --> Repositories["Customer, ticket, memory repositories"]
    Repositories --> SQL["SQLite or PostgreSQL"]
```

The service constructs:

- one short-term object;
- one long-term object;
- the long-term object with the caller's SQLAlchemy session.

The short-term object obtains Redis through the shared core factory.

### Recall route

```mermaid
flowchart LR
    Node["Customer context node"]
    Node -->|"recall_customer(customer_id)"| MS["MemoryService"]
    MS -->|"delegates"| LTM["LongTermMemory"]
    LTM -->|"up to 10 notes"| Repo["CustomerMemoryRepository"]
    Repo -->|"async SQL query"| DB["SQLite or PostgreSQL"]
    DB --> Repo
    Repo --> LTM
    LTM --> MS
    MS --> Node
```

### Resolution-record route

```mermaid
sequenceDiagram
    participant Node as Completed workflow node
    participant MS as MemoryService
    participant LTM as LongTermMemory
    participant DB as Async SQLAlchemy session

    Node->>MS: record_resolution(...)
    MS->>MS: Normalize ticket ID
    MS->>MS: Keep first three troubleshooting steps
    MS->>LTM: record past_issue
    loop Up to three steps
        MS->>LTM: record troubleshooting
    end
    MS->>LTM: record resolution note
    alt A record operation fails
        MS->>DB: rollback
        MS-->>Node: exception
    else All records succeed
        MS->>DB: commit
        MS-->>Node: (note, created) records
    end
```

This transaction boundary is important: P8-3 records a resolution as one
logical SQL transaction. It does not leave a mixture of partial past-issue,
step, and resolution notes after an error.

### Short-term convenience routing

```mermaid
flowchart LR
    MS["MemoryService"]

    MS --> Conversation["get or append conversation"]
    MS --> Workflow["get or set workflow state"]

    Conversation --> STM["ShortTermMemory"]
    Workflow --> STM

    STM --> Redis["Redis or Fakeredis"]
```

The future workflow node does not need to import Redis or build Redis key names
when using these convenience methods.

## Test-time wiring

Phase 8 tests construct isolated memory dependencies:

```mermaid
flowchart LR
    Test["pytest async test"]
    Test --> SQLite["In-memory SQLite async engine"]
    SQLite --> Session["async_sessionmaker"]
    Test --> Fake["Fakeredis client"]
    Test --> MS["MemoryService"]

    Session --> MS
    Fake --> MS

    MS --> STM["ShortTermMemory"]
    MS --> LTM["LongTermMemory"]

    STM --> Fake
    LTM --> Session

    Session --> LTMRepo["Customer, ticket, memory repositories"]
```

The tests verify:

- Redis TTL constants and key formats;
- JSON round trips;
- customer-scoped recall;
- exact duplicate prevention;
- ticket ownership;
- raw-ticket rejection;
- secret scrubbing;
- short-term/long-term separation;
- resolution transaction behavior.

No Docker container or live Redis server is required.

## HTTP and application routing

Phase 8 does not add a memory API route. The existing FastAPI application
continues to route customer detail through `CustomerService`.

```mermaid
flowchart LR
    Caller["HTTP client"]
    Caller --> Middleware["Request-ID, audit, rate limit, CORS"]
    Middleware --> FastAPI["FastAPI application"]
    FastAPI --> CustomerRoute["Customer routes"]
    CustomerRoute --> CustomerService["CustomerService"]
    CustomerService --> MemoryRepo["CustomerMemoryRepository"]
    MemoryRepo --> SQL["SQLite or PostgreSQL"]
```

Customer detail currently returns memory through this repository path and
applies `scrub()` at the response boundary. It does not use the P8
`MemoryService` in an HTTP route yet.

A future workflow route or memory node can compose `MemoryService` with the
application's session factory and Redis client.

## End-of-Phase 8 component and network view

The complete implemented memory architecture is in-process Python composition
with two configured data backends.

```mermaid
flowchart TB
    subgraph Process["FastAPI or test Python process"]
        Future["Future workflow and agent nodes"]
        MS["MemoryService"]
        STM["ShortTermMemory"]
        LTM["LongTermMemory"]
        Session["Async SQLAlchemy session"]
        Repos["Customer, ticket, and memory repositories"]
        Guard["scrub()"]

        Future --> MS
        MS --> STM
        MS --> LTM
        LTM --> Guard
        LTM --> Session
        LTM --> Repos
        Repos --> Session
    end

    RedisMode{"Redis configuration"}
    RedisMode -->|"USE_FAKE_REDIS or blank URL"| Fake["Fakeredis"]
    RedisMode -->|"REDIS_URL configured"| Real["Redis server"]
    STM --> RedisMode

    SQLMode{"DATABASE_URL"}
    SQLMode -->|"sqlite+aiosqlite"| SQLite["In-process or file SQLite"]
    SQLMode -->|"PostgreSQL URL"| Postgres["PostgreSQL"]
    Session --> SQLMode

    Future -. "Future LangGraph memory nodes" .-> Future
```

### Final routing summary

| Operation | Implemented route |
|---|---|
| Save or read conversation | Workflow node -> MemoryService -> ShortTermMemory -> Redis/fakeredis |
| Save or read workflow state | Workflow node -> MemoryService -> ShortTermMemory -> Redis/fakeredis |
| Cache retrieval result | RAG caller -> ShortTermMemory -> Redis/fakeredis |
| Recall customer memory | Workflow node -> MemoryService -> LongTermMemory -> SQL repository |
| Record resolution | Workflow node -> MemoryService -> LongTermMemory -> one SQL transaction |
| Display customer memory | Customer API -> CustomerRepository -> SQL -> scrubbed response |

## Docker networking — not implemented at end of Phase 8

There is no Dockerfile or Compose file in the repository. Phase 8 therefore
does not create or route:

- backend-to-Redis container DNS;
- backend-to-PostgreSQL container DNS;
- Redis ports or volumes;
- PostgreSQL volumes;
- memory worker containers;
- a dedicated memory microservice;
- Docker health checks for Redis or memory.

Redis and SQL are still configured by environment settings.

The real Redis and database locations are resolved by the Python libraries:

- Redis uses `REDIS_URL`;
- SQLAlchemy uses `DATABASE_URL`.

In the offline demo, the Redis network dependency is replaced by Fakeredis and
SQLite replaces PostgreSQL.

A future container deployment might appear as:

```mermaid
flowchart LR
    Browser["Browser"]
    Browser -->|"Future HTTPS"| Frontend["Next.js container"]
    Frontend -->|"Future REST /api/v1"| Backend["FastAPI container"]

    Backend --> Redis["Redis container or managed Redis"]
    Backend --> PostgreSQL["PostgreSQL container or managed database"]
    Backend --> Qdrant["Qdrant container or managed vector store"]

    subgraph BackendContainer["Future backend container"]
        STM["ShortTermMemory"]
        LTM["LongTermMemory"]
        MS["MemoryService"]
        STM --> MS
        LTM --> MS
    end
```

This is planned container topology, not an implemented Phase 8 Docker
configuration. Service names, ports, networks, volumes, and health checks should
only be written after Compose or deployment files exist.

## Infrastructure and honest status

Phase 8 implementation is verified as:

- an in-process memory service;
- a Redis/Fakeredis short-term backend;
- an async SQLAlchemy long-term backend;
- a customer and ticket repository boundary;
- transaction commit and rollback behavior;
- no dedicated HTTP memory route;
- no Docker or container network.

The local offline suite passed 182 tests, and Ruff passed for the memory
implementation and tests.

Validation used:

- Fakeredis;
- in-memory SQLite;
- async SQLAlchemy sessions.

No live Redis, PostgreSQL, Docker, cloud credential, or real customer data was
used.

The future LangGraph integration must compose `MemoryService` with the real
workflow session and decide when recall and resolution recording occur.

## Implementation references

| Responsibility | Source |
|---|---|
| Redis protocol and factory | [core/redis.py](../../backend/app/core/redis.py) |
| Redis short-term facade | [short_term.py](../../memory/short_term.py) |
| SQL long-term facade | [long_term.py](../../memory/long_term.py) |
| Unified memory service | [memory_service.py](../../memory/memory_service.py) |
| Customer memory repository | [customers.py](../../backend/app/repositories/customers.py) |
| Async SQLAlchemy session routing | [core/database.py](../../backend/app/core/database.py) |
| Secret scrubbing | [guardrails.py](../../backend/app/core/guardrails.py) |
| FastAPI startup and route assembly | [main.py](../../backend/app/main.py) |
| Short-term tests | [test_short_term_memory.py](../../tests/unit/test_short_term_memory.py) |
| Long-term tests | [test_long_term_memory.py](../../tests/unit/test_long_term_memory.py) |
| Memory service tests | [test_memory_service.py](../../tests/unit/test_memory_service.py) |
| Phase task status | [TASK.md](../../TASK.md) |
| Phase exit criteria | [PLAN_PHASE.md](../../PLAN_PHASE.md) |
| Phase 8 system design evolution | [Phase8_Project_System_Design_Evolution.md](../design_evolution/Phase8_Project_System_Design_Evolution.md) |
| Plain-language Phase 8 explanation | [phase8_explained.md](../explain_codebase/phase8_explained.md) |
