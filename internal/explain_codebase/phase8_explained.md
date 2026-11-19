# Phase 8 — CloudDesk Memory

## A plain-language presentation

> **Use this as a speaking script.** It explains Phase 8 for an audience that may
> not have a software background.

Phases 1 through 7 gave CloudDesk a working foundation, stored support records,
APIs, knowledge search, safe tools, and policy guardrails. Phase 8 gives the
system two kinds of memory:

- **short-term memory** for temporary work;
- **long-term memory** for useful facts about a customer.

Think of a support center with two types of information storage:

- a desk notebook used during the current shift;
- a permanent customer file kept for future service.

The first is quick and temporary. The second is carefully limited and lasts
until it is no longer needed.

The short version is:

```text
Temporary conversation and workflow state
  → stored briefly in Redis

Useful, safe facts about a customer
  → stored in the customer-memory database

A memory service
  → recalls the durable facts
  → records the result of completed resolutions
```

Phase 8 does not yet connect memory to the full LangGraph workflow. It creates
the memory facades that later customer, workflow, and resolution nodes can use.

## The problem Phase 8 solves

Support work happens in stages.

Imagine an agent is helping a customer recover from an MFA issue:

1. the customer describes the problem;
2. the workflow checks the account;
3. troubleshooting steps are tested;
4. the agent resolves the issue;
5. the team wants to remember the useful result.

The details of the current session should be easy to retrieve while the work is
active. At the same time, CloudDesk should not copy every customer message into
a permanent profile.

Without memory, the system would repeatedly ask or calculate the same context.
Without safe memory boundaries, it could permanently store passwords, card
numbers, raw ticket text, or details belonging to another customer.

Phase 8 separates these needs.

## The two kinds of memory

### Short-term memory

Short-term memory holds temporary information for a limited time.

It has three uses:

| Short-term use | Everyday meaning |
|---|---|
| Ticket conversation | Messages and context for one ticket |
| Workflow state | The current workflow step and progress |
| Retrieval cache | Recently searched knowledge results |

The short-term implementation uses Redis or Fakeredis.

- **Redis** is for a running shared environment.
- **Fakeredis** is an in-process imitation used for offline tests.

The short-term TTL, or time to live, is:

- 24 hours for conversations and workflow state;
- 300 seconds for retrieval cache.

A TTL means the value is automatically removed after the allowed period.

In plain terms:

```text
Conversation for ticket CD-1001
  → lasts 24 hours

Workflow state for workflow 123
  → lasts 24 hours

Search result for one knowledge question
  → lasts 5 minutes
```

This prevents temporary context from becoming permanent storage.

### Long-term memory

Long-term memory holds useful facts about a customer across future interactions.

The permitted note types are:

- `preference`;
- `past_issue`;
- `troubleshooting`;
- `note`.

Each note belongs to one customer and can optionally refer to a source ticket.

Examples of safe notes could be:

- “Customer prefers written troubleshooting steps.”
- “Customer previously had an MFA recovery issue.”
- “The successful recovery steps were verify enrollment and reset the session.”
- “Support access was restored.”

The long-term implementation uses the `customer_memory` database table and the
existing SQLAlchemy repository.

It is permanent unless explicitly changed or removed, but only permitted,
scrubbed, de-duplicated facts are stored.

## P8-1 — Short-term Redis facade

P8-1 creates `ShortTermMemory`.

It is a Python interface around Redis operations. The application does not need
to build Redis keys or JSON strings everywhere.

### Ticket conversations

The conversation key is:

```text
conversation:{ticket_id}
```

For example:

```text
conversation:ticket-123
```

The facade can:

- set the complete conversation;
- append one message;
- retrieve the conversation;
- delete the conversation.

The value is stored as JSON. A conversation might look like:

```text
[
  { "role": "customer", "body": "SSO is failing" },
  { "role": "agent", "body": "We are investigating" }
]
```

The 24-hour TTL is applied every time the conversation is set.

### Workflow state

The workflow key is:

```text
workflow:{workflow_id}
```

For example:

```text
workflow:workflow-123
```

Workflow state can contain values such as:

- the current node;
- completed nodes;
- a ticket identifier;
- temporary workflow results.

The state is serialized as JSON and expires after 24 hours.

This is separate from the durable `workflow_runs` database table. Redis holds
fast, temporary state, while SQL stores workflow records that the application
needs to retain.

### Retrieval cache

The retrieval cache key shape is:

```text
rag:{mode}:{category}:{top_k}:{query}
```

For example:

