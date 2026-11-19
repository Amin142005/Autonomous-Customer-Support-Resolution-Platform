# Phase 8 — Project System Design Evolution

This document follows the CloudDesk memory design from the Phase 7
rules-and-guardrails baseline through P8-1 to P8-3. It shows the simplest
starting shape, how each subtask changes the design, and the complete
two-tier memory architecture at the end of Phase 8.

## Phase 8 goal

Phase 8 provides short-term workflow storage and safe, de-duplicated customer
memory.

The subtask evolution is:

```mermaid
flowchart LR
    P81["P8-1: Short-term Redis facade"]
    P82["P8-2: Long-term customer memory"]
    P83["P8-3: Recall and record service"]

    P81 --> Final["Two-tier memory system"]
    P82 --> Final
    P83 --> Final
```

P8-1 establishes temporary Redis memory. P8-2 establishes durable,
customer-scoped SQL memory. P8-3 coordinates both tiers through one service
for future workflow nodes.

## Starting design — Phase 7 application without memory facades

At the beginning of Phase 8, CloudDesk has:

- persisted tickets and customers;
- policy and guardrail helpers;
- a tool registry;
- knowledge retrieval;
- a customer-memory database table;
- repository access to that table.

However, the application does not yet have one intentional memory abstraction
with two lifetimes.

```mermaid
flowchart LR
    Ticket["Support ticket"]
    Ticket --> Workflow["Future support workflow"]
    Workflow --> Context["Temporary context recreated from data"]
    Context --> Customer["Customer or ticket record"]

    Conversation["Current conversation"] -. "No facade" .-> Missing["No short-term memory"]
    WorkflowState["Workflow progress"] -. "No facade" .-> Missing
    SearchCache["Repeated retrieval result"] -. "No facade" .-> Missing

    MemoryNotes["customer_memory table"] -. "Repository access exists" .-> Customer
    Service["No unified memory service"] -. "Missing" .-> Workflow
```

### Starting limitations

- Conversation context has no Redis facade.
- Workflow state has no defined short-term key pattern.
- Retrieval results have no 300-second cache boundary.
- Long-term memory has repository access but no dedicated safety facade.
- Memory recall and resolution recording are not coordinated.
- Raw ticket text or secrets could be copied if future code stores them
  directly.

The Phase 8 design therefore needs two tiers with one shared service boundary.

## Evolution by subtask

### P8-1 — Short-term Redis facade

**Design change:** temporary conversation, workflow, and cache values move
behind a Redis/fakeredis Python interface.

P8-1 introduces `ShortTermMemory` and Redis key builders.

```mermaid
flowchart LR
    FutureNode["Future workflow or agent"]
    FutureNode --> STM["ShortTermMemory"]

    STM --> Conversation["Ticket conversation"]
    STM --> Workflow["Workflow state"]
    STM --> Cache["RAG retrieval cache"]

    Conversation --> KeyC["conversation:{ticket_id}"]
    Workflow --> KeyW["workflow:{workflow_id}"]
    Cache --> KeyR["rag:{mode}:{category}:{top_k}:{query}"]

    KeyC --> Redis["Redis or Fakeredis"]
    KeyW --> Redis
    KeyR --> Redis
```

The Redis factory checks settings:

```mermaid
flowchart TD
    Settings["Redis settings"]
    Settings --> Mode{"USE_FAKE_REDIS or no REDIS_URL?"}
    Mode -->|"Yes"| Fake["Shared Fakeredis client"]
    Mode -->|"No"| Real["redis.asyncio client"]
    Fake --> Memory["Short-term data operations"]
    Real --> Memory
```

The TTL design is:

| Data | Key | TTL |
|---|---|---|
| Ticket conversation | `conversation:{ticket_id}` | 24 hours |
| Workflow state | `workflow:{workflow_id}` | 24 hours |
| Retrieval cache | `rag:{mode}:{category}:{top_k}:{query}` | 300 seconds |

Conversation values are JSON lists of messages. Workflow values are JSON
objects or values. Retrieval values are JSON-encoded evidence or search
results.

```mermaid
sequenceDiagram
    participant Node as Future workflow node
    participant STM as ShortTermMemory
    participant Redis as Redis or Fakeredis

    Node->>STM: append_conversation(ticket_id, message)
    STM->>Redis: GET conversation:{ticket_id}
    Redis-->>STM: Existing JSON or none
    STM->>STM: Append message and encode JSON
    STM->>Redis: SET with 24-hour TTL
    Redis-->>STM: OK
    STM-->>Node: Updated conversation
```

The retrieval cache key is normalized:

