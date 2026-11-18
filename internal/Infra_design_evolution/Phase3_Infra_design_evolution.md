# Phase 3 — Infrastructure and Component-Wiring Evolution

This document explains how the Phase 3 authentication, role, rate-limit, request
tracking, and audit components are wired into the running application. It
documents only what is implemented in the repository and clearly separates that
from future Docker and production networking.

## Status at the end of Phase 3

Phase 3 does not add Docker containers or a Compose network. The application is
still a local FastAPI process. It does add runtime HTTP wrapping, in-process
authentication dependencies, and connections to Redis or fake Redis and the
application database.

| Component | Current location | Current infrastructure |
|---|---|---|
| FastAPI process | Local Uvicorn process | `127.0.0.1:8000` in development |
| Database | SQLite or prepared PostgreSQL | SQLite file or in-memory test database |
| Redis | Real Redis or fake Redis | In-process fake Redis in demo/test mode |
| Browser routing | CORS rules | No frontend container or reverse proxy yet |
| Audit storage | `audit_logs` table | Same database session factory as the application |
| Containers | Not implemented | Docker networking remains a later delivery phase |

The subtask wiring sequence is:

```mermaid
flowchart LR
    P31["P3-1: JWT and role dependencies"] --> P32["P3-2: Demo auth routes"]
    P31 --> P34["P3-4: Audit and middleware assembly"]
    P33["P3-3: Redis rate limiter"] --> P34
    P32 --> P34
```

P3-1 and P3-3 can be built independently. P3-2 depends on P3-1 for its JWT
format and role values. P3-4 is last because it connects the complete HTTP
middleware chain.

## Starting point — local HTTP process before request guards

At the start of Phase 3, the application has the data foundation and request-ID
boundary from earlier phases. An incoming HTTP request reaches FastAPI, CORS, and
the route. The route does not have a shared JWT verifier or role dependency.

```mermaid
flowchart LR
    Caller["Browser or API caller"] -->|"HTTP TCP request"| Uvicorn["Local Uvicorn process"]
    Uvicorn --> RequestId["Request-ID middleware"]
    RequestId --> CORS["CORS middleware"]
    CORS --> FastAPI["FastAPI application"]
    FastAPI --> Existing["Health and demo auth routes"]
    Existing --> Data["SQLite or PostgreSQL"]
    Data --> Existing
    Existing --> FastAPI
    FastAPI --> CORS
    CORS --> RequestId
    RequestId --> Caller
```

The diagram represents local process wiring, not Docker network routing. The
database has one application connection, but an authenticated request has not yet
passed through a common role decision.

## P3-1 — Wire JWT verification and route authorization

P3-1 adds two in-process security components:

1. `get_current_user` extracts the bearer token and verifies its JWT claims.
2. `require_role` turns a minimum role into a FastAPI dependency.

These components do not open a separate network service. They run inside the
FastAPI worker process. The effective JWT secret comes from cached application
settings:

```mermaid
flowchart LR
    Environment[".env or process environment"] --> Settings["get_settings"]
    Settings --> Secret["Effective JWT secret"]
    Secret --> Decoder["JWT decoder in security.py"]
    Caller["API caller"] -->|"Authorization: Bearer token"| Route["Protected FastAPI route"]
    Route --> Dependency["require_role dependency"]
    Dependency --> CurrentUser["get_current_user"]
    CurrentUser --> Decoder
    Decoder --> Claims["sub, email, role, exp"]
    Claims --> Rank["Viewer 1, agent 2, admin 3"]
    Rank --> Decision{"Rank sufficient?"}
    Decision -->|"Yes"| Operation["Route operation"]
    Decision -->|"401"| AuthError["Missing or invalid identity"]
    Decision -->|"403"| RoleError["Valid identity, insufficient role"]
```

The secret is selected by the application settings. Supabase JWT secret takes
priority over the local JWT secret. In demo mode, when neither is configured,
the application supplies the demo-only local secret. A production process should
not rely on that fallback.

The actual network flow has no extra authentication server. FastAPI receives the
token and verifies it locally:

```mermaid
sequenceDiagram
    participant Caller
    participant Uvicorn
    participant Route as FastAPI protected route
    participant Security as JWT security module

    Caller->>Uvicorn: HTTP request with bearer token
    Uvicorn->>Route: Dispatch to route
    Route->>Security: Require minimum role
    Security->>Security: Verify signature and required claims
    alt Missing or invalid token
        Security-->>Caller: 401
    else Valid token but low role
        Security-->>Caller: 403
    else Valid token and sufficient role
        Security-->>Route: AuthenticatedUser
        Route-->>Caller: Route response
    end
```