```text
rag:hybrid:billing:5:invoice refund
```

The key includes:

- search mode;
- category;
- number of requested results;
- normalized query text.

A category such as `billing` becomes part of the key. If no category is
supplied, the facade uses `all`.

The retrieval cache expires after 300 seconds. The search can then be repeated
after five minutes instead of trusting an old answer forever.

### Redis or Fakeredis

The Redis factory chooses:

- **Fakeredis** when `USE_FAKE_REDIS=true` or no `REDIS_URL` is configured;
- **real Redis** when a Redis URL is configured.

This lets the offline demo behave like Redis without a server.

## P8-2 — Long-term customer memory

P8-2 creates `LongTermMemory`.

It is a facade over the `CustomerMemoryRepository`, and therefore uses SQLAlchemy
and the existing `customer_memory` table.

### Recall

`recall()` returns up to 10 notes for one customer.

The service:

1. validates the customer ID;
2. validates the recall limit;
3. confirms that the customer exists;
4. asks the repository for that customer's newest permitted memory;
5. returns the notes.

No other customer's notes are included.

### Record

`record()` creates a single durable memory note.

Before writing, it:

1. validates the customer;
2. validates the note type;
3. scrubs credentials and card numbers;
4. validates the source ticket;
5. prevents a raw ticket body from being stored;
6. searches for an exact duplicate;
7. creates the note only if no duplicate exists.

This makes the write path safe and de-duplicated.

### Permitted types

The only permitted memory types are:

- `preference`;
- `past_issue`;
- `troubleshooting`;
- `note`.

A type such as `raw_ticket` is rejected.

This prevents arbitrary future code from turning the memory table into a copy of
every ticket message.

### Source ticket

A memory note can refer to a source ticket.

The source ticket must:

- exist;
- belong to the same customer.

A ticket from another customer cannot be attached to this memory record.

The system also compares the note content with the ticket body. If the content
is the exact raw body or contains that body, the system rejects it.

### Scrubbing

Before a note is stored, it passes through `scrub()`.

The scrubber removes or masks:

- passwords;
- API keys;
- bearer tokens;
- JWT values;
- private keys;
- URL credentials;
- sensitive query values;
- AWS-style keys;
- card numbers.

For example:

```text
Password=example-secret
```

is stored more safely as:

```text
[REDACTED]
```

### Exact duplicate prevention

The repository searches for an existing note with the same:

- customer;
- note type;
- scrubbed content;
- source ticket.

If the exact record already exists, the service returns it and marks it as not
created. This prevents repeated workflow runs from adding the same fact many
times.

## P8-3 — Recall and record service

P8-3 creates `MemoryService`.

It is a coordinator that contains both:

- a `ShortTermMemory` object;
- a `LongTermMemory` object.

Its job is to expose one memory interface to future workflow nodes.

### Recall customer

`recall_customer()` asks the long-term memory facade for up to 10 customer
notes.

It is intentionally customer-scoped.

```text
Customer 123
  → recall up to 10 notes for customer 123
  → never include customer 456's notes
```

This is the read side of the long-term memory service.

### Record resolution

`record_resolution()` is used after a support workflow is complete.

It records:

1. one `past_issue` note;
2. up to three `troubleshooting` notes;
3. one `note` with the resolution summary.

For example:

```text
past_issue
  “Customer previously had an MFA login issue”

troubleshooting
  “Verify MFA enrollment”

troubleshooting
  “Reset the MFA session”

note
  “Customer access was restored”
```

If the troubleshooting list contains more than three steps, only the first
three are recorded.

### Database transaction

The resolution service records all the notes in one SQLAlchemy session.

If one note fails:

- all SQL changes are rolled back;
- no partial resolution memory is left from that operation.

If all notes succeed:

- the session commits once;
- the result reports which notes were created and which were duplicates.

### Short-term convenience methods

The memory service also exposes temporary operations:

- get or append a ticket conversation;
- get or set workflow state.

These methods delegate to `ShortTermMemory`.

This keeps workflow code from knowing how Redis keys or JSON encoding work.

## How short-term and long-term memory differ

| Area | Short-term memory | Long-term memory |
|---|---|---|
| Storage | Redis or Fakeredis | SQL customer-memory table |
| Life | 24 hours or 300 seconds | Permanent |
| Purpose | Current session, workflow, cache | Useful facts about a customer |
| Typical content | Messages, current step, search result | Preference, past issue, troubleshooting, note |
| Safety check | Key and JSON handling | Type validation, scrubbing, ticket ownership |
| Duplicate handling | Replaces or appends temporary values | Exact duplicate lookup |

