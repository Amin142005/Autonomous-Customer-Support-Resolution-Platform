# Phase 3 — Interview Questions and Answers

This question bank covers **Phase 3: Identity and Request Guards** only. The
answers are written for direct speaking. Use the technical follow-ups when an
interviewer asks how a component works internally.

Related reading:

- [Phase 3 plain-language explanation](../explain_codebase/phase3_explained.md)
- [Phase 3 system-design evolution](../design_evolution/Phase3_Project_System_Design_Evolution.md)
- [Phase 3 infrastructure evolution](../Infra_design_evolution/Phase3_Infra_design_evolution.md)
- [Phase 3 task status](../../TASK.md)

## 30-second overview

**Q: Can you summarize Phase 3?**  
**A:** “Phase 3 adds identity and request protection to CloudDesk. It issues
eight-hour demo JWTs, verifies bearer tokens, enforces viewer, agent, and admin
roles on the backend, applies a fixed-window rate limit with Redis or fake Redis,
adds X-Request-ID tracing, and audits state-changing requests. The support-ticket
API and AI workflow are not implemented yet.”

## Product scope and architecture

### 1. What problem does Phase 3 solve?

**A:** “It solves who is calling the system and whether the caller has permission.
It also gives the system a shared way to limit traffic, trace requests, and record
important changes before later support features are added.”

### 2. What are the Phase 3 subtasks?

**A:** “P3-1 adds JWT verification and role dependencies. P3-2 adds demo login and
the `/me` route. P3-3 adds fixed-window Redis rate limiting. P3-4 adds audit
middleware and combines all middleware in the correct order.”

### 3. Why is P3-4 last?

**A:** “P3-4 owns middleware order and must wrap the components created earlier.
It needs the request-ID behavior, rate limiter, and audit data model to be
available so the complete HTTP boundary can be assembled and tested.”

### 4. Is this phase the complete support platform?

**A:** “No. It protects the application, but it does not create tickets, search
knowledge, run agents, approve refunds, send replies, or build the agent console.
Those features will use the identity and guardrails introduced here.”

### 5. What is the current application shape?

**A:** “It is still one local FastAPI process using SQLite or a configured
database, with fake Redis available for demo and testing. There are no Docker
containers or live cloud infrastructure required by this phase.”

### 6. What are authentication and authorization?

**A:** “Authentication verifies who the caller is. Authorization decides what that
verified caller is allowed to do. A 401 usually indicates authentication failure,
while a 403 usually indicates valid authentication with insufficient permission.”

### 7. Which roles exist?

**A:** “Viewer, agent, and admin. Viewer can read, agent can perform support
actions, and admin can perform administrative actions in addition to agent
actions.”

### 8. How is role rank enforced?

**A:** “The application assigns viewer rank 1, agent rank 2, and admin rank 3.
`require_role` compares the authenticated user's rank with the minimum rank required
by a route.”

### 9. Why enforce authorization in the backend?

**A:** “Frontend controls are not a security boundary. A caller could call an API
directly. The backend must verify identity and rank for every protected operation.”

### 10. Why use a numeric hierarchy for roles?

**A:** “It makes minimum-permission checks simple and consistent. The role names
come from a shared enum, while the rank map converts them to an ordering.”

## JWT authentication

### 11. What is a JWT?

**A:** “A JWT is a signed data pass. It contains claims about the user and can be
verified using a secret or key. CloudDesk uses HS256 tokens to carry a subject,
email, role, issue time, and expiry time.”

### 12. Which JWT claims does CloudDesk require?

**A:** “The security decoder requires `sub` and `exp`. It reads `email` and `role`
claims when building the authenticated user. A missing subject or role is rejected
by the appropriate route-level validation.”

### 13. What does `sub` represent?

**A:** “The `sub` claim identifies the user. It is stored as the profile ID and
becomes the basis for actor and profile lookup.”

### 14. How does the decoder validate a token?

**A:** “It verifies the HS256 signature, checks expiry, and requires the subject
and expiry claims. PyJWT errors and expired signatures are translated into HTTP
401 responses.”

### 15. Why use a bearer token header?

**A:** “The bearer scheme gives HTTP routes a standard place to receive the access
pass. A route extracts the credentials and does not need the caller to send a
password on every request.”

### 16. What happens if no bearer token is sent?

**A:** “`get_current_user` rejects the request with 401 and an authentication
detail. The browser receives a bearer challenge header.”

### 17. What happens when a token is expired?

**A:** “The JWT decoder raises an expired-signature result and the request receives
401 with a token-expired detail.”

### 18. What happens when a token has the wrong secret or invalid signature?

**A:** “It is rejected as an invalid authentication token with 401.”

### 19. Can a caller invent an admin role in a JWT?