**Infrastructure effect:** authentication is a CPU and configuration operation
inside the FastAPI process. It does not require a network call to an identity
service.

## P3-2 — Wire demo token issuance and `/me`

P3-2 exposes the demo authentication routes under `/api/v1/auth`. The API route
uses the same database session factory that application startup creates for
SQLite or PostgreSQL.

```mermaid
flowchart LR
    Caller["Demo support user"] -->|"POST /api/v1/auth/demo-token"| Router["Auth FastAPI router"]
    Router --> Check{"DEMO_MODE?"}
    Check -->|"No"| Disabled["403 demo auth disabled"]
    Check -->|"Yes"| Session["Async database session"]
    Session --> Repo["ProfileRepository"]
    Repo --> Database["profiles table"]
    Database --> Profile{"Profile found?"}
    Profile -->|"No"| Missing["404 user not found"]
    Profile -->|"Yes"| Signer["JWT encoder"]
    Signer --> Secret["Effective JWT secret"]
    Secret --> Signer
    Signer -->|"8-hour signed pass"| Caller

    Caller -->|"GET /api/v1/auth/me"| Me["Me route"]
    Me --> Verifier["JWT and role dependency"]
    Verifier --> Session
    Session --> Repo
    Repo --> Database
    Database --> Me
    Me --> Caller
```

The route does not call a separate identity provider. The network components are:

- HTTP: the browser or client to Uvicorn/FastAPI;
- database: FastAPI to SQLite or the configured hosted PostgreSQL service;
- JWT: local signing and verification inside FastAPI;
- browser storage: the caller retains the pass and sends it as a bearer header.

```mermaid
sequenceDiagram
    participant Caller
    participant Auth as Auth router
    participant Session as Async database session
    participant Profiles as ProfileRepository
    participant JWT as JWT module

    Caller->>Auth: POST email
    Auth->>Session: Open session
    Session->>Profiles: Find profile by email
    Profiles->>Session: Profile or none
    alt Unknown profile
        Auth-->>Caller: 404
    else Known profile
        Auth->>JWT: Sign sub, email, role, iat, exp
        JWT-->>Caller: Token plus profile details
    end
```

**Infrastructure effect:** demo login depends on the application database and
process settings. It does not create an additional container or network service.

## P3-3 — Wire Redis and fake Redis rate limiting

P3-3 adds a middleware component that counts one-minute request windows. The
component chooses one of two cache clients from the Redis factory.

```mermaid
flowchart TB
    Request["Incoming HTTP request"] --> Middleware["RateLimitMiddleware"]
    Middleware --> ClientIP["Read client IP"]
    ClientIP --> Key["Build rl:client:window key"]
    Key --> Factory["create_redis_client"]
    Factory --> Choice{"REDIS_URL and fake mode"}
    Choice -->|"No URL or USE_FAKE_REDIS"| Fake["In-process FakeRedis"]
    Choice -->|"Valid REDIS_URL"| Real["redis.asyncio client"]
    Fake --> INCR["INCR counter"]
    Real --> INCR
    INCR --> Expire["Set expiry after first count"]
    Expire --> Decide{"Allowed?"}
    Decide -->|"Yes"| Continue["Continue to CORS and route"]
    Decide -->|"No"| Response429["Return 429 response"]
    Continue --> Headers["Add limit/remaining/reset headers"]
    Response429 --> Headers429["Add retry-after and limit headers"]
```

In the current local setup, `USE_FAKE_REDIS=true` and `REDIS_URL` is empty, so
FakeRedis runs as an in-memory Python object inside the FastAPI process. It does
not create a Redis container or a network socket.

In the future Docker or cloud setup, the backend can receive a Redis URL and
connect to a managed or container Redis service:

```mermaid
flowchart LR
    subgraph LocalOrTest["Current local/test topology"]
        BackendLocal["FastAPI process"] --> Fake["FakeRedis object in memory"]
    end

    subgraph PreparedDeployment["Prepared external Redis topology"]
        BackendRemote["FastAPI container or cloud process"]
        BackendRemote -->|"REDIS_URL redis://redis:6379/0"| Redis["Redis service"]
        Redis -->|"Counter and expiry"| BackendRemote
    end
```

