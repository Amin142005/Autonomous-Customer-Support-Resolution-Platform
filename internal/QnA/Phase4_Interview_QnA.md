# Phase 4 — Interview Questions and Answers

This question bank covers **Phase 4: Support API**. The answers are suitable for
direct speaking. They distinguish implemented Phase 4 behavior from features that
belong to later phases.

Related reading:

- [Phase 4 plain-language explanation](../explain_codebase/phase4_explained.md)
- [Phase 4 system-design evolution](../design_evolution/Phase4_Project_System_Design_Evolution.md)
- [Phase 4 infrastructure evolution](../Infra_design_evolution/Phase4_Infra_design_evolution.md)
- [Phase 4 task status](../../TASK.md)

## 30-second overview

**Q: Can you summarize Phase 4?**  
**A:** “Phase 4 adds the first support-facing API to CloudDesk. P4-1 defines a
shared ticket and customer contract. P4-2 adds ticket list, detail, and creation
routes. P4-3 adds customer list, detail, and ticket-history routes. The routes
use Pydantic schemas, role checks, services, repositories, and an async database
session. AI investigation and the workflow screen are not implemented yet.”

**Q: What is the main architectural goal of this phase?**  
**A:** “The goal is to expose safe, typed ticket and customer operations while
keeping HTTP concerns, business coordination, validation, and database access in
separate layers.”

## Product scope

### 3. What problem does the Support API solve?

**A:** “It gives support applications predictable ways to create tickets, read
ticket information, inspect customer context, and view a customer's previous
tickets.”

### 4. Which Phase 4 subtasks were completed?

**A:** “P4-1 added the ticket and customer API contract. P4-2 added the ticket
API. P4-3 added the customer API.”

### 5. Did P4-2 and P4-3 depend on P4-1?

**A:** “Yes. P4-1 established the contract first so ticket and customer routes
could use the same field names, enum values, list shapes, and response structures.”

### 6. Does Phase 4 implement the complete support workflow?

**A:** “No. It implements the API foundation for later knowledge, AI, workflow,
approval, escalation, and frontend features.”

### 7. Can Phase 4 send real emails or issue real refunds?

**A:** “No. Those integrations are intentionally not implemented in v1. The phase
does not perform real customer messaging or financial transactions.”

### 8. Is the frontend implemented in Phase 4?

**A:** “No. Phase 4 provides backend routes and TypeScript contract types for
future frontend use. A running Next.js application is not part of this phase.”

### 9. Is Docker implemented in Phase 4?

**A:** “No. Phase 4 runs as a local FastAPI process using SQLite or a configured
database. Docker Compose and container networking remain later delivery work.”

## API contract

### 10. What is an API contract?

**A:** “It is the agreed description of route paths, HTTP methods, permissions,
request fields, response fields, and status codes. The project keeps it in
`docs/API_CONTRACT.md`.”

### 11. Why is Pydantic used?

**A:** “Pydantic validates incoming JSON and defines predictable response shapes.
It can reject invalid enums or missing fields before database or service work
begins.”

### 12. How are backend and frontend types kept consistent?

**A:** “Pydantic models define the backend contract, while `frontend/lib/types.ts`
mirrors the ticket and customer domain types. The API document is the written
source of truth for route and payload decisions.”

### 13. What happens if the contract and implementation disagree?

**A:** “The contract, Pydantic schemas, frontend types, and API tests should be
updated together. Otherwise a caller and server may interpret the same field
differently.”

### 14. Which shared domain values are used?

**A:** “The contract uses role, category, severity, status, and channel enums.
Examples include viewer, agent, and admin roles; low to critical severity; and
email, chat, web, or API channels.”

### 15. What list shape does the API use?

**A:** “List endpoints return an object containing an `items` array. This gives
callers a consistent collection envelope.”

### 16. How are pagination values handled?

**A:** “Ticket and customer list routes use `limit` and `offset` query parameters.
The ticket history route also supports limits and offsets, while customer detail
limits memory notes separately.”

### 17. What HTTP status codes does Phase 4 use?

**A:** “It uses 200 for successful reads, 201 for ticket creation, 401 for missing
or invalid authentication, 403 for insufficient role, 404 for missing resources,
and 422 for invalid input.”

## Ticket API

### 18. What ticket routes exist in Phase 4?

**A:** “A viewer or stronger role can list tickets and get ticket detail. An agent
or admin can create a ticket.”

### 19. How can the ticket list be filtered?

**A:** “It supports status, category, and severity filters, plus `limit` and
`offset` pagination.”

### 20. Can a viewer create a ticket?

**A:** “No. Ticket creation requires the agent role or a higher role.”

### 21. Can an agent list and view tickets?

