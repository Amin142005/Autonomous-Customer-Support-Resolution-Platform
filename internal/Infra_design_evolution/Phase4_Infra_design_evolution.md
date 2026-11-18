# Phase 4 — Infrastructure and Component-Wiring Evolution

This document explains how the Phase 4 Support API components are wired into the
running application. It covers routing, middleware, database sessions, services,
repositories, and response paths. It also separates implemented process wiring
from the Docker and container networking that are planned for a later phase.

## Current infrastructure status

At the end of Phase 4, CloudDesk still runs as a local Python/FastAPI process.
The Phase 4 subtasks add API routers, Pydantic validation models, and service
components. They do not add Docker containers, a Compose file, a reverse proxy,
or a frontend deployment.

| Component | Phase 4 infrastructure state |
|---|---|
| FastAPI application | One local Uvicorn/ASGI process |
| Ticket API | Mounted in-process under `/api/v1/tickets` |
| Customer API | Mounted in-process under `/api/v1/customers` |
| Authentication | JWT verification inside the FastAPI process |
| Role checks | FastAPI dependencies inside each protected route |
| Database sessions | Async SQLAlchemy sessions created from the application factory |
| Redis | Real Redis or in-process FakeRedis |
| Frontend | Not implemented as a running container or server |
| Docker | No Dockerfile or Compose network is present yet |

The subtask wiring sequence is:

```mermaid
flowchart LR
    P41["P4-1: API contract and Pydantic schemas"]
    P42["P4-2: Ticket router, service, and repositories"]
    P43["P4-3: Customer router, service, and repositories"]

    P41 --> P42
    P41 --> P43
```

P4-1 defines the route and JSON contract. P4-2 and P4-3 then add separate HTTP
routers that consume that contract.

## Starting point — protected local API without support routes

Before Phase 4, FastAPI has authentication, request-ID, audit, rate-limit, CORS,
health, and demo-auth components. It also has an application database session
factory and repositories. However, it has no mounted ticket or customer API.

```mermaid
flowchart LR
    Caller["Browser or API caller"] -->|"HTTP request"| Uvicorn["Local Uvicorn process"]
    Uvicorn --> RequestId["Request-ID middleware"]
    RequestId --> Audit["Audit middleware"]
    Audit --> Rate["Rate-limit middleware"]
    Rate --> CORS["CORS middleware"]
    CORS --> FastAPI["FastAPI application"]
    FastAPI --> Health["Health routes"]
    FastAPI --> Auth["Authentication routes"]
    FastAPI -.->|"Not mounted yet"| Missing["Ticket and customer routes"]
    Missing -.-> Repositories["Phase 2 repositories"]
    Repositories -.-> Database["SQLite or PostgreSQL"]
```

The database session factory already exists, so Phase 4 does not create a second
server process or database connection system. It mounts new routers and has those
routers request sessions from the existing application state.

## P4-1 — Wire the API contract into backend and frontend types

P4-1 is primarily a contract wiring change. It gives the application named domain
and response structures before P4-2 and P4-3 add routes.

The contract has two technical copies:

1. `docs/API_CONTRACT.md` is the written route and payload contract.
2. Pydantic classes in `backend/app/schemas/` validate backend requests and shape
   backend responses.

The future frontend should mirror the contract in `frontend/lib/types.ts`. This
does not create a network call or container connection. It prevents the browser
and backend from treating the same values differently.

```mermaid
flowchart LR
    Writer["API contract in docs/API_CONTRACT.md"]
    Writer --> TicketSchemas["Ticket Pydantic schemas"]
    Writer --> CustomerSchemas["Customer Pydantic schemas"]
    TicketSchemas --> TicketRouter["Ticket API router"]
    CustomerSchemas --> CustomerRouter["Customer API router"]
    TicketSchemas --> FrontendTypes["Frontend ticket TypeScript types"]
    CustomerSchemas --> FrontendTypes
    FrontendTypes -->|"Future browser requests and typed responses"| Caller["Support frontend"]
```

Pydantic acts at the HTTP boundary:

- request JSON is converted into typed values;
- invalid channels, statuses, or required fields are rejected;
- ticket creation requires exactly one customer source;
- database entities are converted into response models.

**Infrastructure effect:** P4-1 adds no runtime network hop. It adds a validation
and transformation boundary that runs inside the FastAPI process.

## P4-2 — Wire ticket routes, ticket service, and repositories

P4-2 mounts a ticket router on the main FastAPI application:

