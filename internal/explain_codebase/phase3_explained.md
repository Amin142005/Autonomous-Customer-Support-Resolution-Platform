# Phase 3 — Identity and Request Guards

## A plain-language presentation

> **Use this as a speaking script.** The goal is to explain the system design in
> simple words, even to people who are not software specialists.

Phase 1 gave CloudDesk a reliable foundation. Phase 2 gave it organized data and
example records. Phase 3 introduces the rules for knowing who is making a request
and for protecting the system when many requests arrive.

The best everyday comparison is a secure office building. A visitor must show an
entry pass, the pass must give the right level of access, the building must limit
how many requests can come through at once, and important actions must be recorded
afterwards. Phase 3 puts those protections in front of the application.

This phase does not build the complete support workflow. It makes sure that future
ticket, customer, approval, and AI actions can be connected to an authenticated
person and protected by consistent rules.

## The main idea

Every request should be able to answer four questions:

1. Is this person authenticated?
2. Does this person have enough permission?
3. Is the request arriving too quickly?
4. If the request changes something, should it be recorded?

The components in Phase 3 answer those questions automatically.

```text
Browser or support application
  └─ Sends a request
       └─ Request receives a tracking ID
            └─ Request is checked and audited
                 └─ Request-rate limit is checked
                      └─ CORS rules are applied
                           └─ Authentication and role rules run
                                └─ The requested service responds
```

## The Phase 3 pieces, in everyday language

### 1. Identity: proving who the user is

CloudDesk uses a signed digital pass called a JWT, or JSON Web Token. After a
support user signs in through the demo authentication route, the system creates
a pass containing useful, limited facts:

- the user's identification number;
- the user's email address;
- the user's role;
- the pass issue time;
- the pass expiry time.

The demo pass lasts for eight hours. It is protected with HS256 signing, so the
application can recognize whether the pass was created by CloudDesk and whether it
has been changed.

The JWT does not replace the database. The system uses the pass to identify the
person and then can use that identity to read the corresponding profile.

**Why it matters:** the application can identify a caller consistently without
asking the caller to send a password with every request.

### 2. Demo authentication: a safe way to obtain a pass locally

The demo authentication route accepts a demonstration support user's email address
and looks for that user in the sample profile records. It does not create a public
registration process and it is disabled when demo mode is off.

The existing demo users are:

- `admin@clouddesk.demo` — the strongest role;
- `sam.agent@clouddesk.demo` — the normal support-agent role;
- `vic.viewer@clouddesk.demo` — the read-only role.

After a successful demo login, the route returns the signed pass and a small copy
of the user's profile.

**Why it matters:** the team can demonstrate login and permission behavior locally
using fictional accounts instead of real customer identities.

### 3. Roles: not every user should have every permission

CloudDesk has three roles, arranged in a clear order:

1. **Viewer** — can read information.
2. **Agent** — can also perform support actions.
3. **Admin** — can perform all agent actions and administration.

The role is deliberately defined in both a common role list and a permission
ranking:

```text
Viewer = 1
Agent = 2
Admin = 3
```

When a future route requires an agent or an admin, the application compares the
signed-in user's rank with the minimum rank required by that route.

For example, a viewer is allowed to read a ticket but should not be allowed to
approve an approval request or run a workflow. An agent can perform normal support
actions, while an admin can perform administrative actions.

**Why it matters:** role rules are enforced by the backend, not only by hiding
buttons in a future screen.

### 4. Token validation: rejecting a bad or expired pass

Before a protected route runs, the application checks the signed pass.

A missing pass is reported as an authentication problem. An expired pass is
reported separately. A pass with an invalid signature or missing required identity
information is rejected.

The application also verifies that the role contained in the pass is one of the
three supported roles. A person or service cannot invent a role string and pass
the check accidentally.

**Why it matters:** every protected operation starts with one consistent identity
and permission check.

### 5. Request tracking: a trace number for every request

The request-ID middleware gives every HTTP request a trace number. If the browser
or another service supplies a valid `X-Request-ID`, the system uses it. If the
value is missing or invalid, the system creates a new unique ID.

The same ID is:

- returned in the `X-Request-ID` response header;
- available to logs created while handling the request;
- saved with state-changing audit records.

**Why it matters:** support staff and operators can correlate a response, a set
of logs, and an audit entry with the same request.

### 6. Rate limiting: preventing excessive request volume

The rate limiter acts like a reception desk that only accepts a limited number of
requests from the same visitor during a fixed period.

CloudDesk counts requests in one-minute windows. The demo limit is 120 requests per
minute per client. When the limit is exceeded, the service returns HTTP 429,
“Rate limit exceeded.”

The response includes useful information:

- the configured limit;
- the number of requests remaining;
- the time when the window resets;
- how long to wait before trying again.

In production, a Redis service can store and share the request counts. In local
development or tests, the system can use an in-memory fake Redis instead. If Redis
is temporarily unavailable, the limiter allows the request through rather than
breaking the application.