```mermaid
flowchart LR
    Input["Mode, category, top_k, query"]
    Input --> Normalize["Lowercase and trim"]
    Normalize --> Category{"Category supplied?"}
    Category -->|"Yes"| C["Use normalized category"]
    Category -->|"No"| All["Use all"]
    C --> Key["rag:key"]
    All --> Key
    Key --> Cache["GET or SET with 300-second TTL"]
```

**Result:** P8-1 gives future nodes Redis-style temporary memory without
building Redis keys and JSON encoding themselves.

### P8-2 — Long-term customer memory

**Design change:** durable memory becomes a restricted, customer-scoped facade
instead of direct repository writes.

P8-2 introduces `LongTermMemory`, permitted memory types, exact duplicate
lookup, source-ticket validation, and secret scrubbing.

```mermaid
flowchart LR
    Caller["Memory service or future workflow"]
    Caller --> LTM["LongTermMemory"]

    LTM --> Customers["CustomerRepository"]
    LTM --> Tickets["TicketRepository"]
    LTM --> MemoryRepo["CustomerMemoryRepository"]
    LTM --> Scrub["scrub()"]

    Customers --> DB["SQLite or PostgreSQL"]
    Tickets --> DB
    MemoryRepo --> DB
    Scrub --> Safe["Scrubbed content"]
    Safe --> MemoryRepo
```

The permitted type boundary is:

```mermaid
flowchart TD
    Request["Requested memory type"]
    Request --> Type{"Type permitted?"}
    Type -->|"preference"| Allowed["Allow"]
    Type -->|"past_issue"| Allowed
    Type -->|"troubleshooting"| Allowed
    Type -->|"note"| Allowed
    Type -->|"Anything else"| Reject["Reject type"]
```

The safe record flow is:

```mermaid
sequenceDiagram
    participant Caller
    participant LTM as LongTermMemory
    participant Customer as CustomerRepository
    participant Ticket as TicketRepository
    participant Memory as CustomerMemoryRepository
    participant Guard as scrub()
    participant DB as SQL database

    Caller->>LTM: record(customer, type, content, ticket)
    LTM->>Customer: verify customer exists
    Customer-->>LTM: customer or missing
    opt Source ticket supplied
        LTM->>Ticket: get source ticket
        Ticket-->>LTM: ticket
        LTM->>LTM: verify ticket belongs to customer
        LTM->>LTM: reject raw ticket body content
    end
    LTM->>Guard: scrub content
    Guard-->>LTM: safe content
    LTM->>Memory: find exact duplicate
    Memory->>DB: customer, type, content, source query
    DB-->>Memory: existing note or none
    alt Duplicate exists
        Memory-->>LTM: existing note
        LTM-->>Caller: existing note, created=false
    else No duplicate
        LTM->>Memory: create note
        Memory->>DB: INSERT
        DB-->>LTM: created note
        LTM-->>Caller: note, created=true
    end
```

Recall is customer-scoped and bounded:

```mermaid
flowchart LR
    Request["recall(customer_id, limit)"]
    Request --> Validate["Validate customer and 1–10 limit"]
    Validate --> Exists{"Customer exists?"}
    Exists -->|"No"| Error["LookupError"]
    Exists -->|"Yes"| Repo["CustomerMemoryRepository"]
    Repo --> Query["Filter customer ID"]
    Query --> Newest["Newest first"]
    Newest --> Page["Apply limit"]
    Page --> Result["At most 10 customer notes"]
```

**Result:** P8-2 prevents arbitrary note types, cross-customer ticket sources,
raw ticket bodies, secrets, and exact duplicates.

### P8-3 — Recall and record service

**Design change:** short-term and long-term memory become one coordinated
service for future workflow nodes.

P8-3 introduces `MemoryService`.

```mermaid
flowchart LR
    Workflow["Future LangGraph node"]
    Workflow --> MS["MemoryService"]

    MS --> STM["ShortTermMemory"]
    MS --> LTM["LongTermMemory"]

    STM --> Redis["Redis or Fakeredis"]
    LTM --> Repositories["Customer, ticket, and memory repositories"]
    Repositories --> SQL["SQLite or PostgreSQL"]
```

The service exposes two main long-term operations:

- `recall_customer`;
- `record_resolution`.

It also exposes short-term convenience operations for:

- ticket conversations;
- workflow state.

The resolution record flow is:

```mermaid
sequenceDiagram
    participant Workflow as Completed workflow node
    participant MS as MemoryService
    participant LTM as LongTermMemory
    participant DB as SQL database

    Workflow->>MS: record_resolution(customer, ticket, issue, steps, summary)
    MS->>MS: Validate ticket ID
    MS->>MS: Keep first three troubleshooting steps

    MS->>LTM: Record past_issue
    loop Each of up to three steps
        MS->>LTM: Record troubleshooting
    end
    MS->>LTM: Record resolution note
    LTM-->>MS: (note, created or duplicate)

    alt Any step fails
        MS->>DB: Roll back session
        MS-->>Workflow: Exception
    else All steps succeed
        MS->>DB: Commit session
        MS-->>Workflow: Created/duplicate record list
    end
```

