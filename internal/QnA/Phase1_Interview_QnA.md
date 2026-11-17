# Phase 1 — Interview Questions and Answers

This question bank covers **Phase 1: Runtime Skeleton** only. The sample answers
are written so they can be spoken directly; expand the technical details when the
interviewer asks a follow-up. A separate file should be maintained for each later
phase.

Related reading:

- [Phase 1 plain-language explanation](../explain_codebase/phase1_explained.md)
- [Phase 1 system-design evolution](../design_evolution/Phase1_Project_System_Design_Evolution.md)
- [Phase 1 infrastructure-design evolution](../Infra_design_evolution/Phase1_Infra_design_evolution.md)

## 30-second overview

**Q: Can you summarize Phase 1?**  
**A:** “Phase 1 builds the foundation for CloudDesk Support. It centralizes
application settings, adds health checks, gives HTTP requests traceable IDs, writes
structured logs with common secrets masked, and sets up repeatable offline tests.
It does not yet implement ticket investigation or AI resolutions.”

## Product and scope

### 1. What is CloudDesk Support?

**A:** “It is a support-agent platform for a fictional SaaS company. Its intended
purpose is to investigate customer tickets and help support agents prepare
resolutions. Agents remain in control of consequential actions.”

### 2. What did Phase 1 deliver?

**A:** “It delivered the runtime foundation: configurable settings, JSON logging,
health routes, request-ID middleware, an offline pytest setup, a Makefile, and a
safe environment-variable template.”

### 3. Is the autonomous support agent already implemented?

**A:** “No. Phase 1 does not classify tickets, search a knowledge base, recommend
resolutions, or process refunds. It prepares the service foundation those later
features will use.”

### 4. What routes are available in this phase?

**A:** “The current routes are `/health`, `/health/live`, and `/health/ready`.
Business routes such as ticket creation are planned for later phases.”

### 5. Why build infrastructure before AI features?

**A:** “It gives later features consistent configuration, diagnostic information,
and a repeatable way to test. That makes it easier to find problems before the
application handles real support workflows.”

### 6. Is Phase 1 a microservices system?

**A:** “No. It is a single local FastAPI application. The later target architecture
has more components, but Phase 1 does not run separate service containers.”

## Settings and environment

### 7. How does the application get its settings?

**A:** “It reads environment variables and, for local development, can read a
`.env` file. A typed settings class gathers those values in one place instead of
spreading configuration throughout the code.”

### 8. Why use environment settings instead of hard-coding values?

**A:** “The same code can run with different local, test, or deployment settings.
Changing a database or model-provider choice does not require editing application
logic.”

### 9. What is the difference between `.env.example` and `.env`?

**A:** “`.env.example` is the committed template with safe example values.
Developers copy it to `.env` and put machine-specific values there. The real `.env`
is ignored by Git so private settings are not committed.”

### 10. Does the setup command overwrite an existing `.env`?

**A:** “No. The Makefile is designed to copy `.env.example` only when `.env` is
missing. That preserves the developer's existing local configuration.”

### 11. Why are settings cached?

**A:** “Settings are loaded once and reused, so the application uses one consistent
configuration during a run. Because of that, a `.env` change requires restarting
the server.”

### 12. How are sensitive settings represented?

**A:** “Secret values use Pydantic's secret type, and the settings dump masks
sensitive fields and URL credentials. The example file uses placeholders, not real
credentials.”

### 13. Does secret masking guarantee that no secret can ever appear in logs?

**A:** “No automated pattern matcher can guarantee that. The logger masks common
credential patterns, but the application should still avoid logging secrets in the
first place.”

### 14. Why does the settings class validate some values?

**A:** “It catches invalid configuration early. For example, dimensions and
timeouts must be positive, and a refund amount without approval cannot be negative.”

## Logging and observability

### 15. What is a JSON log?

**A:** “It is a log record with named fields, such as time, severity, message, and
request ID. Those consistent fields are easier to search and process than arbitrary
text.”

### 16. What information can a Phase 1 log include?

**A:** “It can include a timestamp, log level, logger name, message, request ID,
workflow ID when available, exception details, and safe extra fields.”

### 17. How are request and workflow IDs added to logs?

**A:** “The logger reads them from context associated with the current operation.
The request middleware sets the request ID for the lifetime of an HTTP request.
Workflow IDs are supported for later workflow code.”

### 18. What kinds of values does the logger try to mask?

**A:** “It masks common patterns for passwords, API keys, bearer tokens, JWTs, and
credentials in URLs or query strings. It also masks fields whose names indicate
they contain sensitive values.”

### 19. Why use structured logs instead of simple print statements?

**A:** “Structured records are more consistent and easier for people and monitoring
tools to filter. They also give us a standard place for request context.”

### 20. Does Phase 1 include full workflow tracing?

**A:** “No. The log format supports a workflow ID, but the workflow graph and its
event tracing belong to later phases.”

## HTTP routing, middleware, and health

### 21. What is middleware?

**A:** “Middleware is a shared layer around the application. It can apply behavior
to every request and response without duplicating that behavior inside every route.”

### 22. What is the HTTP request path in Phase 1?

**A:** “A request enters the request-ID middleware, then CORS, then the FastAPI
application and its health router. The response travels back through CORS and the
request-ID middleware.”

### 23. What does the request-ID middleware do?

**A:** “It keeps a safe incoming request ID or creates a new unique one, adds it to
the log context, and attaches it to the HTTP response as `X-Request-ID`.”

### 24. How does it decide whether an incoming request ID is safe?

**A:** “It accepts a bounded ASCII value containing letters, digits, periods,
underscores, colons, or hyphens, up to 128 characters. If the value is invalid, it
generates a UUID instead.”

### 25. Does the request ID provide authentication or authorization?

