# Phase 3 — Project System Design Evolution

This document follows the identity and request-protection design from the
Phase 2 baseline through the four Phase 3 subtasks. Each subtask adds a focused
piece; the final design shows how those pieces wrap the application together.

## Phase 3 goal

Phase 1 established the runtime foundation, request tracking, and structured
logs. Phase 2 added persistent support data and demo records.

Phase 3 adds the control plane needed before protected support routes can be
built:

- authentication and signed JWTs;
- role-based authorization;
- demo login and the `/me` identity route;
- fixed-window request limiting;
- audit logging for state-changing HTTP requests;
- one consistent middleware order.

The subtask evolution is:

```mermaid
flowchart LR
    P31["P3-1: JWT and require_role"] --> P32["P3-2: Demo auth routes"]
    P31 --> P34["P3-4: Audit and middleware order"]
    P33["P3-3: Redis rate limit"] --> P34
    P32 --> P34
```

P3-1 and P3-3 start in parallel. P3-2 follows P3-1 because its demo tokens use
the JWT identity and role definitions. P3-4 is last because it owns the final
middleware arrangement.

## Starting design: a runnable API without route-level identity guards

At the beginning of Phase 3, CloudDesk already has a FastAPI application,
database models and repositories, health routes, request-ID middleware, and demo
startup data. Requests can reach the application, but protected operations do not
yet have a common JWT validation or role comparison.

This conceptual starting shape is based on the implemented Phase 1 and Phase 2
foundation; it is not a claim about a particular historical commit.

```mermaid
flowchart LR
    Caller["Browser or API caller"] --> App["FastAPI application"]
    App --> Health["Health routes"]
    App --> ExistingApi["Existing API routes"]
    ExistingApi --> Database["SQLite or PostgreSQL"]
    ExistingApi --> Response["HTTP response"]
    Response --> Caller
    RequestId["Request-ID middleware"] -.-> App
    Seed["Phase 2 demo profiles"] -.-> Database
```

The missing capabilities are an authenticated identity, a route permission check,
and shared protection against abusive traffic or missing audit trails.

## Evolution by subtask

### P3-1 — JWT and `require_role`

**Design change:** a request gains a verified identity and role, and future routes
can declare a minimum role.

The authentication code reads a bearer token, verifies its HS256 signature and
expiry, and requires `sub` and `exp` claims. It extracts a role from the token
and turns the claims into an `AuthenticatedUser` with an ID, email, and role.

Roles form a numeric hierarchy:

```mermaid
flowchart LR
    Viewer["Viewer = 1"] --> Agent["Agent = 2"]
    Agent --> Admin["Admin = 3"]
```

`require_role` is a FastAPI dependency factory. A route declares the minimum role
it needs, then the dependency compares the current user's rank with that minimum.
Missing or invalid authentication produces 401. A valid user without enough rank
produces 403.

```mermaid
sequenceDiagram
    participant Caller
    participant Route as Protected Route
    participant Security as JWT and Role Dependency
    participant DB as Profile Database

    Caller->>Route: Authorization: Bearer JWT
    Route->>Security: Run require_role(minimum_role)
    Security->>Security: Verify signature and exp claim
    Security->>Security: Read sub, email, and role
    Security->>Security: Compare role rank
    alt Authentication fails
        Security-->>Route: 401 Unauthorized
    else Role is too low
        Security-->>Route: 403 Forbidden
    else Role is sufficient
        Security-->>DB: Optionally load the profile
        DB-->>Route: Profile or identity available
        Route-->>Caller: Requested response
    end
```

**Result:** identity and authorization become reusable backend dependencies
rather than route-specific checks.

### P3-2 — Demo authentication routes and tokens

**Design change:** demo users can exchange a known fictional email for an
eight-hour signed access pass.

The demo authentication router is available only in demo mode. It looks up a
profile through `ProfileRepository`, rejects unknown users, and creates a JWT
with `sub`, `email`, `role`, `iat`, and `exp`.

The same JWT structure is used for the later protected-route checks. The `/me`
route validates the pass, loads the matching profile, and returns that profile
through a typed Pydantic response.

```mermaid
flowchart LR
    Caller["Demo support user"] --> DemoToken["POST /api/v1/auth/demo-token"]
    DemoToken --> Check{"Demo mode enabled?"}
    Check -->|"No"| Disabled["403 demo authentication disabled"]
    Check -->|"Yes"| ProfileRepo["ProfileRepository lookup"]
    ProfileRepo --> Profiles["Seeded profile records"]
    Profiles --> ProfileFound{"User exists?"}
    ProfileFound -->|"No"| Unknown["404 demo user not found"]
    ProfileFound -->|"Yes"| Claims["Build sub, email, role, iat, exp"]
    Claims --> Sign["Sign HS256 JWT for 8 hours"]
    Sign --> Caller

    Caller --> Me["GET /api/v1/auth/me"]
    Me --> Security["JWT validation and role extraction"]
    Security --> Profile["Load authenticated profile"]
    Profile --> Me
```