The two stores serve different purposes. The system should not copy every
conversation into long-term SQL memory.

## Complete Phase 8 flow

```text
During a support workflow
  → short-term memory stores conversation and workflow state
  → Redis cache stores recent retrieval results

After a resolution
  → memory service creates a durable summary
  → long-term memory validates and scrubs it
  → exact duplicates are skipped
  → safe facts are stored in the customer-memory table

On a later ticket
  → memory service recalls up to 10 customer notes
  → support agents get useful customer context
```

### P8-1, P8-2, and P8-3 together

```text
P8-1: temporary Redis storage
  → conversations
  → workflow state
  → retrieval cache

P8-2: durable SQL memory
  → permitted memory types
  → scrubbing
  → duplicate prevention
  → customer and ticket ownership

P8-3: unified service
  → short-term operations
  → recall customer
  → record resolution
  → transaction control
```

## How the components fit

```text
Future workflow or agent
  └─ MemoryService
       ├─ ShortTermMemory
       │    ├─ Redis / Fakeredis
       │    ├─ conversation keys
       │    ├─ workflow keys
       │    └─ RAG cache keys
       │
       └─ LongTermMemory
            ├─ CustomerRepository
            ├─ TicketRepository
            ├─ CustomerMemoryRepository
            ├─ scrub()
            └─ customer_memory table
```

The responsibilities are deliberately separated:

- `ShortTermMemory` knows Redis data and TTLs;
- `LongTermMemory` knows SQL memory, allowed types, and data safety;
- `CustomerMemoryRepository` owns memory database queries;
- `MemoryService` coordinates both sides for future workflow code;
- `scrub()` removes known secrets before storage.

## Safety and boundaries

- Short-term conversation and workflow values expire.
- Retrieval cache expires after 300 seconds.
- Long-term recall is limited to 10 notes.
- Only four note types are permitted.
- Notes are scrubbed before storage.
- Raw ticket bodies cannot be stored.
- Source tickets must belong to the customer.
- Other-customer data is not recalled.
- Exact duplicates are not created twice.
- Resolution recording rolls back on failure.

These rules protect both privacy and the usefulness of memory.

## What Phase 8 does not do

Phase 8 does not yet:

- connect memory automatically to LangGraph;
- add memory node implementations;
- create a frontend memory screen;
- use semantic search over customer notes;
- add automatic memory summarization;
- delete or expire long-term notes based on retention policy;
- use a live Redis server in the offline demo;
- persist Redis values outside the configured backend.

The facade is ready. A later graph integration must decide when to recall and
when to record memory.

## Validation and honest status

The Phase 8 implementation includes:

- short-term Redis/fakeredis storage;
- conversation and workflow TTL keys;
- RAG retrieval cache keys;
- permitted long-term note types;
- customer-scoped recall;
- source-ticket ownership checks;
- secret scrubbing;
- exact duplicate prevention;
- a unified memory service;
- resolution recording and transaction rollback.

The local offline test suite passed **182 tests**, and Ruff passed for the
memory implementation and tests.

The tests use Fakeredis and in-memory SQLite. No live Redis server, PostgreSQL
database, Docker container, or cloud credential was used.

P8-3 is complete, but memory nodes in the future LangGraph workflow are not yet
implemented.

## Short answers for likely questions

**Why have short-term and long-term memory?**  
Temporary conversation context should expire quickly, while useful customer
facts can remain available for future service.

**Why not store every ticket as memory?**  
Raw tickets can contain secrets and too much detail. CloudDesk stores only a
small, permitted, scrubbed summary.

**How long does short-term memory last?**  
Conversation and workflow values last 24 hours. Retrieval cache values last 300
seconds.

**How much long-term memory is recalled?**  
The service limits recall to 10 notes per customer.

**What types of long-term memory are allowed?**  
Preference, past issue, troubleshooting, and note.

**How are duplicates prevented?**  
The service searches for the same customer, type, scrubbed content, and source
ticket before inserting.

**What happens if resolution memory recording fails?**  
The SQL transaction rolls back so partial memory writes do not remain.

**Does Fakeredis represent a real Redis server?**  
No. It provides offline, in-process behavior for tests and demos. The real Redis
factory is selected when `REDIS_URL` is configured.

**What is the strongest one-sentence summary of Phase 8?**  
“Phase 8 gives CloudDesk two safe memory tiers: Redis for temporary workflow
context and SQL for limited, scrubbed, de-duplicated customer facts.”
