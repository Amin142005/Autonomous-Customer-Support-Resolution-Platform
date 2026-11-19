# Phase 8 — Interview Questions and Answers

This question bank covers **Phase 8: Memory**. The answers are written for
interview speaking, distinguish implemented behavior from future LangGraph
integration, and include both beginner-friendly and technical explanations.

Related reading:

- [Phase 8 plain-language explanation](../explain_codebase/phase8_explained.md)
- [Phase 8 system-design evolution](../design_evolution/Phase8_Project_System_Design_Evolution.md)
- [Phase 8 infrastructure evolution](../Infra_design_evolution/Phase8_Infra_design_evolution.md)
- [Phase 8 task status](../../TASK.md)
- [Phase 11 memory exit criteria](../../PLAN_PHASE.md)

## 30-second overview

### 1. Can you summarize Phase 8?

**A:** “Phase 8 creates two memory tiers. Redis or Fakeredis holds temporary
ticket conversations, workflow state, and retrieval cache. SQLAlchemy holds
safe, permanent customer facts. A unified memory service coordinates recall
and resolution recording.”

### 2. What problem does Phase 8 solve?

**A:** “Support workflows need temporary context during an active run and useful
customer facts across future runs. Phase 8 keeps those needs separate so
temporary data expires and durable data remains limited and safe.”

### 3. What are the three Phase 8 subtasks?

**A:** “P8-1 adds short-term Redis memory, P8-2 adds a safe SQL long-term
memory facade, and P8-3 adds a unified recall-and-record service.”

### 4. Which memory stores are used?

**A:** “Redis or Fakeredis for short-term memory and SQLite or PostgreSQL through
SQLAlchemy for long-term customer memory.”

### 5. Is Redis the system of record?

**A:** “No. Redis stores temporary conversation, workflow, and cache values.
Customer memory is stored in SQL through `CustomerMemoryRepository`.”

### 6. Does Phase 8 implement LangGraph memory nodes?

**A:** “No. It implements the memory facades that later `customer_context` and
`memory_update` graph nodes can call.”

### 7. Does Phase 8 add an HTTP memory route?

**A:** “No. It adds Python memory components. Existing customer API behavior
can read the SQL memory table, but there is no dedicated P8 memory route.”

### 8. What is the central memory principle?

**A:** “Keep temporary context temporary and permanent facts narrow. Do not copy
raw tickets or secrets into long-term memory.”

### 9. Why use a service instead of calling Redis and SQL directly?

**A:** “A service gives future workflow nodes one interface and prevents each
node from repeating key names, SQL code, transaction logic, scrubbing, and
duplicate checks.”

### 10. What is the strongest one-sentence Phase 8 summary?

**A:** “Phase 8 creates a two-tier memory system: Redis for short-lived
workflow context and SQL for safe, customer-scoped, de-duplicated facts.”

## P8-1 — Short-term Redis memory

### 11. What does `ShortTermMemory` hold?

**A:** “It holds ticket conversations, workflow state, and RAG retrieval cache
values.”

### 12. Which Redis key is used for a ticket conversation?

**A:** “`conversation:{ticket_id}`.”

### 13. Which Redis key is used for workflow state?

**A:** “`workflow:{workflow_id}`.”

### 14. What is the retrieval-cache key?

**A:** “`rag:{mode}:{category}:{top_k}:{query}`.”

### 15. What is the conversation TTL?

**A:** “24 hours.”

### 16. What is the workflow-state TTL?

**A:** “24 hours.”

### 17. What is the retrieval-cache TTL?

**A:** “300 seconds.”

### 18. Why use TTLs?

**A:** “TTL prevents temporary context and cache values from remaining
indefinitely.”

### 19. What does TTL mean in plain language?

**A:** “A TTL is an expiration time. After the time is reached, the store
automatically removes the temporary value.”

### 20. How are values stored?