```mermaid
flowchart LR
    FastAPI["create_app() FastAPI application"]
    FastAPI --> TicketInclude["include_router(ticket router, /api/v1)"]
    TicketInclude --> TicketRouter["Ticket router prefix /tickets"]
    TicketRouter --> List["GET /tickets"]
    TicketRouter --> Detail["GET /tickets/{ticket_id}"]
    TicketRouter --> Create["POST /tickets"]
```

The HTTP flow for the ticket API is:

```mermaid
flowchart TB
    Caller["API caller"] --> Uvicorn["FastAPI ASGI process"]
    Uvicorn --> RequestId["Request-ID middleware"]
    RequestId --> Audit["Audit middleware"]
    Audit --> Rate["Rate limiter"]
    Rate --> CORS["CORS middleware"]
    CORS --> TicketRouter["Ticket API router"]
    TicketRouter --> Role["require_role viewer or agent"]
    Role -->|"Allowed"| Pydantic["Pydantic request or response model"]
    Pydantic --> TicketService["TicketService"]
    TicketService --> TicketRepo["TicketRepository"]
    TicketService --> CustomerRepo["CustomerRepository"]
    TicketService --> WorkspaceRepo["WorkspaceRepository"]
    TicketService --> MessageRepo["TicketMessageRepository"]
    TicketRepo --> Session["Async SQLAlchemy session"]
    CustomerRepo --> Session
    WorkspaceRepo --> Session
    MessageRepo --> Session
    Session --> Database["SQLite or configured PostgreSQL"]
    Database --> Session
    Session --> TicketService
    TicketService --> TicketRouter
    TicketRouter --> CORS
    CORS --> Rate
    Rate --> Audit
    Audit --> RequestId
    RequestId --> Caller
```

### Ticket list route

`GET /api/v1/tickets` is routed to the ticket router. The viewer-or-higher role
dependency is evaluated before the service is called.

The query parameters for status, category, severity, limit, and offset are
Pydantic/FastAPI values. `TicketService` validates pagination limits, and
`TicketRepository` creates the SQLAlchemy filtered query.

```mermaid
sequenceDiagram
    participant Caller
    participant Router as Ticket Router
    participant Security as Role Dependency
    participant Service as TicketService
    participant Repo as TicketRepository
    participant Session as AsyncSession
    participant DB as SQLite or PostgreSQL

    Caller->>Router: GET /api/v1/tickets
    Router->>Security: Require viewer role
    Security-->>Router: AuthenticatedUser
    Router->>Service: list(filters, limit, offset)
    Service->>Repo: list_tickets(...)
    Repo->>Session: build SELECT with filters
    Session->>DB: execute query
    DB-->>Session: ticket rows
    Session-->>Repo: SQLAlchemy Ticket objects
    Repo-->>Service: ticket list
    Service-->>Router: TicketListResponse
    Router-->>Caller: 200 JSON items
```

### Ticket detail route

`GET /api/v1/tickets/{ticket_id}` asks `TicketService` for a complete ticket.
`TicketRepository.get_detail()` uses eager-loading to gather the customer,
workspace, and messages with one repository result path.

```mermaid
flowchart LR
    Caller["API caller"] --> Router["GET /tickets/{ticket_id}"]
    Router --> Role["Require viewer or higher"]
    Role --> Service["TicketService.get_detail"]
    Service --> Repo["TicketRepository.get_detail"]
    Repo --> Session["AsyncSession"]
    Session --> Database["Database"]
    Database -->|"Ticket plus relations"| Session
    Session --> Repo
    Repo --> Service
    Service -->|"Found"| Detail["TicketDetail Pydantic response"]
    Service -->|"Missing"| Error["404 Ticket not found"]
    Detail --> Caller
    Error --> Caller
```

### Ticket creation route

`POST /api/v1/tickets` is the more complex P4-2 request path. The route requires
an agent or admin, validates the Pydantic request, and gives it to
`TicketService`.