**A:** “Yes. The agent role inherits viewer permissions and adds support actions
such as ticket creation.”

### 22. What fields are required to create a ticket?

**A:** “The request requires subject, body, channel, and exactly one customer
source: either `customer_id` or a `customer` object.”

### 23. What is `customer_id` used for?

**A:** “It identifies an existing customer. The ticket service retrieves that
customer and rejects creation if the ID does not exist.”

### 24. How is a new customer created during ticket creation?

**A:** “The request may include customer name and email with optional company and
plan. The service first searches by normalized email. If no customer exists, it
creates one.”

### 25. Why does the API require exactly one customer source?

**A:** “It prevents ambiguity from combining an existing customer ID with separate
customer details. The Pydantic model validator rejects both or neither.”

### 26. How does a workspace get linked to a ticket?

**A:** “If a workspace ID is supplied, the service loads the workspace and verifies
that its `customer_id` equals the ticket's customer ID.”

### 27. What happens if the workspace belongs to another customer?

**A:** “It is rejected as a customer-workspace mismatch. The implementation returns
404 to avoid exposing whether the mismatched workspace is a valid resource.”

### 28. What ticket number is assigned?

**A:** “The repository calculates the next numeric suffix after the highest existing
`CD-*` ticket number. For example, the demo starts at `CD-1001` and a later new
ticket could receive `CD-1002`.”

### 29. Does ticket creation store the original customer message?

**A:** “Yes. After creating the ticket, the service creates a `TicketMessage` with
author type `customer` and the original request body.”

### 30. Is ticket creation committed atomically?

**A:** “The ticket and original message are created through the same session and
committed together by `TicketService`. Reloading the complete detail happens after
the commit.”

### 31. What does ticket detail return?

**A:** “It returns ticket summary fields plus a customer summary, optional
workspace summary, and ordered ticket messages.”

### 32. What does the detail repository eager-load?

**A:** “It loads the ticket's customer relationships, workspace, and messages so
the service can build a complete detail response.”

### 33. What happens for an unknown ticket ID?

**A:** “The service raises a 404-style service error, and the route converts it
to an HTTP 404 detail response.”

## Customer API

### 34. What customer routes exist in Phase 4?

**A:** “Viewer or stronger roles can list customers, get one customer detail, and
get that customer's ticket history.”

### 35. What is returned by the customer list route?

**A:** “It returns a list of `CustomerSummary` objects containing ID, name, email,
company, and plan.”

### 36. What does customer detail contain?

**A:** “It contains the customer summary plus subscriptions, workspaces, associated
tickets, and up to ten memory notes.”

### 37. Why is customer memory limited?

**A:** “The API should provide useful remembered context without loading an
unbounded history into every detail response.”

### 38. How are memory notes protected?

**A:** “The customer service scrubs likely password assignments, API keys, tokens,
secrets, and recognizable card numbers before converting notes into response
models.”

### 39. Does redaction delete the original memory record?

**A:** “No. It creates a redacted response value. The existing database record is
not rewritten by the customer detail operation.”

### 40. How is customer ticket history filtered?

**A:** “The service first verifies that the customer exists, then calls
`list_for_customer()` with that exact customer ID.”

### 41. Can one customer retrieve another customer's history?

**A:** “No. The repository query filters by the requested customer ID. The API
also uses the authenticated viewer role but does not perform cross-customer
authorization at this point because all support roles are allowed to inspect
support customer context.”

### 42. Are customer tickets ordered in a specific way?

**A:** “Yes. Customer detail sorts tickets newest first in the service, and the
customer-history repository orders results newest first.”

### 43. What happens for an unknown customer ID?

**A:** “Customer detail and history return a controlled 404 response with
`Customer not found`.”

## Architecture and layering

### 44. What are the main Phase 4 layers?

**A:** “The API contract, Pydantic schemas, API routers, ticket and customer
services, repositories, and database models.”

### 45. What is the responsibility of an API router?

**A:** “It receives HTTP requests, declares role dependencies and response models,
calls the appropriate service, and translates service errors into HTTP errors.”

### 46. Should an API route execute SQL?

**A:** “No. SQL is kept in repositories. The route should remain an HTTP and
validation boundary.”

### 47. What is the responsibility of a service?

**A:** “A service coordinates repositories and applies operation-specific logic,
such as customer linking, workspace ownership validation, ticket numbering,
pagination, ordering, and memory redaction.”

### 48. What is the responsibility of a repository?

**A:** “A repository builds SQLAlchemy queries and persists or loads entities.
It does not decide HTTP status codes or call an AI model.”

### 49. Why use repositories instead of direct SQL in routes?

