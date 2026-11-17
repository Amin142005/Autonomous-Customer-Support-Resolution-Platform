# Phase 1 — The Foundation of CloudDesk Support

## A plain-language presentation

> **Use this as a speaking script.** Technical terms are explained as they appear.

CloudDesk is being built to help a company's support team investigate customer
problems and prepare helpful resolutions. The support agent remains in control,
especially when a decision could affect a customer's account or money.

Phase 1 does not build the AI support workflow yet. It builds the dependable
foundation that the later features will use: application settings, basic service
checks, request tracking, safe logs, and a way to test without relying on paid or
external services.

One way to picture it is preparing a well-organized help desk before the support
specialists arrive. We set up the operating instructions, the status board, the
tracking numbers, and the practice environment first.

## What happens when a request reaches the service

```text
Application starts
  └─ Reads its settings

Request arrives
  └─ Gets a tracking ID
       └─ Passes through the web-service boundary
            └─ Reaches a health-check route
                 └─ Returns a response with the same tracking ID
                      └─ Writes a structured, privacy-conscious log
```

In this phase, the available routes are health checks. The ticket creation,
customer lookup, and AI resolution workflow are planned for later phases.

## The Phase 1 pieces, in everyday language

### 1. Settings: one place for the operating instructions

The application needs to know things such as which database or AI provider to use.
Those choices come from environment settings, usually kept in a local `.env` file,
instead of being scattered through the source code.

The committed `.env.example` is a safe starter template with example values and
empty secret fields. A developer can copy it to `.env` and customize their own
machine. The real `.env` file is ignored by Git so private values are not included
in normal source control changes.

Settings are loaded once and reused while the application is running. Sensitive
values are represented as secrets and are masked if settings are displayed.

**Why it matters:** the same application can use safe local settings during
development and different settings in another environment without changing its code.

### 2. Health checks: a simple status board

The service provides three checks:

- `/health` and `/health/live` give a basic “I am running” response. They do not
  contact other services.
- `/health/ready` checks whether the required connection settings appear to be
  configured. It reports “ready” or “degraded,” with the check results.

An important limitation: readiness currently checks configuration, not whether a
database, cache, or other service is actually reachable. Live dependency checks can
be added when those connections are implemented.

**Why it matters:** monitoring tools and operators have a quick way to tell whether
the web service is alive and whether its basic setup looks sufficient.

### 3. Request IDs: a tracking number for each visit

When a web request arrives, middleware checks for a safe tracking ID. If one is
missing or malformed, the service creates a new unique ID. That ID is returned in
the `X-Request-ID` response header and is also added to the request's log context.

Middleware is a small layer around the application that can handle shared tasks
before and after a route runs. In this case, it adds tracking consistently, including
for not-found and server-error responses.

**Why it matters:** if someone reports a problem, an operator can use the tracking
ID to find the related log entries without guessing which request caused them.

### 4. Structured logs: consistent records, with sensitive values masked

The application writes logs as JSON—consistent, labeled records rather than
unstructured sentences. Each record can include the time, severity, message,
request ID, and workflow ID when available.

Before log text and extra fields are written, patterns for common credentials—such
as passwords, API keys, bearer tokens, and URL passwords—are masked.

**Why it matters:** structured logs are easier for monitoring tools and people to
search, while the masking reduces the chance of exposing credentials in routine
diagnostics.

### 5. Offline tests: a safe practice environment

The test setup sets predictable local options before the application is imported:
fake AI, in-memory knowledge storage, fake-Redis mode, and in-memory SQLite and
checkpoint settings. This lets the current tests run without a paid AI key, a cloud
database, or Docker.

The tests check settings and log masking, health responses, and request-ID behavior.
They verify the components that exist now; they do not prove that future ticket,
payment, or AI workflows are complete.

**Why it matters:** developers can repeat checks locally and get consistent results
without contacting real customer systems or incurring external service costs.

### 6. Makefile: shortcuts for routine developer tasks

The Makefile defines short commands for setting up the local environment, running
tests, checking code style, and starting the backend. For example, `make test` is
intended to run the offline test suite, while `make backend` starts the local API.

The setup command installs the project's development dependencies and creates `.env`
from `.env.example` only when `.env` does not already exist. That avoids overwriting
a developer's local settings.

## How the pieces fit together

1. The developer prepares local settings from the example template.
2. The application reads those settings when it starts.
3. A request enters through the tracking layer and gets a request ID.
4. The health route returns a simple status.
5. The same request ID appears in the response and related logs.
6. Tests exercise these behaviors using local fakes rather than external services.

Together, these choices make the early application easier to configure, diagnose,
and test before more complex business features are added.

## What Phase 1 does not do

Phase 1 is infrastructure, not the finished support product. It does not yet create
or store support tickets, authenticate support agents, search a real knowledge base,
make AI recommendations, send replies, or process refunds. Those capabilities belong
to later tasks and must not be presented as already implemented.

The planned next steps add data storage and demo records, then identity and protected
requests. Later phases add the support API, knowledge search, safe tools and rules,
the AI workflow and approval process, the agent console, and delivery checks.

## Short answers for likely questions

**Is this already an autonomous support agent?**  
No. Phase 1 builds the application's runtime foundation. The ticket investigation
and resolution workflow comes later, with human approval for consequential actions.

**Does “ready” prove that the database is online?**  
Not yet. The current readiness endpoint checks configuration. It does not make live
connections to the database or other dependencies.

**Why use fake services in tests?**  
They make tests repeatable and offline. They also avoid using real accounts, paid
services, or customer data while checking the current foundation.

**How do you trace one failed request?**  
Use its `X-Request-ID` value to locate log records carrying the same ID.

## Current validation note

The offline test suite passed **14 tests**, the configured Ruff checks passed, and
the example environment file was checked against every application setting. GNU
Make was not installed in the validation environment, so the Makefile targets were
not invoked through `make`; their underlying test, lint, and setup commands were
checked directly. Phase 1 remains marked in progress until Makefile invocation can
be verified.