**A:** “The facade JSON-encodes conversation lists, workflow objects, and cache
values before writing them to Redis.”

### 21. What operations exist for conversations?

**A:** “Set, append, get, and delete.”

### 22. What operations exist for workflow state?

**A:** “Set, get, and delete.”

### 23. What operations exist for retrieval cache?

**A:** “Set, get, and delete.”

### 24. How is a missing conversation returned?

**A:** “It is returned as an empty list.”

### 25. How is missing workflow state returned?

**A:** “It is returned as `None`.”

### 26. How is a missing cache value returned?

**A:** “It is returned as `None`.”

### 27. How is the RAG cache key normalized?

**A:** “Mode and category are lowercased or trimmed, query whitespace is
collapsed, the query is lowercased, and `top_k` is validated.”

### 28. What happens if no category is supplied?

**A:** “The key uses `all` as the category.”

### 29. What does Fakeredis provide?

**A:** “It provides Redis-like behavior in the Python test process, allowing
offline tests without a real Redis server.”

### 30. When does the factory select Fakeredis?

**A:** “When `USE_FAKE_REDIS=true` or `REDIS_URL` is empty.”

### 31. When does the factory select real Redis?

**A:** “When `REDIS_URL` is configured and the fake Redis setting is false.”

### 32. Is a Fakeredis value shared with later processes?

**A:** “No. Fakeredis state is process-local. A real Redis URL provides shared
state across backend processes.”

### 33. What is the short-term memory protocol?

**A:** “It is a Python protocol with async methods for get, set, delete, exists,
increment, expire, TTL, ping, and close behavior.”

### 34. Why is a protocol useful?

**A:** “It lets short-term code accept both a real Redis client and Fakeredis
as long as they implement the required async methods.”

### 35. Does P8-1 integrate caching into the RAG retriever?

**A:** “Not yet. P8-1 provides cache operations for future RAG integration.”

## P8-2 — Long-term customer memory

### 36. What does `LongTermMemory` do?

**A:** “It recalls and records durable, customer-scoped memory through
SQLAlchemy and the memory repository.”

### 37. Which SQL entity stores long-term memory?

**A:** “The `CustomerMemory` entity, stored in `customer_memory`.”

### 38. Which repositories does it use?

**A:** “`CustomerRepository`, `TicketRepository`, and
`CustomerMemoryRepository`.”

### 39. What are the permitted note types?

**A:** “`preference`, `past_issue`, `troubleshooting`, and `note`.”

### 40. Why restrict note types?

**A:** “It prevents future code from storing arbitrary raw ticket or system
payloads in the memory table.”

### 41. What is the recall limit?

**A:** “Between 1 and 10 notes. The service default is 10.”

### 42. How are recalled notes ordered?

**A:** “Newest first.”

### 43. Are recall notes filtered by customer?

**A:** “Yes. The repository query starts with `customer_id`.”

### 44. What happens if the customer is missing?

**A:** “The facade raises `LookupError`.”

### 45. What happens if recall limit is invalid?

**A:** “A `LongTermMemoryError` is raised for limits below 1 or above 10.”

### 46. What does `record()` return?

**A:** “It returns `(note, created)`, where `created` indicates whether a new
row was inserted.”

### 47. How are secrets handled at record time?

**A:** “The content passes through `scrub()` before the duplicate lookup and
database create.”

### 48. What values are scrubbed?

**A:** “Passwords, API keys, tokens, bearer and JWT values, private keys,
URL credentials, sensitive query values, AWS-style keys, and card numbers.”

### 49. What is an exact duplicate?

**A:** “A note with the same customer, type, scrubbed content, and source ticket
identifier.”

### 50. How are duplicates prevented?

**A:** “The repository performs an exact lookup before creating a note.”

### 51. What happens for an existing duplicate?

**A:** “The existing note is returned and `created=false`.”

### 52. Can an arbitrary source ticket be attached?