**A:** “No, if they do not know the signing secret. They could encode a claim, but
it would fail signature verification. The role is also checked against the allowed
enum values.”

### 20. Does the system authorize based on the JWT alone?

**A:** “It authorizes using the role claim after verifying the token. `/me` and
some routes also load or verify the corresponding profile from the database.”

### 21. What is the effective JWT secret?

**A:** “It is the signing value selected by settings: Supabase JWT secret if
configured, otherwise the local JWT secret. Demo mode may use the documented
demo-only fallback secret.”

### 22. Why should production set a real JWT secret?

**A:** “The demo fallback is public project configuration and must not protect
real identities. Production should use a strong secret stored outside source
control and outside browser code.”

### 23. How is JWT information kept out of settings output?

**A:** “Secret fields use Pydantic's secret type, and model dumps mask sensitive
keys and credential values. The setting should still be kept in `.env` or a secrets
manager rather than source control.”

### 24. Is HS256 a good choice for this system?

**A:** “It is suitable for a shared-secret deployment such as demo and
Supabase-compatible validation, when the secret is strong and protected. External
identity providers using asymmetric keys would require a corresponding public-key
verification design.”

## Demo authentication

### 25. What does the demo-token route do?

**A:** “It accepts an email, checks demo mode, finds the matching seeded profile,
and creates an eight-hour bearer token containing identity and role claims.”

### 26. Why are demo users backed by database profiles?

**A:** “It connects authentication to the same profile records used by the rest of
the support system. It also lets `/me` verify that a profile exists.”

### 27. What happens for an unknown demo email?

**A:** “The route returns 404, `Demo user not found`.”

### 28. What happens if demo mode is disabled?

**A:** “The route returns 403, `Demo authentication is disabled`.”

### 29. How long does a demo token live?

**A:** “Eight hours, or 28,800 seconds.”

### 30. Which claims are set by demo login?

**A:** “`sub`, `email`, `role`, `iat`, and `exp`.”

### 31. What does `/me` return?

**A:** “The authenticated profile's ID, email, full name, and role.”

### 32. What happens if `/me` cannot find the profile?

**A:** “It first checks by subject ID and then by email. If neither finds a profile,
it returns 404, `Authenticated profile not found`.”

### 33. What are the three demo accounts?

**A:** “`admin@clouddesk.demo`, `sam.agent@clouddesk.demo`, and
`vic.viewer@clouddesk.demo`.”

### 34. Does demo login replace real identity infrastructure?

**A:** “No. It is a repeatable offline demonstration, not a user-registration or
real enterprise identity service.”

## Rate limiting

### 35. What type of rate limiter is implemented?

**A:** “A fixed-window rate limiter. The request count belongs to a window
calculated from the current Unix time divided into one-minute intervals.”

### 36. How is a client's counter key built?

**A:** “It combines `rl`, the client IP, and the current window number.”

### 37. What is the default limit?

**A:** “120 requests per minute per client.”

### 38. What happens after the limit is reached?

**A:** “The middleware returns 429, `Rate limit exceeded`, with limit, remaining,
reset, and retry-after headers.”

### 39. What headers are returned on allowed requests?

**A:** “`X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset`.”

### 40. What headers are returned on a blocked request?

**A:** “The limit, zero remaining, reset time, and retry-after time.”

### 41. How does Redis count requests?

**A:** “It increments the window key. On the first increment it sets a 60-second
expiry.”

### 42. Why expire the counter?

**A:** “The expiry prevents old fixed-window counters from remaining in storage
after the window is over.”

### 43. How can the fixed-window algorithm have a burst problem?

**A:** “A client could use one window's last seconds and the next window's first
seconds, producing two bursts close together. A sliding-window limiter would
smooth that edge behavior, but it is not implemented in this phase.”

### 44. What is fake Redis?

**A:** “It is an in-memory Redis-compatible client used for local and offline
tests. It provides the same increment and expiry behavior without a network Redis
server.”

### 45. How does the application select Redis mode?

**A:** “It uses fake Redis when fake mode is enabled or no Redis URL is configured.
Otherwise it creates a Redis async client from the configured URL.”

### 46. What happens if Redis is unavailable?

**A:** “The limiter catches Redis, timeout, and connection errors and fails open,
allowing the request while keeping the normal limit header values.”

### 47. Is fail-open always desirable?

**A:** “It avoids an availability outage, but it may temporarily disable enforcement.
The tradeoff should be monitored and revisited for an environment where strict
rate enforcement is more important.”

### 48. Does rate limiting run for health routes?

**A:** “Yes, because the middleware wraps the application. However, the current
implementation uses the caller IP as the shared key and applies it to all HTTP
requests.”

### 49. Does the implementation distinguish authenticated users for rate limits?

