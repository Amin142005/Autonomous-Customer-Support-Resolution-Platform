# Phase 4 — CloudDesk Support API

## A plain-language presentation

> **Use this as a speaking script.** The goal is to explain the system design in
> simple words, including to people who are not software specialists.

Phase 1 prepared the application foundation. Phase 2 gave CloudDesk organized
stored information and fictional example records. Phase 3 added login, role
checks, request tracking, rate limits, and audit records.

Phase 4 gives the application a first set of useful entry points for support
staff. These entry points allow the system to receive a ticket, show tickets,
show customer information, and show a customer's previous tickets.

At this stage, the API is a structured front desk. It receives properly formatted
requests, checks who is making the request, coordinates the needed data, and
returns a consistent response.

Phase 4 does not yet run the AI investigation workflow. It creates the API
foundation that later workflow and console features will use.

## The main idea

A support application needs predictable ways to ask CloudDesk for information.
For example:

- “Show me the latest tickets.”
- “Create a ticket for this customer.”
- “Show me everything relevant about customer Avery.”
- “Show this customer’s previous tickets.”

These requests go through an API, which means a clearly defined set of digital
doors with known inputs and outputs.

```text
Support application or future frontend
  └─ Sends an HTTP request
       └─ Authentication and role check
            └─ API router receives the request
                 └─ Pydantic validates the request shape
                      └─ Ticket or customer service coordinates the work
                           └─ Repository reads or writes the database
                                └─ Safe Pydantic response is returned
```

The components have separate responsibilities:

- **API routers** accept web requests and apply authentication.
- **Pydantic schemas** define and validate request and response shapes.
- **Services** coordinate business operations and meaningful errors.
- **Repositories** communicate with the database.
- **The database** stores customers, tickets, workspaces, subscriptions, and memory.

## The three Phase 4 pieces

### 1. P4-1 — The shared API contract

P4-1 created the agreed language for ticket and customer information.

The API contract is documented in `docs/API_CONTRACT.md`. It describes the
available routes, who may use them, and what a request or response may contain.
The backend also has Pydantic schemas, and the planned frontend has matching
TypeScript types.

For example, a ticket creation request can include:

- a subject;
- a body;
- a channel, such as email, chat, web, or API;
- either an existing customer ID or new customer details;
- optionally, a workspace ID.

A customer source is important. The system does not allow a ticket to contain both
an existing customer ID and a completely separate customer object. It must identify
one customer source clearly.

The shared contract also defines:

- ticket categories;
- ticket severity;
- ticket status;
- ticket messages;
- customer subscriptions;
- customer workspaces;
- safe customer memory;
- list responses containing an `items` collection.

**Why it matters:** without one shared contract, the backend and frontend could
disagree about field names or response shapes. A shared contract makes integration
more predictable and makes future features easier to build.

### 2. P4-2 — Ticket APIs

P4-2 created the APIs for working with tickets:

| Operation | Minimum role | Everyday meaning |
|---|---|---|
| List tickets | Viewer | Show a collection of tickets |
| Get ticket detail | Viewer | Show one ticket, its messages, customer, and workspace |
| Create ticket | Agent | Add a new support ticket |

A viewer can read ticket information but cannot create a ticket. An agent or
admin can create tickets because agents and admins rank above viewers.

The list route can be narrowed using status, category, and severity filters.
It also supports `limit` and `offset`, so the application can request a manageable
number of records rather than loading every ticket at once.

**Why it matters:** the system separates reading information from creating it,
so a read-only employee cannot accidentally change support records.

## How ticket creation works

Imagine an agent receives a customer request by email and wants CloudDesk to
create a support ticket.

```text
Agent sends ticket information
  └─ API checks that the caller is an agent
       └─ Pydantic validates the subject, body, channel, and customer source
            └─ Ticket service searches for or creates the customer
                 └─ Ticket service validates the workspace if supplied
                      └─ Repository assigns the next ticket number
                           └─ Ticket and original message are saved
                                └─ The full ticket detail is returned
```

The ticket number is generated in sequence, for example `CD-1002` after
`CD-1001`.

The system can handle two customer cases:

1. **Existing customer:** the supplied customer ID is found in the database.
2. **New customer:** the system checks whether the email already belongs to a
   customer. If not, it creates a customer record.

If a workspace ID is supplied, CloudDesk verifies that the workspace belongs to
the identified customer. A workspace for another customer is not accepted.

The original customer message is stored as a ticket message. After the database
changes are completed, the service commits the transaction and returns a complete
ticket with the customer, optional workspace, and messages.

**Why it matters:** one API request can create several related pieces of
information consistently. The customer, ticket, and original message remain
connected.

### 3. P4-3 — Customer APIs

P4-3 created the APIs for working with customer context:

| Operation | Minimum role | Everyday meaning |
|---|---|---|
| List customers | Viewer | Show the customer directory |
| Get customer detail | Viewer | Show subscriptions, workspaces, tickets, and memory |
| Get customer tickets | Viewer | Show a customer's ticket history |

Customer detail is designed to help a support team prepare for a conversation.
It can show:

- the customer's name and company;
- the customer's plan;
- active or previous subscriptions;
- one or more workspaces;
- recent or associated tickets;
- up to ten saved memory notes.

The memory notes are safe context, not raw copies of every customer message.
Before returning a note, the customer service masks likely password or secret
assignments and recognizable card numbers.

**Why it matters:** a support agent can see the customer's relevant account
context, while likely sensitive values are not repeated in the API response.

## How customer detail works