**A:** “Repositories make queries reusable and testable. They keep database
details out of HTTP code and allow future services and agents to share data-access
logic.”

### 50. What is a service error in this implementation?

**A:** “It is a small Python exception that carries an HTTP detail and status code.
The API router catches it and raises an appropriate FastAPI `HTTPException`.”

### 51. Is this an anti-corruption or clean-architecture pattern?

**A:** “It is a layered application design with separate API, service, and
repository responsibilities. The route does not expose raw SQLAlchemy entities
directly; Pydantic converts them into response models.”

### 52. Why use Pydantic `ConfigDict(from_attributes=True)`?

**A:** “It allows response schemas to validate values from SQLAlchemy-style
objects by reading attributes instead of requiring dictionaries.”

### 53. Why not return raw database entities?

**A:** “Raw entities can expose fields, relationships, or internal values that
the API contract does not intend to publish. Typed responses return only support-
appropriate fields.”

## FastAPI and dependency injection

### 54. How does role enforcement work in the routes?

**A:** “The route declares `require_role(Role.VIEWER)` or
`require_role(Role.AGENT)` as a FastAPI dependency. FastAPI runs that dependency
before the route operation.”

### 55. How does a route get a database session?

**A:** “It uses `Depends(get_session)`. The database dependency creates an
`AsyncSession` from the application's session factory and closes it after the
request.”

### 56. Does each route create a database engine?

**A:** “No. Application startup creates an async engine and session factory.
Routes reuse them through request-scoped sessions.”

### 57. How does the app support SQLite and PostgreSQL?

**A:** “It reads `DATABASE_URL` during lifespan startup. SQLAlchemy entity models
and the session factory remain the same while SQLite or PostgreSQL is selected
by configuration.”

### 58. What does `response_model` do?

**A:** “It validates and filters the route's returned value into the declared
Pydantic shape. It also makes the response visible in API documentation.”

### 59. How are invalid Pydantic requests handled?

**A:** “FastAPI normally returns a 422 validation response. This includes invalid
enum values, missing required fields, and failed custom validators.”

## Transactions and consistency

### 60. What is a database transaction here?

**A:** “It is a unit of database work that is committed or rolled back together.
Ticket creation uses one session and commits the ticket plus original message
together.”

### 61. What could fail during ticket creation?

**A:** “The customer lookup or creation could fail, the workspace could be missing
or mismatched, the ticket insert could fail, or the message insert could fail.”

### 62. What happens if a later ticket creation step fails?

**A:** “The transaction has not been committed, so database changes made in that
session should not be left as an independently committed support record.
Operational error handling should also surface the failure instead of presenting
partial success.”

### 63. Why reload ticket detail after creation?

**A:** “Reloading ensures the response reflects the committed database state and
includes relationships such as customer, workspace, and messages.”

### 64. Is the next ticket number guaranteed under concurrent requests?

**A:** “The current repository calculates the highest existing numeric suffix.
It is simple for the demo but does not provide a separate database sequence or
concurrency-safe ticket-number reservation. A production design may need a
sequence or unique allocation mechanism.”

### 65. Why is this an honest follow-up limitation?

**A:** “Because interview answers should distinguish an offline demo implementation
from a production-grade high-concurrency allocation strategy.”

## Security and privacy

### 66. How does Phase 4 prevent a viewer from creating tickets?

**A:** “The `POST /api/v1/tickets` route declares an agent minimum role. The
backend compares the authenticated role rank before executing the service.”

### 67. How does it prevent raw memory data from reaching the API?

**A:** “It returns a dedicated `CustomerMemoryResponse` and scrubs likely secrets
and card numbers before adding it to customer detail.”

### 68. Does the memory scrubber guarantee that all secrets are found?

**A:** “No. It uses regex patterns for likely assignment and card-number formats.
The full memory policy will require stronger secret classification and careful
database write and log handling in later phases.”

### 69. Can a browser receive the database service-role key in Phase 4?

**A:** “No. The server-only database credential stays on the backend. Pydantic
responses contain support fields, not database credentials.”

### 70. What happens to audit logs for POST ticket creation?

**A:** “The existing audit middleware recognizes POST as state-changing and may
record actor ID, method, path, status, and request ID. It does not change the
route response if audit persistence fails.”

## Testing

### 71. How was the Phase 4 API tested?

**A:** “Focused FastAPI tests use an in-memory SQLite database and an ASGI
transport. They issue bearer tokens and call the ticket and customer routes.”

### 72. Which ticket behaviors are covered?

**A:** “List and detail reads, filters, missing resources, agent-only creation,
viewer rejection, customer linking or creation, workspace mismatch, and original
message creation.”

### 73. Which customer behaviors are covered?