**A:** “Not in the current phase. It uses client IP. A future design could combine
or prioritize authenticated identity and IP, as long as NAT and proxy behavior
are handled correctly.”

### 50. Does rate limiting prevent distributed denial of service?

**A:** “No. It reduces application-level excessive traffic, but upstream network
security, a load balancer, and cloud protection are still needed for broad
distributed attacks.”

## Request tracking

### 51. What does `X-Request-ID` do?

**A:** “It gives one incoming HTTP operation a trace value that can appear in the
response, logs, and audit row.”

### 52. Which request IDs are accepted?

**A:** “A valid value has at least one and at most 128 ASCII characters using
letters, digits, periods, underscores, colons, or hyphens.”

### 53. What happens to an invalid request ID?

**A:** “The middleware replaces it with a generated UUID.”

### 54. Is the request ID authentication?

**A:** “No. It is observability metadata. It should not be used by itself to trust
or identify a user.”

### 55. Why put request-ID middleware outside audit and rate limiting?

**A:** “It makes the ID available to every response, including CORS preflight,
404, 429, and server-error responses.”

### 56. Does the middleware bind the ID to logs?

**A:** “Yes. It uses the logging context manager so JSON log events created during
the request can carry the same request ID.”

### 57. Why expose `X-Request-ID` through CORS?

**A:** “Browsers can read a response header only if CORS exposes it. Exposing it
lets the frontend surface or forward the trace ID.”

## Audit logging

### 58. What does the audit middleware record?

**A:** “For a state-changing request it records actor ID when identifiable,
HTTP method, path, response status, and request ID.”

### 59. Which requests are audited?

**A:** “The middleware bypasses `GET`, `HEAD`, and `OPTIONS`. Other HTTP methods
are watched because they may change state.”

### 60. Why not audit every read-only request?

**A:** “The project requirement records state-changing requests. Auditing every
read could create much more data for limited additional security value.”

### 61. How does it find the actor?

**A:** “It reads the bearer token, verifies it using the effective JWT secret,
and extracts `sub` as the actor ID.”

### 62. Does audit decode expireable tokens differently from normal security?

**A:** “The audit actor helper currently disables expiry verification because it
only attempts actor extraction. Normal route authentication still requires and
checks expiry through `decode_jwt`.”

### 63. What happens if the token is invalid?

**A:** “The actor helper returns null, and the audit row is still written without
an actor ID if the response reaches audit middleware.”

### 64. What fields are in `AuditLog`?

**A:** “ID, optional actor ID, method, path, status code, request ID, optional
JSON data, created time, and updated time.”

### 65. Where does audit middleware write data?

**A:** “Through the application async SQLAlchemy session factory into the
`audit_logs` table in SQLite or the configured PostgreSQL database.”

### 66. What happens if audit storage fails?

**A:** “The middleware catches SQLAlchemy, OS, and runtime exceptions and does not
turn the audit failure into the application response failure.”

### 67. Is audit failure fail-open acceptable?

**A:** “It keeps support operations available, but it means a database outage could
leave missing audit entries. The production design should monitor audit write
failures and escalate or adjust fail behavior for highly sensitive operations.”

### 68. Does audit middleware store request bodies?

**A:** “No. The current `data` field is null. This avoids accidentally storing
ticket text, passwords, or other sensitive content.”

### 69. What response status does audit capture?

**A:** “It captures the HTTP response status. If the application throws outside a
response, middleware records 500 in the audit helper before re-raising.”

### 70. What are its current limitations?

**A:** “It does not audit by route policy, does not store structured change data,
and does not guarantee delivery if the database is unavailable. It is a practical
Phase 3 trail, not a complete tamper-resistant audit platform.”

## Middleware order

### 71. What is middleware?

**A:** “Middleware is code wrapped around an application that can inspect requests
or responses and add shared behavior without repeating it in every route.”

### 72. What is the Phase 3 middleware order?

**A:** “Request-ID is outside, audit is inside request-ID, rate limiting is inside
audit, CORS is inside rate limiting, and FastAPI routes are innermost.”

### 73. Why put request-ID outside all other HTTP guards?

**A:** “It guarantees that every response has a trace header, even if a later
layer returns a 429, CORS error, or application error.”

### 74. Why put audit outside rate limiting?

**A:** “It can observe the final status and create the state-changing audit record
even when the inner rate limiter blocks the route.”

### 75. What is CORS?

**A:** “CORS is a browser-origin policy that controls whether a browser page may
make or read a cross-origin API response. It does not replace authentication.”

### 76. How is CORS configured?

**A:** “The application allows the configured origins, permits all methods and
headers, and exposes `X-Request-ID`.”

### 77. Which app does CORS wrap?

**A:** “The CORS middleware wraps the FastAPI application that contains health and
authentication routes.”

