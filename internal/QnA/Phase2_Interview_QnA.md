# Phase 2 — Interview Questions and Answers

This question bank covers **Phase 2: Persistence and Demo Data**. The answers are
written so they can be spoken directly; use the follow-up details when an
interviewer asks for more depth.

Related reading:

- [Phase 2 plain-language explanation](../explain_codebase/phase2_explained.md)
- [Phase 2 system-design evolution](../design_evolution/Phase2_Project_System_Design_Evolution.md)
- [Phase 2 infrastructure evolution](../Infra_design_evolution/Phase2_Infra_design_evolution.md)
- [Phase 2 task status](../../TASK.md)

## 30-second overview

**Q: Can you summarize Phase 2?**  
**A:** “Phase 2 built the data foundation for CloudDesk Support. It defines the
records the system stores, adds portable SQLAlchemy models, prepares PostgreSQL
schema and access policies, adds async repositories, and loads fictional demo
records into an empty local database when demo mode is enabled. The work is tested
offline with SQLite. It does not yet include the ticket API or AI workflow, and the
PostgreSQL setup has not been applied to a live account.”

## Product scope and architecture

### 1. What is the goal of Phase 2?

**A:** “The goal is to give future support features a consistent place to save and
retrieve customers, tickets, messages, subscriptions, and workflow records. It also
gives developers a repeatable fictional dataset to use locally.”

### 2. What were the Phase 2 subtasks?

**A:** “P2-1 defined SQLAlchemy entities and shared category values. P2-2 added
PostgreSQL schema, row-level security, and migrations. P2-3 added the repository
layer. P2-4 added sample records and startup seeding.”

### 3. What did Phase 2 actually deliver?

**A:** “It delivered the data models, SQL files for PostgreSQL, async repositories,
SQLite table creation at startup, a conditional demo-data bootstrap, JSON fixtures,
and PostgreSQL seed SQL generated from those fixtures.”

### 4. Is the support platform complete after Phase 2?

**A:** “No. Phase 2 provides persistence foundations. The ticket and customer APIs,
authentication, AI investigation, knowledge search, approval workflow, and agent
console belong to later phases.”

### 5. What is the current HTTP request path?

**A:** “A request passes through request-ID middleware, then CORS, then FastAPI.
At this point the implemented HTTP routes are health checks. The ticket routes
that will use repositories are still future work.”

### 6. Is this a microservices or Docker-based system now?

**A:** “No. The current backend is one local FastAPI process. Phase 2 does not add
Dockerfiles, Compose, or a container network. Those are planned for later delivery
work.”

## Data models and shared values

### 7. What is an entity in this project?

**A:** “An entity is the application's standard definition of a type of record.
For example, the Ticket entity defines the fields and relationships for a support
ticket. The SQLAlchemy entities are in `backend/app/models/entities.py`.”

### 8. Which kinds of records are modeled?

**A:** “The models cover profiles, customers, subscriptions, workspaces, products,
tickets, ticket messages, support articles, incidents, workflow runs and events,
resolution actions, approval requests, escalations, customer memory, and audit
logs.”

### 9. Why define ticket categories in one shared enum?

**A:** “A shared enum gives every part of the application one spelling and set of
allowed categories. It reduces mismatches between stored tickets, API payloads,
and future workflow code.”

### 10. What ticket categories are supported?

**A:** “There are ten: login issue, billing, API failure, workspace permissions,
storage quota, integration, feature request, account, security, and other.”

### 11. Which other shared values are defined?

**A:** “The project also defines severity, status, channel, and support-role values.
For example, severity ranges from low to critical, and channels include email,
chat, web, and API.”

### 12. Why use string IDs instead of database-specific UUID columns?

**A:** “The models use 36-character string IDs to keep the application model
portable across SQLite and PostgreSQL. The values still look like UUIDs, but the
column type is more consistent between the two databases.”

### 13. Why use JSON columns?