The demo role set is:

| Demo user | Role |
|---|---|
| `admin@clouddesk.demo` | admin |
| `sam.agent@clouddesk.demo` | agent |
| `vic.viewer@clouddesk.demo` | viewer |

**Result:** the application has a real local sign-in path for testing, while
demo authentication remains unavailable outside demo mode.

### P3-3 — Redis fixed-window rate limiting

**Design change:** the API gains a per-client traffic guard that counts requests
in fixed one-minute windows.

`FixedWindowRateLimiter` creates a counter key from the client IP and the current
window. It increments the Redis counter and sets an expiry on the first request
in that window. The middleware adds limit, remaining, reset, and retry headers to
responses.

Redis is shared by real deployments and fake Redis is used for local tests or
when no Redis URL is configured. If Redis operations fail, the limiter fails open
and permits the request instead of making a cache outage stop the application.

```mermaid
flowchart TB
    Request["Incoming HTTP request"] --> ClientKey["Identify client IP"]
    ClientKey --> Window["Calculate fixed one-minute window"]
    Window --> RedisKey["Rate-limit counter key"]
    RedisKey --> RedisChoice{"Redis configured?"}
    RedisChoice -->|"Yes"| Redis["Real Redis client"]
    RedisChoice -->|"No or fake mode"| Fake["Fake Redis client"]
    Redis --> Increment["INCR counter"]
    Fake --> Increment
    Increment --> First{"Counter is 1?"}
    First -->|"Yes"| Expiry["Set 60-second expiry"]
    First -->|"No"| Compare["Compare count with limit"]
    Expiry --> Compare
    Compare --> Allowed{"Count within limit?"}
    Allowed -->|"Yes"| Headers["Add rate-limit response headers"]
    Headers --> Application["Continue to application"]
    Allowed -->|"No"| Block["Return 429 and retry timing"]
    RedisFailure["Redis unavailable"] -.->|"Fail open"| Application
```

**Result:** an individual client's request volume is constrained, while normal
application behavior remains available if the cache is unreachable.

### P3-4 — Audit middleware and middleware order

**Design change:** shared middleware gains the same trace ID, security,
rate-limit, CORS, and audit behavior for every route.

The audit middleware excludes read-only `GET` requests and watches the status
returned by state-changing requests. It records:

- actor ID, when a valid bearer JWT can identify it;
- HTTP method;
- request path;
- response status;
- request trace ID;
- an optional data field, currently null.

Audit writes use the application database session factory. They are separate from
the route transaction and are not allowed to turn a telemetry failure into a
failed application request.

The final middleware wrapping order is:

```mermaid
flowchart TB
    Client["Browser or API caller"] --> RequestId["1. Request-ID middleware"]
    RequestId --> Audit["2. Audit middleware"]
    Audit --> Rate["3. Rate-limit middleware"]
    Rate --> CORS["4. CORS middleware"]
    CORS --> FastAPI["5. FastAPI routes"]
    FastAPI --> RouteAuth["JWT and require_role dependencies"]
    RouteAuth --> Protected["Protected route operation"]
    Protected --> Response["HTTP response"]
    Response --> CORS
    CORS --> Rate
    Rate --> Audit
    Audit --> RequestId
    RequestId --> CallerResponse["Response with trace and guard headers"]
    CallerResponse --> Client
```

This order means request-ID processing surrounds the later guards and application
routes, so even rate-limited or preflight responses receive a trace ID.

```mermaid
sequenceDiagram
    participant Caller
    participant RequestId as Request-ID
    participant Audit as Audit
    participant Limit as Rate Limit
    participant CORS
    participant Route as FastAPI Route

    Caller->>RequestId: HTTP request
    RequestId->>RequestId: Validate or create X-Request-ID
    RequestId->>Audit: Pass with request_id in scope
    Audit->>Limit: Watch state-changing response
    Limit->>Limit: Count client one-minute window
    alt Limit exceeded
        Limit-->>Audit: 429 response
    else Allowed
        Limit->>CORS: Apply browser rules
        CORS->>Route: Dispatch route
        Route-->>CORS: Route and security response
        CORS-->>Limit: Response
    end
    Limit-->>Audit: Final status
    Audit->>Audit: Record non-GET state-changing request
    Audit-->>RequestId: Response
    RequestId-->>Caller: Response plus X-Request-ID
```

**Result:** request context, traffic protection, browser policy, audit capture,
and route authorization are applied consistently rather than being implemented
again in every route.

## End-of-Phase 3 design

The complete Phase 3 design adds identity and common request guards around the
existing FastAPI and data services.