### 78. What is an ASGI middleware wrapper?

**A:** “It is an application-level callable that receives scope, receive, and send
functions and can modify or inspect request and response messages.”

### 79. Can middleware order change behavior?

**A:** “Yes. A middleware placed outside another layer can observe or decorate the
inner response. The actual implementation is intentionally arranged so trace and
audit behavior surround later guards.”

### 80. Why does middleware need to handle non-HTTP scope?

**A:** “ASGI also carries lifespan and WebSocket scope types. The HTTP middleware
passes those scopes through unchanged instead of trying to treat them as HTTP
requests.”

## Routing, 401, 403, and 429

### 81. What is the normal protected-request sequence?

**A:** “A request gets a request ID, is considered by audit middleware, is
counted by the limiter, receives CORS checks, reaches FastAPI, and then runs JWT
and role dependencies.”

### 82. What status does a missing token produce?

**A:** “401 Unauthorized.”

### 83. What status does an expired token produce?

**A:** “401 Unauthorized.”

### 84. What status does a wrong-role request produce?

**A:** “403 Forbidden.”

### 85. What status does excessive traffic produce?

**A:** “429 Too Many Requests.”

### 86. What status does a successful demo login produce?

**A:** “200, with the bearer token and profile information.”

### 87. What status does unknown demo login produce?

**A:** “404, unless demo authentication is disabled first, in which case demo mode
returns 403.”

### 88. Can 403 happen with a perfectly valid JWT?

**A:** “Yes. Authentication has passed, but the role claim is below the route's
minimum role.”

## Testing

### 89. How are JWT and role behaviors tested?

**A:** “Unit tests build FastAPI routes with `get_current_user` and
`require_role`, then send missing, invalid, expired, wrong-secret, viewer, agent,
and admin tokens.”

### 90. What is tested for demo authentication?

**A:** “The tests check the eight-hour expiry, expected subject and role claims,
unknown-user rejection, `/me` profile response, and missing bearer authentication.”

### 91. How is rate limiting tested?

**A:** “Tests use fake Redis to allow an exact number of requests, reject the next
request, separate client keys, verify response headers, and confirm fake-Redis
factory selection.”

### 92. How are middleware and audit behavior tested?

**A:** “ASGI HTTP tests use in-memory SQLite and verify GET does not create an
audit row, POST creates method, path, status, request ID, and actor data, and an
audit token identifies the actor.”

### 93. How is the 19-test result relevant?

**A:** “It is the result of the focused Phase 3 test set combining audit,
authentication, rate-limit, health, and middleware behavior. It does not prove all
future support workflows.”

### 94. Are tests dependent on Docker or external services?

**A:** “No. The focused tests use ASGI transports, in-memory SQLite, fake Redis,
and local signed JWTs.”

### 95. How could the test suite miss a bug?

**A:** “Unit tests may not cover live Redis behavior, live Supabase RLS, reverse
proxy headers, browser CORS in a real network, or database failure recovery.
Those need integration and deployment validation.”

## Security trade-offs

### 96. Why is storing JWTs in localStorage not automatically safe?

**A:** “Browser storage can be affected by scripts on the same origin. The current
phase is backend-oriented and does not implement a frontend storage policy. A
production design should also use secure transport and consider XSS and token
lifetime risks.”

### 97. Is the JWT itself encrypted?

**A:** “No. HS256 signed JWTs are readable by their bearer. They are integrity
protected, not secret. HTTPS is still necessary to protect tokens in network
traffic.”

### 98. Should secrets appear in browser environment variables?

**A:** “No. Server signing secrets must remain server-side. Public `NEXT_PUBLIC_*`
configuration is not appropriate for the JWT secret.”

### 99. How does the system handle IP behind a load balancer?

**A:** “The current limiter reads `scope.client` directly. Behind a proxy, it may
need trusted forwarded-header handling or the load balancer should preserve a
forwarded client identity securely.”

### 100. What is one important remaining security gap in Phase 3?

**A:** “A complete production identity service is not implemented. Demo login is
not real enterprise authentication, and the project still needs live identity,
secrets, TLS, proxy, audit monitoring, and deployment integration.”

## Honest status

### 101. What is implemented and proven locally?

**A:** “JWT verification, role ranking, demo auth routes, the `/me` route, fake
and real-Redis client selection, fixed-window limiting, request IDs, audit
middleware, and middleware assembly are implemented. Focused offline tests pass.”

### 102. What has not been deployed or applied?

**A:** “No live PostgreSQL database was used, no live Redis account was used,
no Docker Compose stack was started, and no cloud service was configured.”

### 103. What should Phase 3 not be claimed as?

**A:** “It should not be claimed as a complete support platform or a production
identity system. It is the authenticated request-control foundation for later
support APIs and workflow features.”