**A:** “Some records contain flexible structured details, such as workspace
settings or workflow state. The models use portable JSON rather than relying on a
PostgreSQL-only JSONB type.”

### 14. How do records relate to each other?

**A:** “A ticket points to its customer and can point to a workspace. Messages and
workflow records point back to the ticket. Subscriptions and workspaces point to
customers. These relationships let the application retrieve related context
without copying all the same information into each record.”

### 15. What keeps the Python models and PostgreSQL schema aligned?

**A:** “The schema tests compare the tables in the PostgreSQL SQL files with the
SQLAlchemy metadata, check that each model has an `updated_at` field and trigger,
and verify that migrations cover the expected tables. Those are static checks;
they do not replace applying and testing the SQL against a live PostgreSQL
database.”

## SQLite and PostgreSQL

### 16. Why support both SQLite and PostgreSQL?

**A:** “SQLite makes local development and offline tests simple. PostgreSQL is the
planned hosted database. Using the same SQLAlchemy entities for both makes it
easier to develop locally without changing the application's record definitions.”

### 17. What does the application use locally?

**A:** “The default local configuration uses SQLite. The backend creates its
parent data directory when needed, creates missing tables at startup, and can
load demo records when `DEMO_MODE=true`.”

### 18. What is `database/schema.sql` for?

**A:** “It is the complete PostgreSQL schema for a clean hosted database. It
creates the tables, relationships, and update-time triggers.”

### 19. What is a migration?

**A:** “A migration is a numbered record of a database change. The first migration
creates the schema and the second applies the RLS setup. After a migration has
been applied, future changes should be added in a new numbered file rather than
editing the old one.”

### 20. What does the `updated_at` trigger do?

**A:** “When a row is updated in PostgreSQL, the trigger automatically sets its
`updated_at` value to the current time. This gives records a consistent
last-updated timestamp.”

### 21. Has the PostgreSQL schema been applied to Supabase?

**A:** “No. The schema, policies, migrations, and seed script are prepared in the
repository, but no live PostgreSQL account was used or changed.”

### 22. How does a developer set up a clean PostgreSQL database?

**A:** “The documented manual path is to apply `database/schema.sql`, then
`database/rls_policies.sql`, then `database/seed.sql`. If a database is managed by
migrations, apply the numbered migration files in order instead. The two setup
paths should not both be applied to the same database.”

## Access control and security boundaries

### 23. What is row-level security?

**A:** “Row-level security, or RLS, is a set of rules enforced by PostgreSQL that
controls whether a database role can read or change records. It provides a
database-side access boundary in addition to checks in the application.”

### 24. What do the Phase 2 RLS policies allow?

**A:** “They enable authenticated users with a recognized support profile to read
the application records. Direct writes from authenticated clients are withheld.
The backend is intended to perform writes using its server-only service-role
credential.”

### 25. Does RLS replace API authentication?

**A:** “No. RLS protects direct database access. The API still needs its own
authentication and role checks, which are planned for Phase 3.”

### 26. Is the service-role credential safe to put in the frontend?

**A:** “No. It is a powerful server-side credential and must never be exposed to
the browser. The browser should communicate with the backend, not use that key.”

### 27. Does Phase 2 implement refund approval or account-change approval?

**A:** “No. Phase 2 models approval-related records and prepares the data layer.
The actual policy and human approval workflow are later work. No demo seed
operation performs a refund or account change.”

### 28. Does the prompt-injection ticket execute its contents?

**A:** “No. The example is stored as ticket text for future safety testing. It is
customer data, not a command. The guardrail and workflow behavior for that case
belong to later phases.”

## Repository layer

### 29. What is a repository?

**A:** “A repository is a focused component that handles database queries for a
kind of record. A ticket repository can find a ticket by its number or list a
customer's ticket history.”

### 30. Why not put SQL directly in API routes?

**A:** “Keeping database queries in repositories prevents the same query logic
from being copied across routes and services. It also keeps the API layer focused
on HTTP and validation instead of persistence details.”