```mermaid
sequenceDiagram
    participant Caller as Agent
    participant Router as Ticket Router
    participant Service as TicketService
    participant Customer as CustomerRepository
    participant Workspace as WorkspaceRepository
    participant Ticket as TicketRepository
    participant Message as TicketMessageRepository
    participant Session as AsyncSession
    participant DB as Database

    Caller->>Router: POST /api/v1/tickets
    Router->>Router: Require agent role
    Router->>Router: Validate ticket JSON
    Router->>Service: create(request)
    alt customer_id supplied
        Service->>Customer: get_by_id
    else customer object supplied
        Service->>Customer: get_by_email
        opt No existing customer
            Service->>Customer: create customer
        end
    end
    opt workspace_id supplied
        Service->>Workspace: get_by_id
        Workspace-->>Service: workspace
        Service->>Service: Verify workspace belongs to customer
    end
    Service->>Ticket: next_ticket_number
    Service->>Ticket: create ticket
    Service->>Message: create original customer message
    Ticket-->>Session: queue changes
    Message-->>Session: queue changes
    Session->>DB: commit
    Service->>Ticket: reload ticket detail
    Ticket-->>Service: complete detail
    Service-->>Router: TicketDetail
    Router-->>Caller: 201 { ticket }
```

All repositories use the same request-scoped `AsyncSession`. The ticket, customer
link, workspace link, and original message are committed together. This is one
database transaction rather than independent network calls.

**Infrastructure effect:** P4-2 adds local in-process routing and repository
coordination. It does not open a separate ticket microservice or message queue.

## P4-3 — Wire customer routes, customer service, and redaction

P4-3 mounts a second in-process router on the main FastAPI application:

```mermaid
flowchart LR
    FastAPI["FastAPI application"]
    FastAPI --> CustomerInclude["include_router(customer router, /api/v1)"]
    CustomerInclude --> CustomerRouter["Customer router prefix /customers"]
    CustomerRouter --> List["GET /customers"]
    CustomerRouter --> Detail["GET /customers/{customer_id}"]
    CustomerRouter --> History["GET /customers/{customer_id}/tickets"]
```

The customer API follows the same middleware and session path as the ticket API:

```mermaid
flowchart TB
    Caller["API caller"] --> RequestId["Request-ID middleware"]
    RequestId --> Audit["Audit middleware"]
    Audit --> Rate["Rate limit"]
    Rate --> CORS["CORS"]
    CORS --> CustomerRouter["Customer API router"]
    CustomerRouter --> Role["Require viewer or higher"]
    Role --> CustomerService["CustomerService"]
    CustomerService --> CustomerRepo["CustomerRepository"]
    CustomerService --> MemoryRepo["CustomerMemoryRepository"]
    CustomerService --> TicketRepo["TicketRepository"]
    CustomerRepo --> Session["AsyncSession"]
    MemoryRepo --> Session
    TicketRepo --> Session
    Session --> Database["SQLite or PostgreSQL"]
    CustomerService -->|"redact memory notes"| Response["Pydantic customer response"]
    Response --> CustomerRouter
    CustomerRouter --> CORS
```

### Customer list route

The list route uses `CustomerRepository.list()` and a Pydantic
`CustomerListResponse`. It returns summary fields rather than subscriptions,
workspaces, or memory.

### Customer detail route

The detail route has the largest P4-3 component assembly:

```mermaid
flowchart LR
    Router["GET /customers/{customer_id}"]
    Router --> Role["Require viewer or higher"]
    Role --> Service["CustomerService.get_detail"]
    Service --> Customer["CustomerRepository.get_with_context"]
    Service --> Memory["CustomerMemoryRepository.list_for_customer"]
    Customer --> Session["AsyncSession"]
    Memory --> Session
    Session --> Database["Database"]
    Database --> Customer
    Database --> Memory
    Customer --> Relationships["Subscriptions, workspaces, tickets, memory"]
    Relationships --> Sort["Sort tickets newest first"]
    Sort --> Scrub["Redact likely secrets and card numbers"]
    Scrub --> Typed["CustomerDetail Pydantic response"]
    Typed --> Router
```

The redaction step runs inside `CustomerService`, not in the database or the HTTP
router. It masks likely password, API-key, token, secret, and card patterns before
the Pydantic memory objects leave the application.

### Customer ticket-history route

The history route verifies that the customer exists, then calls
`TicketRepository.list_for_customer()` with the requested customer ID and pagination
values.

```mermaid
sequenceDiagram
    participant Caller
    participant Router as Customer Router
    participant Service as CustomerService
    participant Customer as CustomerRepository
    participant Ticket as TicketRepository
    participant DB as Database

    Caller->>Router: GET /customers/{customer_id}/tickets
    Router->>Service: get_ticket_history(customer_id)
    Service->>Customer: get_by_id(customer_id)
    alt Customer missing
        Customer-->>Service: null
        Service-->>Caller: 404
    else Customer exists
        Service->>Ticket: list_for_customer(customer_id)
        Ticket->>DB: filtered newest-first paginated query
        DB-->>Ticket: only this customer's tickets
        Ticket-->>Service: Ticket entities
        Service-->>Router: CustomerTicketHistoryResponse
        Router-->>Caller: 200 items
    end
```