**A:** “No. The ticket must exist and belong to the same customer.”

### 53. Can raw ticket bodies be stored?

**A:** “No. The facade rejects content that exactly matches or contains the raw
source ticket body.”

### 54. Can a note be stored without a source ticket?

**A:** “Yes. `source_ticket_id` is optional.”

### 55. Is `source_ticket_id` a foreign key?

**A:** “The database model includes a foreign key to `tickets.id`; the facade
also checks customer ownership before recording.”

### 56. Is long-term memory permanent?

**A:** “The current design stores it permanently in SQL until it is manually
changed or removed. P8 does not implement retention expiration.”

### 57. Does P8 implement memory deletion?

**A:** “It provides delete for the short-term facade, but not a long-term
deletion or retention API.”

### 58. Is long-term recall safe at output time?

**A:** “The customer detail service scrubs memory again before response
serialization, and P8 write logic also scrubs before storage.”

### 59. How does P8 prevent another customer's memory from being recalled?

**A:** “The SQL query always begins with the requested customer ID.”

### 60. Why use a facade rather than direct `CustomerMemoryRepository` calls?

**A:** “The facade combines customer validation, ticket ownership, note-type
validation, scrubbing, and duplicate behavior in one place.”

## P8-3 — Recall and record service

### 61. What does `MemoryService` coordinate?

**A:** “It coordinates `ShortTermMemory` and `LongTermMemory`.”

### 62. What is `recall_customer()`?

**A:** “It delegates to `LongTermMemory.recall()` and returns up to 10 notes for
one customer.”

### 63. What is `record_resolution()`?

**A:** “It records a past issue, up to three troubleshooting steps, and a
resolution note for a completed ticket.”

### 64. How many troubleshooting steps are stored?

**A:** “A maximum of three. The service truncates an iterable list to the first
three valid, nonblank steps.”

### 65. What note types does resolution recording create?

**A:** “One `past_issue`, up to three `troubleshooting`, and one `note`.”

### 66. What is a successful resolution summary shape?

**A:** “Past issue plus the useful first steps plus a concise resolution
summary.”

### 67. Does resolution memory store the entire ticket body?

**A:** “No. It stores the supplied summary fields, and the long-term facade
rejects raw or body-containing text.”

### 68. How are duplicates handled in `record_resolution()`?

**A:** “Each record is passed through `LongTermMemory.record()`. Duplicate
records return `created=false` rather than inserting a row.”

### 69. How is transaction consistency handled?

**A:** “All resolution records use the same SQLAlchemy session. Failure triggers
rollback; success commits once.”

### 70. What happens on a partial recording failure?

**A:** “The service rolls back the SQL transaction instead of leaving a partial
past-issue or resolution set.”

### 71. What happens to short-term data after a resolution?

**A:** “It remains governed by its own TTL and key. Resolution recording does
not automatically delete conversation or workflow Redis values.”

### 72. How does the service expose ticket conversation?

**A:** “It provides `get_conversation()` and `append_conversation()` methods
delegating to `ShortTermMemory`.”

### 73. How does it expose workflow state?

**A:** “It provides `get_workflow_state()` and `set_workflow_state()` methods
delegating to `ShortTermMemory`.”

### 74. Does the service connect RAG cache reads automatically?

**A:** “No dedicated cache convenience is exposed in `MemoryService`; P8-1
provides retrieval-cache operations in `ShortTermMemory`.”

### 75. What dependency is required to build `MemoryService`?

**A:** “A SQLAlchemy async session. Redis is optional because the short-term
facade can obtain or accept a Redis/Fakeredis client.”

## Redis and SQL architecture

### 76. Why use Redis and SQL together?

**A:** “Redis is fast and expires temporary values. SQL is the durable,
customer-scoped system of record for permitted memory facts.”

### 77. What belongs in Redis rather than SQL?

**A:** “Active ticket conversation, current workflow state, and temporary RAG
retrieval cache.”