### 31. What operations does the base repository provide?

**A:** “The shared repository supports lookup by ID, paginated listing, adding or
creating records, updating mapped fields, and deleting records. It rejects
invalid pagination and prevents updates to primary-key fields.”

### 32. What specialized repository queries are included?

**A:** “There are focused queries for customer context, ticket number and filters,
customer ticket history, ordered ticket messages, latest workflow runs, workflow
events, pending approvals, customer memory, active incidents, support articles,
open escalations, profiles, and audit logs.”

### 33. Do repositories commit transactions?

**A:** “No. They flush changes so generated IDs and database errors are available,
but the caller owns the transaction and decides whether to commit or roll back.
That lets a service treat a multi-step operation as one unit.”

### 34. Why are the repositories asynchronous?

**A:** “The backend uses FastAPI and SQLAlchemy's async support. Async database
calls let the application await I/O instead of blocking the event loop while a
database operation is in progress.”

### 35. Do repositories call the AI model?

**A:** “No. Repositories own persistence and queries. They do not call LLMs or
decide how to resolve a support issue.”

### 36. Are the repositories already used by ticket API routes?

**A:** “No. The repository layer and a session dependency are ready, but the ticket
and customer API routes have not been implemented yet.”

### 37. Why does the bootstrap use a SQLAlchemy session directly instead of
repositories?

**A:** “The bootstrap loads a related set of records as one transaction during
application startup. It uses the session to insert those ordered fixture batches.
The domain repositories are intended for later application operations such as
ticket and customer services.”

## Sample data and startup

### 38. What is in the demo dataset?

**A:** “It contains three support profiles, eight fictional customers, eight
subscriptions, eight workspaces, four products, one active incident, and thirteen
tickets with thirteen initial messages.”

### 39. What do the thirteen tickets cover?

**A:** “They cover the planned examples: SSO problems, a seat-billing question, API
rate limits, storage quota, possible security compromise, missing files, sharing
permissions, an integration failure, account deletion, a feature request, a
payment dispute, MFA lockout, and a prompt-injection attempt.”

### 40. Is the sample data real customer data?

**A:** “No. It is fictional demo data, and the customer email addresses use the
reserved `.test` domain. Real customer details and credentials should never be
added to these fixtures.”

### 41. When does startup load the fixtures?

**A:** “Only when `DEMO_MODE=true` and all mapped application tables are empty.
Startup creates missing tables regardless, but it does not seed a database when
demo mode is off.”

### 42. What happens if even one application table already has records?

**A:** “The bootstrap leaves the database unchanged and does not add the rest of
the demo set. This avoids mixing the sample dataset into an existing database.”

### 43. How does the bootstrap avoid duplicate records?

**A:** “It checks whether the application tables contain any data before loading.
After the first successful load, a later startup sees existing records and skips
the seed.”

### 44. Is loading the seed atomic?

**A:** “Yes. The seed service loads fixture batches inside a transaction. If a
fixture is invalid or a database constraint fails, the transaction is rolled back
instead of leaving a partial dataset.”

### 45. What validation does the seed service perform?

**A:** “It requires each file to be a JSON array of objects, reports invalid JSON
with its file and location, and checks that the customer and ticket files contain
the required eight and thirteen records. Database constraints validate
relationships and required fields during insertion.”

### 46. What are previous-resolution examples used for?

**A:** “They are stored as retrieval fixtures for a later similar-case feature.
There is no dedicated previous-resolution table in this phase, so the bootstrap
does not insert them into the database.”

### 47. How does the PostgreSQL seed stay consistent with the JSON data?

**A:** “`database/generate_seed_sql.py` generates `database/seed.sql` from the
same fixture files. A test compares the checked-in SQL with the generated output,
so a fixture change makes a stale SQL seed visible.”

### 48. What happens if a required fixture file is missing or malformed?

**A:** “The seeding operation fails visibly and its transaction is rolled back.
The service does not silently skip the file or report a successful seed.”