**Infrastructure effect:** P4-3 adds no external customer service. It combines
database relationships and an in-process redaction function inside the backend
process.

## Complete Phase 4 request and response routing

The final in-process topology has one FastAPI application, one application database
session factory, and two Support API routers. Middleware wraps every HTTP request.

```mermaid
flowchart TB
    Client["Browser or API client"]

    subgraph Process["One FastAPI process"]
        RequestId["Request-ID middleware"]
        Audit["Audit middleware"]
        Rate["Rate-limit middleware"]
        CORS["CORS middleware"]
        FastAPI["FastAPI route dispatcher"]
        Security["JWT and require_role dependencies"]

        subgraph Routers["Phase 4 routers"]
            TicketRouter["/api/v1/tickets"]
            CustomerRouter["/api/v1/customers"]
        end

        subgraph Services["Phase 4 services"]
            TicketService["TicketService"]
            CustomerService["CustomerService"]
            MemoryScrub["Memory redaction"]
        end

        subgraph Repositories["Repository layer"]
            TicketRepo["TicketRepository"]
            MessageRepo["TicketMessageRepository"]
            CustomerRepo["CustomerRepository"]
            WorkspaceRepo["WorkspaceRepository"]
            MemoryRepo["CustomerMemoryRepository"]
        end

        Session["Application async_sessionmaker"]
    end

    subgraph Data["Data and cache"]
        SQLite["SQLite local or test database"]
        Postgres["PostgreSQL / Supabase"]
        Redis["Real Redis or in-process FakeRedis"]
    end

    Client --> RequestId
    RequestId --> Audit
    Audit --> Rate
    Rate --> CORS
    CORS --> FastAPI
    FastAPI --> Security
    Security --> TicketRouter
    Security --> CustomerRouter

    TicketRouter --> TicketService
    CustomerRouter --> CustomerService
    CustomerService --> MemoryScrub

    TicketService --> TicketRepo
    TicketService --> MessageRepo
    TicketService --> CustomerRepo
    TicketService --> WorkspaceRepo
    CustomerService --> CustomerRepo
    CustomerService --> TicketRepo
    CustomerService --> MemoryRepo

    TicketRepo --> Session
    MessageRepo --> Session
    CustomerRepo --> Session
    WorkspaceRepo --> Session
    MemoryRepo --> Session

    Session --> SQLite
    Session -.->|"Configured hosted option"| Postgres
    Rate -.->|"Counter operations"| Redis

    TicketRouter -->|"HTTP JSON response"| CORS
    CustomerRouter -->|"HTTP JSON response"| CORS
```

## Database and session routing

FastAPI creates the database engine and session factory during its lifespan. A
ticket or customer route does not create a new engine for every request.

```mermaid
flowchart LR
    Lifespan["FastAPI lifespan startup"]
    Lifespan --> Settings["Read DATABASE_URL"]
    Settings --> Engine["create_database_engine"]
    Engine --> Factory["async_sessionmaker"]
    Factory --> AppState["app.state.session_factory"]
    AppState --> TicketRoute["Ticket route get_session dependency"]
    AppState --> CustomerRoute["Customer route get_session dependency"]
    TicketRoute --> TicketSession["AsyncSession"]
    CustomerRoute --> CustomerSession["AsyncSession"]
    TicketSession --> Database["SQLite or PostgreSQL"]
    CustomerSession --> Database
    Lifespan --> Shutdown["Dispose engine"]
```

The database URL determines the target:

- local demo and tests normally use SQLite;
- PostgreSQL and Supabase use an external database connection;
- no browser or frontend component receives the database credential.

The service-role credential belongs to the backend server process. It is not
placed in the Next.js browser bundle or in Pydantic response fields.

## Audit and error routing in Phase 4

Phase 4 makes the existing audit infrastructure more useful because there are
now real state-changing API operations. A `POST /api/v1/tickets` request passes
through the audit middleware as a non-GET method.

```mermaid
sequenceDiagram
    participant Caller
    participant RequestId
    participant Audit
    participant Rate
    participant Route as Ticket or Customer Route
    participant DB as Application Database

    Caller->>RequestId: HTTP request
    RequestId->>RequestId: validate or create request ID
    RequestId->>Audit: pass request with trace scope
    Audit->>Rate: count request
    alt Rate limit exceeded
        Rate-->>Caller: 429
    else Allowed
        Rate->>Route: dispatch
        Route-->>Audit: route status and response
    end
    Audit->>DB: insert audit record for non-GET
    DB-->>Audit: committed or audit failure
    Audit-->>RequestId: response
    RequestId-->>Caller: response plus X-Request-ID
```