The resolution shape is consistent:

```mermaid
flowchart LR
    Input["Past issue + troubleshooting steps + resolution note"]
    Input --> Issue["past_issue"]
    Input --> Step1["troubleshooting 1"]
    Input --> Step2["troubleshooting 2"]
    Input --> Step3["troubleshooting 3"]
    Input --> Resolution["note"]

    Issue --> Safe["LongTermMemory.scrubbing and duplicate checks"]
    Step1 --> Safe
    Step2 --> Safe
    Step3 --> Safe
    Resolution --> Safe
    Safe --> Commit["One SQL transaction"]
```

The short-term and long-term stores remain separate:

```mermaid
flowchart TB
    MS["MemoryService"]

    MS --> Conversation["Conversation operations"]
    MS --> WorkflowState["Workflow state operations"]
    MS --> Recall["Recall customer notes"]
    MS --> Resolution["Record resolution"]

    Conversation --> STM["ShortTermMemory"]
    WorkflowState --> STM
    Recall --> LTM["LongTermMemory"]
    Resolution --> LTM

    STM --> Redis["Redis or Fakeredis"]
    LTM --> MemoryRepo["CustomerMemoryRepository"]
    MemoryRepo --> SQL["SQLite or PostgreSQL"]
```

**Result:** P8-3 gives future graph code one composition service instead of
separate Redis, repository, and scrubbing calls.

## End-of-Phase 8 design

The final Phase 8 design has two memory lifetimes and one coordination
service.

```mermaid
flowchart TB
    subgraph Workflow["Future workflow nodes"]
        CustomerNode["Customer context node"]
        Investigation["Troubleshooting node"]
        Resolution["Resolution node"]
        MemoryUpdate["Memory update node"]
    end

    subgraph MemoryService["MemoryService composition"]
        Service["MemoryService"]
        Short["ShortTermMemory"]
        Long["LongTermMemory"]

        Service --> Short
        Service --> Long
    end

    subgraph RedisMemory["Short-term memory"]
        Redis["Redis or Fakeredis"]
        Conversation["conversation:{ticket_id}<br/>24 hours"]
        State["workflow:{workflow_id}<br/>24 hours"]
        Cache["rag:{mode}:{category}:{top_k}:{query}<br/>300 seconds"]
        Redis --> Conversation
        Redis --> State
        Redis --> Cache
    end

    subgraph SQLMemory["Long-term memory"]
        Repo["CustomerMemoryRepository"]
        Table["customer_memory"]
        Repo --> Table
    end

    subgraph Safety["Long-term safety"]
        Guard["scrub()"]
        Types["Permitted note types"]
        Ownership["Customer and ticket ownership"]
        Duplicate["Exact duplicate lookup"]
    end

    CustomerNode --> Service
    Investigation --> Short
    Resolution --> Service
    MemoryUpdate --> Service

    Short --> Redis
    Long["LongTermMemory"] --> Safety
    Safety --> Repo

    CustomerNode -->|"recall_customer"| Service
    MemoryUpdate -->|"record_resolution"| Service
    Service -->|"temporary conversation or state"| Short
```

The final memory update flow is:

```mermaid
sequenceDiagram
    participant Workflow as Completed support workflow
    participant MS as MemoryService
    participant STM as ShortTermMemory
    participant LTM as LongTermMemory
    participant Redis as Redis or Fakeredis
    participant SQL as SQL customer_memory

    Workflow->>STM: Read or save temporary context
    STM->>Redis: JSON value with TTL
    Redis-->>STM: Temporary value

    Workflow->>MS: recall_customer(customer_id)
    MS->>LTM: recall up to 10 notes
    LTM->>SQL: Customer-scoped newest-first query
    SQL-->>LTM: Permitted memory notes
    LTM-->>MS: Customer context
    MS-->>Workflow: Customer memory

    Workflow->>MS: record_resolution(...)
    MS->>LTM: Past issue, steps, resolution note
    LTM->>LTM: Validate, scrub, and deduplicate
    LTM->>SQL: Insert missing notes once
    SQL-->>LTM: Stored or existing notes
    LTM-->>MS: Records and created flags
    MS-->>Workflow: Resolution memory result
```

## Memory separation by purpose