## Testing and validation

### 49. How was the repository and bootstrap work tested?

**A:** “The async repositories were tested with SQLite for CRUD, filters, eager
loading, ordering, and domain queries. Bootstrap tests check record counts,
idempotence, non-demo behavior, malformed fixture data, startup wiring, and
generated PostgreSQL seed consistency.”

### 50. How many tests passed?

**A:** “The full offline suite passed 32 tests, and the configured Ruff checks
passed. No live PostgreSQL account or Docker environment was used.”

### 51. Does passing SQLite tests prove PostgreSQL behavior?

**A:** “No. It validates the portable SQLAlchemy behavior and local bootstrap.
The PostgreSQL SQL files also have static consistency tests, but they still need
to be applied and exercised against PostgreSQL before claiming live database
validation.”

### 52. Does `/health/ready` confirm that the database connection works?

**A:** “No. It checks whether the settings look configured. Database initialization
does happen during application startup, but the readiness route itself does not
perform a live connection probe.”

### 53. How can someone run the tests on Windows?

**A:** “The project uses the virtual-environment Python executable:
`.venv\\Scripts\\python.exe -m pytest -q`. The same test suite runs without cloud
credentials or Docker.”

### 54. How do you validate that JSON seed data is up to date?

**A:** “The unit test calls the SQL seed generator and compares its result with
`database/seed.sql`. That catches a mismatch between the sample fixture source and
the PostgreSQL script.”

## Design choices and trade-offs

### 55. Why not use only PostgreSQL in development?

**A:** “SQLite keeps local setup and tests lightweight and offline. PostgreSQL
remains the intended hosted database, and the shared models reduce differences
between the two.”

### 56. Why use both a model definition and SQL schema files?

**A:** “The SQLAlchemy models are used by the Python application across SQLite and
PostgreSQL. The SQL files provide explicit PostgreSQL setup, RLS policies, and
migrations for the hosted database.”

### 57. Why keep seed data in JSON?

**A:** “JSON is simple to inspect and reuse in local bootstrap code and other
offline tests. The PostgreSQL seed script is generated from those same files to
avoid maintaining a separate hand-written copy.”

### 58. Why seed only an empty database instead of updating records individually?

**A:** “The bootstrap is for initializing a clean demo environment, not for
migrating or overwriting user data. Skipping any non-empty database is a safer and
clearer boundary.”

### 59. What is the trade-off of this empty-database bootstrap?

**A:** “It does not repair a partially populated database or update existing demo
records. That behavior is intentional for the demo loader; schema evolution is
handled through migrations, and future production data changes need explicit
services or migrations.”

### 60. Why keep transaction commits outside repositories?

**A:** “A service may need several database operations to succeed together. If
repositories committed individually, a later failure could leave only part of the
operation saved. The caller can control one transaction around the complete
operation.”

### 61. What are the main limitations of Phase 2?

**A:** “The ticket API and consumers of the repositories are not implemented yet.
The PostgreSQL SQL has not been run against a live database, Docker networking
does not exist yet, and previous-resolution examples are not persisted to a
dedicated table.”

### 62. What would you do next?

**A:** “I would add JWT-based identity and server-side role enforcement, then build
ticket and customer APIs on top of the repositories. After that, the workflow
agents can use this persistence layer to load customer context and record their
work.”

## Honest Phase 2 status

- **Implemented locally:** all Phase 2 subtasks—entities and enums, PostgreSQL
  schema/RLS/migrations, async repositories, sample fixtures, and startup demo
  bootstrap.
- **Validated locally:** 32 offline tests passed and configured Ruff checks
  passed. The fixture loader and SQLite path were exercised locally.
- **Not validated against a live service:** PostgreSQL schema, RLS, migrations,
  and seed SQL have not been applied to a hosted database.
- **Not implemented in this phase:** ticket/customer APIs, API authentication,
  AI ticket workflow, Docker/Compose networking, and live deployment.