Audit failures are not allowed to change the route's intended HTTP result. The
audit record is separate telemetry. This protects ticket and customer responses
from a telemetry-write failure.

## CORS and browser routing

There is no frontend application or reverse proxy in Phase 4. CORS is configured
inside the FastAPI process so a future browser frontend can call the API.

```mermaid
flowchart LR
    FutureBrowser["Future Next.js browser app"]
    FutureBrowser -->|"HTTPS in deployed environment"| Proxy["Future reverse proxy or edge routing"]
    Proxy -->|"REST /api/v1"| Cors["FastAPI CORS boundary"]
    Cors --> FastAPI["FastAPI routes"]
    FastAPI -->|"HTTP JSON"| Cors
    Cors -->|"CORS headers plus X-Request-ID"| Proxy
    Proxy --> FutureBrowser

    FutureBrowser -.->|"No direct database or Redis access"| Database["Database"]
    FutureBrowser -.->|"No service-role credential"| Database
```

The current CORS configuration allows configured origins, all methods and headers,
and exposes `X-Request-ID`. CORS is browser access control, not a network proxy
and not a replacement for JWT or role checks.

## Planned Docker component topology

The Docker topology is future work. It is not a description of the currently
running Phase 4 process. The project specification anticipates:

```mermaid
flowchart LR
    Browser["Support agent browser"]

    subgraph PlannedDocker["Planned Docker Compose network"]
        Frontend["Next.js frontend<br/>port 3000"]
        Backend["FastAPI backend<br/>port 8000"]
        Redis["Redis"]
        Qdrant["Qdrant"]
    end

    Browser -->|"HTTPS"| Frontend
    Frontend -->|"REST /api/v1"| Backend
    Backend -->|"TCP service address"| Redis
    Backend -->|"HTTP service address"| Qdrant
    Backend -->|"Database connection"| Database["SQLite volume or PostgreSQL"]
    Backend -.->|"Optional provider API"| LLM["LLM provider"]
```

In the target deployment:

- only the frontend and backend would publish browser-facing or routing ports;
- internal containers would communicate over a Docker network;
- Redis and Qdrant would use service names or DNS names;
- PostgreSQL could be containerized or externally managed;
- the frontend must not receive database or Redis credentials;
- a future reverse proxy or platform router would handle public TLS and route
  `/api/v1` to FastAPI.

These container connections are planned and should not be presented as completed
in Phase 4.

## Component reference

| Infrastructure responsibility | Implementation |
|---|---|
| FastAPI assembly and router mounting | [main.py](../../backend/app/main.py) |
| Database engine and session routing | [database.py](../../backend/app/core/database.py) |
| Ticket HTTP routes | [api/tickets.py](../../backend/app/api/tickets.py) |
| Customer HTTP routes | [api/customers.py](../../backend/app/api/customers.py) |
| Ticket coordination | [ticket_service.py](../../backend/app/services/ticket_service.py) |
| Customer coordination and memory redaction | [customer_service.py](../../backend/app/services/customer_service.py) |
| Ticket and message repositories | [tickets.py](../../backend/app/repositories/tickets.py) |
| Customer and memory repositories | [customers.py](../../backend/app/repositories/customers.py) |
| Request-ID wiring | [request_id.py](../../backend/app/middleware/request_id.py) |
| Audit routing | [audit.py](../../backend/app/middleware/audit.py) |
| Rate-limit routing | [rate_limit.py](../../backend/app/middleware/rate_limit.py) |
| Redis and FakeRedis selection | [redis.py](../../backend/app/core/redis.py) |
| API contract | [API_CONTRACT.md](../../docs/API_CONTRACT.md) |

## Validation and boundaries

Phase 4 component wiring is implemented and covered by focused API tests:

- ticket list, detail, creation, role, and validation routes;
- customer list, detail, history, role, and pagination routes;
- missing-ticket and missing-customer 404 behavior;
- customer/workspace mismatch rejection;
- memory-note redaction;
- middleware and JWT behavior inherited from earlier phases.

No Docker image, Compose network, frontend server, live PostgreSQL instance, or
live Redis service is implemented or required to run the Phase 4 focused tests.