**A:** “No. It is only for tracing a request. Authentication and role-based access
control are separate work planned for a later phase.”

### 26. Why add the ID to errors and CORS preflight responses too?

**A:** “Those responses can still be part of a user-visible problem. Returning an
ID consistently makes them easier to investigate.”

### 27. What is CORS?

**A:** “CORS is a browser rule that controls which website origins may read an API
response. It is not authentication, a reverse proxy, or a connection to another
service.”

### 28. Why is the request-ID middleware outside CORS?

**A:** “The outer layer can add the response ID even when CORS or error handling
produces the response before a normal route completes.”

### 29. What is the difference between `/health` and `/health/live`?

**A:** “Both return a basic running response and do no dependency checks. The
separate liveness route is intended for process-health probes.”

### 30. What does `/health/ready` check?

**A:** “It checks whether settings for the database, Redis, vector store, and model
provider look sufficient. It returns `ready` when they pass or `degraded` with
individual checks when they do not.”

### 31. Does `/health/ready` prove that the database is reachable?

**A:** “No. It checks configuration only. Live connection checks should replace
those checks when the actual dependency clients are implemented.”

### 32. Why keep liveness checks free of dependency calls?

**A:** “A liveness check should answer whether the web process itself can respond.
If it depended on a database, a temporary database outage could make a healthy
process look dead and trigger unnecessary restarts.”

## Offline testing

### 33. How do tests stay offline?

**A:** “`tests/conftest.py` sets test-safe environment values before the app is
imported: fake model and Redis modes, in-memory vector storage, and in-memory
database and checkpoint settings.”

### 34. Does that mean Phase 1 already has Redis and a database connection?

**A:** “No. Those settings make the test environment ready for future components.
The current tests do not connect to a real Redis or database service.”

### 35. How do the API tests exercise HTTP behavior without starting a server?

**A:** “They use HTTPX's ASGI transport to send requests directly to the application
inside the test process. That exercises routes and middleware without opening a
network port.”

### 36. What does the current test suite cover?

**A:** “It checks settings defaults and environment loading, secret redaction, JSON
logging, health behavior, request-ID generation and propagation, error responses,
and CORS exposure of the response header.”

### 37. How many tests passed?

**A:** “The current offline suite passed 14 tests. That result covers the Phase 1
components present now, not features scheduled for future phases.”

### 38. Why use a fake model provider?

**A:** “It avoids API keys, external network calls, and model charges, while making
the test environment predictable.”

### 39. What is `pytest-asyncio` used for?

**A:** “It provides pytest support for asynchronous tests and fixtures. The project
configures automatic asyncio mode and a shared fixture loop for future async test
coverage.”

### 40. How do you run the tests?

**A:** “The Makefile defines `make test`. In the validation environment, GNU Make
was unavailable, so I ran the equivalent `.venv` Python pytest command directly.
The 14 tests passed.”

## Makefile and developer workflow

### 41. What does the Makefile provide?

**A:** “It defines shortcuts for setting up the development environment, running
tests, checking selected lint rules, and starting the local backend.”

### 42. What does `make setup` do?

**A:** “It creates or updates the local virtual environment, installs the project
and development dependencies, and creates `.env` from the example only when needed.”

### 43. What does `make lint` check?

**A:** “It runs Ruff on the backend and tests using the selected error, syntax, and
undefined-name rule groups.”

### 44. Is the Makefile fully verified on this machine?

**A:** “The underlying test, lint, and editable-install commands were checked
directly. GNU Make was not installed, so the targets have not yet been run through
the `make` executable. The phase plan remains in progress pending that check.”

### 45. Does Phase 1 start Docker containers?

**A:** “No. There is no Dockerfile or Compose manifest in Phase 1. The backend runs
as a local Python process; the Docker deployment shape is planned for later.”

### 46. What does the backend bind to locally?

**A:** “The Makefile's backend target binds Uvicorn to `127.0.0.1:8000`, which is
the local machine. This is a development setup, not a public deployment.”

## Security, trade-offs, and next steps

### 47. What security protections are present in Phase 1?

**A:** “The phase keeps secrets out of the committed environment template, ignores
the real `.env`, masks common secrets in settings and logs, and validates request
IDs before echoing them.”

### 48. What important security work is not included yet?

**A:** “There is no JWT authentication, role enforcement, rate limiting, or audit
middleware yet. Those controls are planned for the identity and request-guards
phase.”

### 49. Why not add Docker and external services immediately?

**A:** “Phase 1 is focused on the smallest runtime foundation. Keeping it local and
offline reduces moving parts while we establish configuration, request handling,
health checks, and tests.”

### 50. What is the main limitation of the current design?

**A:** “It verifies that the application can start and handle basic health requests,
but it does not yet prove that external dependencies are reachable or that ticket
workflows work.”

### 51. What happens after Phase 1?

**A:** “The next phase adds persistent data models, repositories, and demo data.
Identity and request protections follow, then the support APIs, knowledge pipeline,
tools, workflow agents, approval handling, user interface, and delivery work.”

### 52. What would you improve next in the infrastructure?

**A:** “I would add live readiness probes when the database and other clients exist,
then verify the Makefile targets with GNU Make. Container health checks and network
configuration belong in the later container-delivery phase.”

## Honest Phase 1 status

- Implemented locally: settings, JSON logging, health routes, request-ID middleware,
  offline pytest setup, Makefile, and `.env.example`.
- Validated locally: 14 pytest tests passed; the configured Ruff checks passed; the
  example environment file contains every current application setting.
- Not yet verified through its normal entry point: GNU Make was unavailable, so the
  Makefile targets were not invoked using `make`.
- Not implemented in this phase: Docker/Compose networking, ticket persistence,
  authentication, and the AI support workflow.