```text
Support agent requests one customer
  └─ API verifies viewer or stronger role
       └─ Customer service asks for customer context
            └─ Repositories gather customer, subscriptions, workspaces,
               tickets, and memory
                 └─ Tickets are ordered newest first
                      └─ Memory notes are limited and redacted
                           └─ One customer-detail response is returned
```

The customer ticket-history route uses a separate, customer-specific repository
query. It does not return another customer's tickets. Its result is ordered newest
first and supports pagination.

## The role and safety rules

Phase 4 relies on the role system from Phase 3.

```text
Viewer
  └─ May list and view tickets
  └─ May list and view customers

Agent
  └─ Has every viewer permission
  └─ May create tickets

Admin
  └─ Has every agent permission
  └─ Retains administrative permissions for later features
```

The role check happens on the API route before the service performs its work.
This means the UI should not be the only place where permissions are enforced.

The APIs also use clear HTTP status responses:

- `200` means a read operation succeeded.
- `201` means a ticket was created.
- `401` means a valid login is missing or invalid.
- `403` means the signed-in role is not sufficient.
- `404` means the requested ticket or customer was not found.
- `422` means the request is invalid or uses invalid field values.

## Pydantic and typed responses

Pydantic is used as a quality-control boundary.

It can:

- reject an invalid ticket channel;
- reject an invalid category or status;
- require a subject and body for a new ticket;
- require exactly one customer source;
- convert database records into predictable response fields;
- provide default empty collections for lists.

The backend response models avoid exposing every database detail. For example,
customer memory is converted into a small, safe response with:

- memory ID;
- memory type;
- scrubbed content;
- optional source ticket ID;
- creation time.

This is the same principle used for the ticket response: return the fields needed
by support workflows and the future console, not unrelated database internals.

## How the components fit together

```text
docs/API_CONTRACT.md
  └─ Defines routes and JSON shapes
       └─ backend/app/schemas/
            └─ Validates request and response data
                 └─ backend/app/api/
                      └─ Checks role and accepts HTTP requests
                           └─ backend/app/services/
                                └─ Coordinates validation and data operations
                                     └─ backend/app/repositories/
                                          └─ Reads or writes SQLAlchemy models
                                               └─ SQLite or PostgreSQL data

frontend/lib/types.ts
  └─ Mirrors the backend contract for future UI development
```

This is a four-part flow: contract, transport, coordination, and storage.
Keeping these parts separate makes the system easier to test and modify.

## A simple ticket example

An agent asks for ticket `CD-1001`.

1. The API receives the ticket ID.
2. The viewer-or-higher role check passes.
3. The ticket repository searches for the ticket and loads its customer,
   workspace, and messages.
4. The ticket service converts the database objects into a ticket detail response.
5. The API returns the ticket with its customer summary and messages.

An unknown ticket ID is handled as a normal `404` response instead of becoming a
server failure.

## A simple customer example

An agent asks for a customer detail page.

1. The API receives the opaque customer ID.
2. The viewer-or-higher role check passes.
3. The customer repository loads the customer's subscriptions, workspaces,
   tickets, and memory relationships.
4. The customer service orders tickets, limits memory notes, and scrubs likely
   sensitive values.
5. The API returns one predictable customer context response.

## What Phase 4 does not do

Phase 4 does not yet:

- run the LangGraph support workflow;
- classify or assess ticket severity;
- search the knowledge base;
- produce an AI diagnosis or response;
- send a real customer email;
- issue a real refund;
- reset account settings;
- pause for human approval;
- escalate tickets by policy.

Those functions belong to later phases. The API routes created in Phase 4 provide
the ticket and customer foundation for those future capabilities.

## Why the layered design is important

The API routes do not write SQL directly. The repositories own database queries,
while services coordinate repository operations and convert data into meaningful
responses.

This division is useful because:

- HTTP and role concerns stay close to the API routers;
- database concerns stay in repositories;
- ticket and customer coordination stays in services;
- request and response shapes stay in Pydantic schemas;
- future frontend types can follow the documented contract.

The design is not simply about organizing folders. It gives CloudDesk clear
boundaries: the web layer accepts requests, the service layer performs coordinated
support operations, and the repository layer communicates with storage.

## Short answers for likely questions

**Can a viewer create a ticket?**  
No. Ticket creation requires the agent role or higher.

**Can a viewer read customer information?**  
Yes. Customer detail and history are viewer-readable.

**How does the API prevent invalid data?**  
Pydantic checks request fields before the service performs database work.

**Can one customer accidentally receive another customer's ticket history?**  
No. The customer-history query first verifies that the customer exists and then
filters tickets using that customer ID.

**Are there direct refunds or real email actions in Phase 4?**  
No. These functions are not implemented, and the real integration is explicitly
out of scope for v1.

**Why return only some customer fields?**  
The API should expose the information support staff and the future console need,
not raw database details or sensitive memory content.

**Does this complete the entire support system?**  
No. Phase 4 completes the ticket and customer API foundation. Later phases add
knowledge retrieval, tools, rules, AI agents, workflow, approvals, memory updates,
and the agent console.

## Current validation note

Phase 4 includes P4-1, P4-2, and P4-3 as locally implemented work:

- the ticket and customer API contract is synchronized across documentation,
  Pydantic schemas, and frontend TypeScript types;
- ticket list, detail, and creation routes are implemented;
- customer list, detail, and ticket-history routes are implemented;
- focused customer and ticket API tests cover role behavior, data shape, missing
  resources, filters, workspace ownership, and memory redaction;
- the focused Phase 4 test set passed and Ruff checks passed.

No live PostgreSQL database or cloud service was used. P4-2 and P4-3 contain the
API foundation only; workflow routes are scheduled for later phases.