The limiter also isolates cache failures. If `INCR`, `EXPIRE`, or connection
operations raise a Redis or network error, the middleware fails open and permits
the request. It does not route traffic to the database for the rate-limit
decision.

**Infrastructure effect:** the Redis client is an optional external dependency,
while fake Redis keeps the demo and offline test stack local.

## P3-4 — Wire audit, tracing, and middleware order

P3-4 is the shared HTTP assembly point. The application is wrapped in:

```text
RequestIdMiddleware
  -> AuditMiddleware
     -> RateLimitMiddleware
        -> CORSMiddleware
           -> FastAPI
```

This order is implemented in `create_app()`:

```mermaid
flowchart TB
    Browser["Browser or API caller"]
    Browser --> RequestId["1. RequestIdMiddleware"]
    RequestId --> Audit["2. AuditMiddleware"]
    Audit --> Limit["3. RateLimitMiddleware"]
    Limit --> CORS["4. CORSMiddleware"]
    CORS --> FastAPI["5. FastAPI application"]
    FastAPI --> Auth["JWT and require_role route dependencies"]
    FastAPI --> Health["Health routes"]
    FastAPI --> DemoAuth["Demo authentication routes"]
    FastAPI --> FutureRoutes["Future support routes"]

    Auth --> Response["Route response"]
    Health --> Response
    DemoAuth --> Response
    FutureRoutes --> Response
    Response --> CORS
    CORS --> Limit
    Limit --> Audit
    Audit --> RequestId
    RequestId --> Browser
```

On the way in, request ID processing surrounds every later result. This means a
request rejected by rate limiting or CORS can still receive the trace header.
On state-changing requests, audit middleware records the actor and response:

```mermaid
sequenceDiagram
    participant Caller
    participant RequestId
    participant Audit
    participant Limit
    participant CORS
    participant FastAPI
    participant Database

    Caller->>RequestId: HTTP request
    RequestId->>RequestId: Validate or create request ID
    RequestId->>Audit: Pass scope with state.request_id
    Audit->>Limit: Observe status and state changes
    Limit->>Limit: Count client in Redis or fake Redis
    alt 429
        Limit-->>Audit: Final 429 status
    else Allowed
        Limit->>CORS: Apply browser-origin policy
        CORS->>FastAPI: Dispatch route
        FastAPI-->>CORS: 401, 403, 200, or error
        CORS-->>Audit: Final response status
    end
    Audit->>Database: Insert audit_log actor, method, path, status, request_id
    Database-->>Audit: Commit or database error
    Audit-->>RequestId: Response
    RequestId-->>Caller: Response plus X-Request-ID
```

Audit middleware uses the application session factory. It is not a separate
microservice or container. It opens an asynchronous SQLAlchemy session to the
configured SQLite or PostgreSQL database, adds an `AuditLog`, and commits.

Read-only `GET` requests are bypassed. State-changing methods are watched,
including requests that can end in 401, 403, 429, or 500. `HEAD` and `OPTIONS`
are also excluded from the audit row.

**Infrastructure effect:** the audit database path is coupled to the application
database availability. Audit failures are isolated so the HTTP response can
continue.

## End-of-Phase 3 component wiring

The complete local component map is:

```mermaid
flowchart TB
    subgraph LocalClient["Local caller"]
        Browser["Browser or HTTP client"]
    end

    subgraph FastAPIProcess["One local Python/FastAPI process"]
        RequestId["Request-ID middleware"]
        Audit["Audit middleware"]
        Limit["Rate-limit middleware"]
        CORS["CORS middleware"]
        Router["FastAPI routers"]
        Security["JWT and role dependencies"]
        Repo["ProfileRepository"]
        Session["Async SQLAlchemy session factory"]
    end

    subgraph ProcessOrLocalStorage["Process-local or configured storage"]
        SQLite["SQLite file or in-memory SQLite"]
        FakeRedis["FakeRedis object"]
    end

    subgraph PreparedExternal["Prepared external services"]
        PostgreSQL["PostgreSQL or Supabase"]
        Redis["Redis service"]
    end

    Browser -->|"HTTP; Authorization; X-Request-ID"| RequestId
    RequestId --> Audit
    Audit --> Limit
    Limit --> CORS
    CORS --> Router
    Router --> Security
    Router --> Repo
    Repo --> Session
    Session --> SQLite
    Session -.->|"When configured"| PostgreSQL
    Limit --> FakeRedis
    Limit -.->|"When REDIS_URL is configured"| Redis
    Audit --> Session

    Router --> CORS
    CORS --> Limit
    Limit --> Audit
    Audit --> RequestId
    RequestId -->|"HTTP response and trace headers"| Browser
```

