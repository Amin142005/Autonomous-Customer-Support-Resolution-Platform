# Autonomous Customer Support & Resolution Platform

CloudDesk is a support-agent platform that investigates incoming tickets and proposes
resolutions for human review. The product requirements and safety constraints are
defined in [CLAUDE.md](./CLAUDE.md).

## Project documents

- [PLAN.md](./PLAN.md) — requirement catalog and project acceptance criteria.
- [PLAN_PHASE.md](./PLAN_PHASE.md) — phase goals, tests, and exit criteria.
- [TASK.md](./TASK.md) — execution checklist.
- [MEMORY.md](./MEMORY.md) — durable decisions and verified project status.
- [Support workflow skill](./.cursor/skills/clouddesk-support/SKILL.md) — implementation
  and validation procedure.
- [Architecture](./docs/ARCHITECTURE.md) — system boundaries and runtime flow.
- [API contract](./docs/API_CONTRACT.md) — route and payload contract.
- [Database setup](./database/README.md) — PostgreSQL schema, RLS, migrations, and seed instructions.
- [Demo fixtures](./sample_data/README.md) — offline customer-support records.

The repository currently includes the runtime foundation and Phase 2 persistence
work: SQLAlchemy entities, PostgreSQL schema/RLS/migrations, async repositories, and
an offline demo-data bootstrap. Later application phases remain planned until their
implementation and validation are confirmed.