### 78. What belongs in SQL rather than Redis?

**A:** “Permitted durable facts such as preferences, past issues,
troubleshooting history, and resolution summaries.”

### 79. Can Redis state restore a workflow after process restart?

**A:** “Not if it uses Fakeredis or Redis data expires. Real Redis can persist
data, but P8 does not implement graph checkpoint restoration.”

### 80. Is Redis the source of truth for customer memory?

**A:** “No. `customer_memory` in SQL is the long-term source of truth.”

### 81. Is SQL used for short-term conversation?

**A:** “No. P8 short-term conversation is routed to Redis or Fakeredis.”

### 82. What happens when `REDIS_URL` is blank?

**A:** “The factory uses Fakeredis unless the settings explicitly select
another setup.”

### 83. What happens when Redis is unavailable in a real configuration?

**A:** “P8 does not add a circuit-breaker or fallback at the memory facade
level. Future nodes should handle short-term memory failures deliberately.”

### 84. How are short-term values serialized?

**A:** “They are JSON encoded and decoded by `ShortTermMemory`.”

### 85. Is JSON serialization security sufficient?

**A:** “It is a storage format, not a secret or privacy guarantee. P8 prevents
raw and secret data from entering long-term memory through separate rules.”

## Repository and layering

### 86. Does `LongTermMemory` bypass repositories?

**A:** “No. It uses `CustomerRepository`, `TicketRepository`, and
`CustomerMemoryRepository` for all SQL operations.”

### 87. Does `MemoryService` contain HTTP behavior?

**A:** “No. It is a memory composition and SQL/Redis service with no HTTP
request handling.”

### 88. Does `ShortTermMemory` contain business rules?

**A:** “It contains key construction, JSON encoding, and TTL behavior, but no
customer-memory policy. Policy is in `LongTermMemory` and guardrails.”

### 89. Does `LongTermMemory` contain Redis behavior?

**A:** “No. It only composes SQL repositories and scrubbing.”

### 90. Why keep Redis and SQL facades separate?

**A:** “They have different lifetimes and failure behaviors. Separating them
keeps the system easier to test and lets future code change one store.”

## Testing and validation

### 91. How is P8-1 tested?

**A:** “Tests use Fakeredis to verify TTL constants, key formats, JSON round
trips, and conversation/workflow/cache operations.”

### 92. How is P8-2 tested?

**A:** “Tests use in-memory SQLite to verify permitted types, customer and
ticket ownership, recall limits, scrubbing, raw-ticket rejection, and duplicate
prevention.”

### 93. How is P8-3 tested?

**A:** “Tests verify recall, resolution memory shape, first-three step limit,
secret scrubbing, duplicate-safe recording, and separation of short-term and
long-term data.”

### 94. What local test count passed?

**A:** “The offline suite passed 182 tests after P8-3.”

### 95. Did Phase 8 use Docker or cloud credentials?

**A:** “No. Tests used Fakeredis and in-memory SQLite.”

### 96. Did Ruff pass?

**A:** “Yes. Ruff passed for the memory implementation and tests.”

## Honest status and limitations

### 97. Is P8 complete?

**A:** “P8-1, P8-2, and P8-3 are marked complete locally and have tests.
LangGraph memory node integration belongs to later work.”

### 98. Does P8 have a live Redis integration?

**A:** “The real Redis client factory exists, but local validation did not use
a live Redis server.”

### 99. Does P8 implement graph checkpoint persistence?

**A:** “No. Workflow-state Redis storage is separate from LangGraph checkpointer
implementation.”

### 100. What is the strongest final interview answer for Phase 8?

**A:** “Phase 8 implements two memory tiers: Redis for short-lived context and
SQL for safe, customer-scoped, scrubbed, de-duplicated facts. A unified memory
service exposes recall and resolution recording while keeping temporary state
separate from permanent memory.”