The route can follow one of these current infrastructure paths:

```mermaid
flowchart LR
    Request["HTTP request"] --> Trace["Request-ID wrapper"]
    Trace --> AuditWrap["Audit wrapper"]
    AuditWrap --> Guard["Rate-limit wrapper"]
    Guard --> BrowserPolicy["CORS wrapper"]
    BrowserPolicy --> RouteType{"Route type"}
    RouteType -->|Health| Health["No auth/database route"]
    RouteType -->|Demo auth| Auth["Profile database plus JWT"]
    RouteType -->|Protected| Protected["JWT verification plus role check"]
    Auth --> ProfileDB["SQLite or PostgreSQL"]
    Protected --> ProfileDB
    Guard --> Counter["FakeRedis or Redis"]
    AuditWrap --> AuditDB["audit_logs in application database"]
    Health --> Response["Response"]
    Auth --> Response
    Protected --> Response
    Response --> Trace
```

## Prepared Docker network: not implemented in Phase 3

The target Phase 14 architecture may place the frontend, backend, Redis, and
vector store in containers. Phase 3 does not yet create that network.

```mermaid
flowchart LR
    Browser["Support agent browser"]
    Browser -->|"HTTPS; frontend port"| Frontend["Next.js container :3000"]

    subgraph FutureDockerNetwork["Future Docker Compose network"]
        Frontend -->|"REST /api/v1; bearer JWT"| Backend["FastAPI container :8000"]
        Backend -->|"Rate counter"| Redis["Redis container"]
        Backend -->|"Future knowledge calls"| Qdrant["Qdrant container"]
    end

    Backend -->|"SQLite volume or external PostgreSQL"| DB["Database"]
    Backend -.->|"Optional future external provider"| LLM["LLM provider"]
```

This is a target design. The repository currently has no Dockerfile or Compose
file for Phase 3, and no live Redis or PostgreSQL container is started by the
current application.

## Component-to-infrastructure reference

| Component | Infrastructure responsibility |
|---|---|
| Uvicorn and FastAPI | Host HTTP routes and middleware in one process |
| `create_app()` | Assemble middleware wrappers and CORS policy |
| `RequestIdMiddleware` | Attach a trace ID to the HTTP scope and response |
| `AuditMiddleware` | Open an application database session and write audit records |
| `FixedWindowRateLimiter` | Count requests through Redis or fake Redis |
| `create_redis_client()` | Select process-local or external cache infrastructure |
| JWT settings and security module | Supply and verify local signing configuration |
| Demo auth router | Query the application database and sign a local pass |
| `get_session()` | Supply route-scoped database sessions |
| SQLite demo database | Store profiles and audit rows in the local process setup |
| PostgreSQL/Supabase | Prepared database infrastructure, not live in Phase 3 |

## Routing and network boundaries

1. The caller reaches FastAPI through a local host port or future load balancer.
2. Request-ID middleware validates or creates the HTTP trace ID.
3. Audit middleware watches state-changing HTTP requests.
4. Rate-limit middleware uses the client IP and cache counter.
5. CORS middleware applies browser-origin policy.
6. FastAPI routes dispatch into auth or future business dependencies.
7. Demo auth and audit operations use the database session factory.
8. Redis operations use fake Redis locally or Redis externally when configured.
9. The response returns through CORS, limit, audit, and request-ID wrappers.
10. The caller receives the HTTP status, JSON body, and trace/rate-limit headers.

## Honest validation status

Phase 3 infrastructure is implemented and validated locally with:

- in-process ASGI HTTP tests;
- in-memory SQLite sessions;
- fake Redis counters;
- no Docker containers;
- no live Redis service;
- no live PostgreSQL or Supabase account;
- no reverse proxy or frontend network;
- no published cloud endpoint.

The middleware order and request routing are implemented. Docker networking,
container health checks, service discovery, TLS termination, load balancing,
and hosted database deployment are future delivery work.