```mermaid
flowchart TB
    subgraph ClientBoundary["Outside the API"]
        Browser["Support UI or API client"]
    end

    subgraph HTTPBoundary["FastAPI middleware boundary"]
        RequestId["Request-ID middleware"]
        Audit["Audit middleware"]
        Rate["Fixed-window rate limit"]
        Cors["CORS middleware"]
    end

    subgraph Application["FastAPI application"]
        Health["Health routes"]
        AuthApi["/api/v1/auth/demo-token"]
        MeApi["/api/v1/auth/me"]
        FutureProtected["Future protected support routes"]
        Security["JWT validation and require_role"]
    end

    subgraph DataAndGuardServices["Shared services"]
        Profiles["Profile repository"]
        ProfileDb["SQLite or PostgreSQL profiles"]
        Redis["Redis or fake Redis counters"]
        AuditDb["audit_logs table"]
    end

    Browser --> RequestId
    RequestId --> Audit
    Audit --> Rate
    Rate --> Cors
    Cors --> Health
    Cors --> AuthApi
    Cors --> MeApi
    Cors --> FutureProtected

    AuthApi --> Profiles
    Profiles --> ProfileDb
    MeApi --> Security
    FutureProtected --> Security
    Security --> ProfileDb

    Rate --> Redis
    Audit --> AuditDb
    AuditDb -.->|"Actor and event history"| ProfileDb

    Health --> Cors
    AuthApi --> Cors
    MeApi --> Cors
    FutureProtected --> Cors
    Cors --> Rate
    Rate --> Audit
    Audit --> RequestId
    RequestId --> Browser
```

The request flow is now:

```mermaid
flowchart LR
    Request["Authenticated or anonymous request"] --> Trace["Attach or create X-Request-ID"]
    Trace --> AuditWatch["Watch if state-changing"]
    AuditWatch --> Limit["Count in fixed one-minute window"]
    Limit -->|Allowed| CORS["Apply browser-origin rules"]
    Limit -->|Exceeded| RateError["Return 429"]
    CORS --> Route["Dispatch to FastAPI route"]
    Route --> Auth{"Protected route?"}
    Auth -->|No| Response["Return route response"]
    Auth -->|Yes| JWT["Verify bearer JWT"]
    JWT -->|Invalid| Error401["Return 401"]
    JWT -->|Valid| Role["Compare viewer / agent / admin rank"]
    Role -->|Insufficient| Error403["Return 403"]
    Role -->|Allowed| Response
    Response --> AuditSave["Save state-changing audit row"]
    RateError --> AuditSave
    Error401 --> AuditSave
    Error403 --> AuditSave
    AuditSave --> TraceResponse["Return X-Request-ID with response"]
```

## Component responsibilities and boundaries

| Component | Responsibility | Does not do |
|---|---|---|
| `Role` enum | Defines `viewer`, `agent`, and `admin` | Does not decide route permissions |
| `decode_jwt` | Verifies JWT signature, expiry, subject, and claims | Does not create users or ticket actions |
| `get_current_user` | Turns bearer credentials into `AuthenticatedUser` | Does not grant a role above the token |
| `require_role` | Compares the user's rank with a route minimum | Does not hide business policy in the UI |
| Demo auth routes | Issue local demo tokens and return `/me` | Do not register real users or external identity providers |
| `FixedWindowRateLimiter` | Counts clients in fixed windows | Does not classify or block individual API paths |
| Redis factory | Chooses real or fake Redis | Does not store application records |
| `AuditMiddleware` | Records state-changing HTTP attempts and status | Does not define refund or ticket business rules |
| `RequestIdMiddleware` | Creates or validates trace IDs | Does not replace application or workflow IDs |
| `create_app` | Wraps CORS and middleware around FastAPI | Does not implement support routes or workflows |

## Design properties

The Phase 3 design improves several system qualities:

- **Identity:** a signed token carries the identity and role of the caller.
- **Authorization:** route dependencies enforce a role hierarchy server-side.
- **Availability:** Redis failure is isolated from normal application execution.
- **Traffic protection:** excessive clients receive a 429 with retry information.
- **Traceability:** every HTTP response has a request ID and state changes can
  contain that ID in audit records.
- **Auditability:** actor, method, path, status, and request ID are retained.
- **Offline operation:** fake Redis and demo profiles allow local testing without
  a real Redis account or paid external service.
- **Separation of concerns:** middleware handles shared HTTP concerns, while
  protected routes and future services keep their own business rules.

## What Phase 3 does not yet include

This phase secures access but is not the complete support-product workflow.

It does not yet:

- create or update tickets;
- list customers;
- run AI investigation or knowledge retrieval;
- make a refund or account-change approval;
- send customer replies;
- escalate tickets;
- build the support console;
- execute LangGraph workflows.

The phase supplies the request identity, role checks, rate guard, trace context,
and audit trail that those later components will use.

## Honest validation status

The current implementation was validated with 19 focused offline tests covering
the auth, rate-limit, request-ID, health, and audit components. It uses:

- in-memory SQLite for middleware tests;
- fake Redis for repeatable rate-limit tests;
- signed demo JWTs;
- no live Redis account;
- no live PostgreSQL account;
- no real customer or external identity provider.

The JWT and role code is implemented, demo login is implemented, rate limiting is
implemented, and the final request-ID, audit, rate-limit, CORS, and route wrapping
is present. Live infrastructure deployment is not claimed.
