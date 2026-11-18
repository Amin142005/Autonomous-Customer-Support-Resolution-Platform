# Phase 2 — Giving CloudDesk a Reliable Memory

## A plain-language presentation

> **Use this as a speaking script.** It explains the design without assuming the
> audience has a software background.

Phase 1 prepared the basic service foundation. Phase 2 gives CloudDesk a place to
store information and a safe set of example records to work with.

Think of a support team arriving at a new help desk. Before they can investigate a
customer's issue, the desk needs organized files, a consistent filing system, and a
small practice set of cases. Phase 2 builds those pieces. It does not yet build the
ticket-handling API or the AI workflow.

## The Phase 2 pieces, in everyday language

### 1. Data models: the forms every record follows

The application has standard forms for the information it needs: customer profiles,
subscriptions, workspaces, tickets, messages, products, incidents, and workflow
records. A ticket, for example, has a number, a subject, a message, a channel, a
status, and a link to the customer who sent it.

These forms are defined in `backend/app/models/entities.py`. Shared labels—such as
ticket categories, severity levels, and statuses—are defined in
`backend/app/schemas/common.py`. This keeps the application from using different
spellings for the same concept in different places.

**Why it matters:** information can be saved and retrieved consistently, whether
CloudDesk is running on a developer's computer or on a hosted database.

### 2. Two database choices, one set of forms

The project supports two kinds of storage:

- **SQLite** is a lightweight database used for local development and offline demos.
- **PostgreSQL** is intended for a hosted environment such as Supabase.

Both use the same application data models. That means the team can practice locally
without changing the way the application describes a ticket or customer when it is
later connected to a hosted database.

The PostgreSQL setup is documented in `database/schema.sql`. It creates the tables,
relationships, and automatic update times. Numbered files in
`database/migrations/` are the history of database changes. Once a migration has
been used, later changes are added in a new file rather than rewriting the old one.

**Why it matters:** the database can evolve in a trackable way, and the same data
design can be used in local and hosted environments.

### 3. Database access rules: read access is not write access

The PostgreSQL setup enables row-level security, often shortened to RLS. In plain
language, RLS is a set of database-side rules that checks who is asking for data.
Recognized support roles can read records, while direct writes from signed-in
clients are withheld.

Changes are intended to go through the backend, which holds the server-only
database credential. That credential must never be placed in the browser.

These are the database guardrails, not the complete sign-in system. Phase 3 builds
the application's login and role checks. The approval flow for consequential
actions—such as refunds or account changes—also comes later; Phase 2 does not
approve or perform those actions.

**Why it matters:** access to stored information and the ability to change it are
treated as separate responsibilities.

### 4. Repositories: a tidy counter between the application and storage

The application does not need every part of the system to write database queries
for itself. Instead, it can ask a repository to perform a focused task, such as
“find this ticket,” “show this customer's recent tickets,” or “save this message.”

The repositories live in `backend/app/repositories/`. They handle database
communication but do not decide how to resolve a customer's problem and do not call
an AI model. The part of the application coordinating the work remains responsible
for the overall transaction.

**Why it matters:** data access has one predictable home, which is easier to test,
review, and change than database code scattered throughout the application.

### 5. Demo records: a safe practice set

The sample records are fictional and live in `sample_data/`. They include:

- Three demo support profiles and eight fictional customers.
- Their subscriptions and workspaces, plus example products and an active incident.
- Thirteen tickets, `CD-1001` through `CD-1013`, with initial customer messages.
- Scenarios such as a billing question, login trouble, missing files, account
  deletion, and a ticket containing an instruction-like message.

The instruction-like ticket is deliberately stored as customer-submitted text. It
is test material, not an instruction for CloudDesk to follow. Previous-resolution
examples are also included as a fixture for a later similarity-search feature; they
are not inserted into a database table in this phase.

**Why it matters:** the team can test how data is organized using repeatable,
fictional examples instead of real customer records.

### 6. Startup bootstrap: prepare the local practice database

When the backend starts, it creates any missing tables. If `DEMO_MODE` is enabled
and the database is completely empty, the bootstrap reads the JSON fixtures and
loads the records in relationship order—for example, customers before their tickets.
The operation is transactional: if loading fails, it does not leave a half-loaded
demo behind.

If the database already contains data, the bootstrap leaves it alone. Running the
startup process again therefore does not duplicate the demo records. When demo mode
is off, the application creates tables but does not insert the demo data.

The bootstrap is in `backend/app/services/seed_service.py`, and database startup
support is in `backend/app/core/database.py`. PostgreSQL seed SQL can also be
generated from the same JSON files with `database/generate_seed_sql.py`, so the
local and hosted examples start from the same source records.

**Why it matters:** a developer can start with a ready-made local dataset without
accidentally overwriting an existing database or contacting an external service.

## How the pieces fit together

```text
Backend starts
  └─ Reads the configured database choice
       └─ Creates missing tables from the shared data model
            └─ Checks whether the database is empty
                 ├─ Demo mode + empty database → load fictional sample records
                 └─ Otherwise → leave existing records unchanged

Application service
  └─ Asks a repository to read or save a record
       └─ Repository sends the database query
            └─ Data is returned in the same standard format
```

In short, the models define the forms, the database stores the forms, repositories
manage the conversations with storage, and the demo bootstrap fills a new local
database with safe practice data.

## What Phase 2 does not do

Phase 2 creates the data foundation; it is not the finished support product. It does
not yet provide the complete ticket API, sign-in flow, AI investigation, knowledge
search, approval workflow, or agent console. Those belong to later phases.

The PostgreSQL files and policies have been checked for consistency with the
application models, but they have not been applied to a live PostgreSQL account.
The demo data and database behavior have been tested locally with SQLite.

## Short answers for likely questions

**Why support both SQLite and PostgreSQL?**  
SQLite makes local practice simple and offline. PostgreSQL is the planned hosted
option. The application uses the same data definitions for both.

**How do you avoid loading the demo data twice?**  
The startup bootstrap checks all application tables first. It loads only when the
database is empty, and it performs the load as one transaction.

**Can the browser make unrestricted database changes?**  
No. The PostgreSQL policies withhold direct authenticated writes. Intended changes
go through the backend, which keeps the server database credential private.

**Does this phase already let AI resolve tickets?**  
No. Phase 2 stores and prepares the data. The ticket API, AI workflow, and human
approval steps are future work.

## Current validation note

The offline test suite passed **32 tests**, including checks for the expected demo
record counts, repeat-start behavior, and the rule that demo data is not loaded when
demo mode is off. Ruff checks passed. No live PostgreSQL database was used.