**A:** “Customer list and detail, subscriptions, workspaces, associated tickets,
history, missing customer responses, authentication, role access, and memory
redaction.”

### 74. Why use an in-memory database for tests?

**A:** “It gives repeatable offline tests without a Docker container or live
PostgreSQL account.”

### 75. Why use ASGITransport instead of opening a TCP port?

**A:** “It sends HTTP requests directly to the FastAPI application object. It tests
routing and middleware behavior without starting a separate server process.”

### 76. Did the focused test set pass?

**A:** “Yes. The Phase 4 customer and ticket focused tests passed, and Ruff
checks passed for the changed implementation.”

### 77. Was a live database or cloud service used?

**A:** “No. Validation used local SQLite and offline test settings.”

## Infrastructure and routing

### 78. How are routers mounted?

**A:** “`create_app()` includes the ticket and customer routers with
`/api/v1` prefixes. Their own routers add `/tickets` and `/customers`.”

### 79. What middleware wraps the routes?

**A:** “Request-ID middleware is outermost, followed by audit, rate limiting,
CORS, and FastAPI route dispatch.”

### 80. Why is request-ID middleware outermost?

**A:** “It ensures every response, including middleware and error responses,
receives a trace ID.”

### 81. How does CORS fit into the API?

**A:** “CORS is applied around FastAPI to control browser origins and expose
`X-Request-ID`. It is not a substitute for authentication or role enforcement.”

### 82. Does ticket or customer data go to Redis?

**A:** “No. Redis is used by rate limiting in this phase. Ticket and customer
records go through the SQLAlchemy database session.”

### 83. Is there a separate ticket microservice?

**A:** “No. Ticket and customer routes run in the same FastAPI process.”

### 84. What is the database session lifecycle?

**A:** “Application startup creates an async engine and session factory. Each
route dependency creates a session for the request and closes it afterward.”

### 85. Is a Docker network used today?

**A:** “No. The current components communicate through local Python objects and
local database/cache connections. Docker networking is future delivery work.”

## Follow-up and limitations

### 86. What are Phase 4's biggest limitations?

**A:** “It does not run an AI workflow, knowledge retrieval, workflow state,
workflow events, human approvals, or real integrations. Ticket numbering is a
simple highest-existing-suffix approach rather than a production sequence.”

### 87. Is Phase 4 a complete agent console backend?

**A:** “No. It supplies list, detail, and creation APIs. Later workflow, evidence,
action, approval, and reply routes are still required.”

### 88. How would a future frontend use these routes?

**A:** “A frontend could list and filter tickets, open ticket detail, create a
ticket, open customer detail, and display customer history using the typed API
client.”

### 89. How does this phase prepare for AI agents?

**A:** “Future agents can use repository-backed customer and ticket context while
keeping SQL outside the agent layer. Pydantic schemas provide predictable domain
inputs and outputs.”

### 90. How would a workflow route avoid duplicating ticket logic?

**A:** “It should use existing services and repositories rather than writing
route-specific database code. Workflow and approval work belongs in later
services and graph nodes.”

### 91. Why is customer detail safer than raw database access?

**A:** “It exposes selected support fields and redacts likely memory secrets.
The browser is not given raw entity relationships or database credentials.”

### 92. What did P4-1 add that P4-2 and P4-3 use?

**A:** “It added a shared written contract and Pydantic/TypeScript representations
for ticket summaries, ticket detail, customer summaries, customer detail, and list
responses.”

### 93. What did P4-2 add?

**A:** “It added ticket routes, `TicketService`, customer/workspace validation,
ticket-number allocation, original-message creation, detail eager-loading, and
focused API tests.”

### 94. What did P4-3 add?

**A:** “It added customer routes, `CustomerService`, customer-context assembly,
customer-only history, memory redaction, and focused API tests.”

### 95. What would you improve in a production version?

**A:** “I would add stronger memory-secret classification, distributed ticket
number allocation, explicit transaction error handling, cursor or keyset
pagination, database indexes, cache plans, and end-to-end frontend contract tests.
Live container, database, and observability integration would come with delivery
work.”

### 96. What did you learn from separating API, service, and repository layers?

**A:** “I learned that HTTP, business coordination, and SQL concerns become easier
to test when they have separate homes. It also makes role enforcement and response
validation consistent across routes.”

### 97. How can Phase 4 evolve into the agent console?

**A:** “Later pages can call the typed customer and ticket routes, while workflow
and action routes are added for agent runs, evidence, approvals, replies, and
escalations.”

### 98. What is the safest way to explain Phase 4 to a non-technical interviewer?

**A:** “Describe it as the structured front desk: it verifies who is asking,
understands the request, connects ticket or customer records, removes unsafe
details, and returns a consistent answer.”