**Why it matters:** the API remains protected from accidental loops and unusually
heavy traffic, while a cache outage does not automatically stop every request.

### 7. Audit logging: remembering important changes

The audit middleware records requests that may change state. It does not normally
record read-only `GET` requests.

For a state-changing request, such as `POST`, `PUT`, `PATCH`, or `DELETE`, it
attempts to save:

- the user identified by a valid bearer pass, if available;
- the HTTP method;
- the requested path;
- the response status;
- the request trace ID;
- the time of the action.

The record is stored in the `audit_logs` table. The current implementation treats
audit storage as telemetry: if the audit database operation fails, it does not
crash the application's response. Database and network failures are not allowed to
silently become the only copy of the event, so the team can review and improve
operational behavior as audit coverage expands.

**Why it matters:** an administrator has a trail showing which state-changing
actions were attempted and whether they succeeded.

### 8. Middleware order: applying the guards in the right sequence

Middleware is a shared security and operations layer that wraps the application.
The order in CloudDesk is:

```text
Outer layer
  1. Request-ID middleware
     2. Audit middleware
        3. Rate-limit middleware
           4. CORS middleware
              5. CloudDesk routes
Inner application
```

The order means that every request receives a request ID first, even if a later
layer rejects it. Audit middleware can connect to that request ID. The rate
limiter can then reject excessive traffic before the route runs. CORS rules
determine which browser origins may call the API. Authentication and role checks
are performed at the individual route level.

For browser requests, CORS is also told to expose `X-Request-ID` so the frontend
can read that tracking header.

**Why it matters:** protections still work consistently for successful responses,
authorization failures, missing routes, CORS preflight requests, and server errors.

## How a protected request works

Imagine an agent tries to perform a support action:

```text
1. The browser sends a signed pass in the Authorization header.
2. Request-ID middleware creates or validates a trace ID.
3. Audit middleware watches for a state-changing request.
4. The rate limiter counts the request in the client's one-minute window.
5. CORS checks whether the browser is permitted to make this call.
6. The route verifies the pass signature and expiry.
7. The route extracts the user's identity and role.
8. The role is compared with the route's minimum requirement.
9. The action is allowed or rejected.
10. The audit middleware stores the action details and result.
11. The response includes the request trace ID.
```

The possible outcomes are:

- **401 Unauthorized** — no valid pass or missing authentication;
- **403 Forbidden** — the pass is valid, but the role is too low;
- **429 Too Many Requests** — the client exceeded the rate limit;
- **Success status** — authentication, role, and limits all passed.

## How the components fit together

```text
Demo profile in SQLite or PostgreSQL
  └─ Identified by email
       └─ Signed JWT contains user ID and role
            └─ Route validates the JWT
                 └─ Role rule decides if access is allowed

Incoming HTTP request
  └─ Request ID added
       └─ Request counted in Redis or fake Redis
            └─ State-changing request recorded in audit_logs
                 └─ Response returned with trace and rate-limit headers
```

Phase 3 connects three concerns that should not be mixed:

- authentication proves who the caller is;
- authorization decides what the caller may do;
- request guards provide tracking, traffic protection, and an audit trail.

## What Phase 3 does not do

Phase 3 establishes identity and shared protection, but it does not yet build the
support ticket routes or the AI workflow.

It also does not yet:

- approve or reject a refund;
- create or resolve support tickets;
- perform account changes;
- run the LangGraph investigation;
- send replies to customers;
- provide a support console in the browser.

Those capabilities will use the identity and role checks introduced in this phase.
Consequential actions will receive separate approval gates in later phases.

## Short answers for likely questions

**What is the difference between 401 and 403?**  
401 means the system does not recognize or accept the user's authentication. 403
means the system recognizes the user, but the user's role is not enough for that
operation.

**Is a JWT stored on the server?**  
The application signs and validates the pass, but the pass itself is returned to
the demo client for use in the `Authorization` header. The user's profile remains
in the database.

**Can a viewer manually call an agent-only route?**  
No. Even if the route is called directly, the backend role comparison should reject
the viewer.

**Why use fake Redis for local tests?**  
It makes rate-limit tests repeatable and offline. A real Redis service can be used
with a Redis connection setting when the application is deployed.

**Does every request create an audit record?**  
No. Read-only `GET` requests are not recorded by the current audit rule. State
changing requests are recorded, including requests that fail or return an error
when middleware can observe the response.

**Can a rate-limit failure bypass request tracking or auditing?**  
No. Request-ID middleware runs outside the audit and rate-limit layers, so the
client should still receive a request trace even when another layer rejects the
request.

## Current validation note

The Phase 3 implementation and focused offline tests passed 19 checks covering
request identity, demo authentication, role-based JWT behavior, fixed-window rate
limiting, request IDs, health responses, and audit middleware.

The audit test suite verifies that reads are not recorded, state-changing requests
are recorded with method, path, status, and request ID, and a valid bearer pass
identifies the actor. No live Redis or cloud database was used in local validation.