| Design concern | Short-term component | Long-term component |
|---|---|---|
| Storage | Redis/fakeredis | SQLAlchemy/customer_memory |
| Lifetime | 24 hours or 300 seconds | Permanent until removed |
| Typical data | Active conversation, workflow state, cache | Past issue, preference, steps, resolution |
| Customer isolation | Keyed by ticket/workflow, not customer data | Customer ID and source ticket ownership |
| Secret safety | No dedicated scrub in P8-1 | P7 scrub reused before write |
| Duplication | Cache or message list behavior | Exact duplicate lookup |
| Recall size | Defined by temporary key contents | Maximum 10 |

The design does not store raw conversation content in the customer-memory
table. It stores only small resolution summaries and permitted facts.

## Data-safety boundaries

The long-term record path has several gates:

```mermaid
flowchart TD
    Draft["Draft memory note"]
    Draft --> Customer{"Customer exists?"}
    Customer -->|"No"| Reject["Reject"]
    Customer -->|"Yes"| Type{"Permitted type?"}
    Type -->|"No"| Reject
    Type -->|"Yes"| Source{"Source ticket belongs to customer?"}
    Source -->|"No"| Reject
    Source -->|"Yes"| Raw{"Same as or contains raw ticket body?"}
    Raw -->|"Yes"| Reject
    Raw -->|"No"| Scrub["Scrub secret values"]
    Scrub --> Duplicate{"Exact duplicate?"}
    Duplicate -->|"Yes"| Existing["Return existing note"]
    Duplicate -->|"No"| Insert["Insert safe note"]
```

This boundary is important because P8 is not only a storage feature. It is a
privacy and data-quality feature.

## Component boundaries

| Component | Owns | Does not own |
|---|---|---|
| `ShortTermMemory` | Redis keys, JSON values, and TTLs | Long-term SQL memory |
| `LongTermMemory` | Permitted types, recall, scrubbing, ticket ownership, duplicates | Redis state |
| `CustomerMemoryRepository` | SQL customer-memory reads and exact lookup | Ticket-body or secret policy |
| `MemoryService` | Coordination and resolution recording | LangGraph node routing |
| `scrub()` | Secret redaction | Customer ownership or note types |
| Redis/fakeredis | Temporary value storage | Durable customer facts |

These boundaries keep temporary state separate from durable facts and keep
policy out of direct SQL repository calls.

## Evolution of the design

```mermaid
flowchart LR
    Start["Workflow with no memory facade"]
    P81["P8-1: Redis short-term memory"]
    P82["P8-2: Safe SQL long-term memory"]
    P83["P8-3: Unified memory service"]
    Final["Recall and record customer context safely"]

    Start --> P81 --> P82 --> P83 --> Final
```

The design becomes safer and easier to use at every step:

1. P8-1 removes temporary Redis key duplication.
2. P8-2 restricts and de-duplicates durable records.
3. P8-3 gives future workflow nodes one recall/record interface.

## Validation and honest status

Phase 8 implementation includes:

- Redis/fakeredis short-term memory;
- conversation and workflow TTL keys;
- retrieval cache TTL and normalized key format;
- permitted long-term memory types;
- recall limit of 10;
- source-ticket ownership checks;
- secret scrubbing;
- exact duplicate prevention;
- unified recall and record service;
- resolution transaction rollback.

The local offline suite passed 182 tests, and Ruff passed for the memory
implementation and tests.

The implementation was validated with:

- Fakeredis;
- in-memory SQLite;
- in-memory async sessions.

No live Redis server, PostgreSQL database, Docker container, or cloud
credential was used.

P8-3 is complete, but future LangGraph memory nodes are not implemented yet.
The facades are ready for those nodes to call.

## Component reference

| Responsibility | Implementation |
|---|---|
| Redis protocol and factory | [core/redis.py](../../backend/app/core/redis.py) |
| Short-term memory facade | [short_term.py](../../memory/short_term.py) |
| Long-term memory facade | [long_term.py](../../memory/long_term.py) |
| Recall and record service | [memory_service.py](../../memory/memory_service.py) |
| Memory repository exact lookup | [customers.py](../../backend/app/repositories/customers.py) |
| Secret scrubbing | [guardrails.py](../../backend/app/core/guardrails.py) |
| Short-term tests | [test_short_term_memory.py](../../tests/unit/test_short_term_memory.py) |
| Long-term tests | [test_long_term_memory.py](../../tests/unit/test_long_term_memory.py) |
| Memory service tests | [test_memory_service.py](../../tests/unit/test_memory_service.py) |
| Phase task status | [TASK.md](../../TASK.md) |
| Phase exit criteria | [PLAN_PHASE.md](../../PLAN_PHASE.md) |
| Plain-language Phase 8 explanation | [phase8_explained.md](../explain_codebase/phase8_explained.md) |
