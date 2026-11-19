# Autonomous-Customer-Support-Resolution-Platform

<!-- Written by Euron Code project setup. Run /init to let the model fill in the details. -->

Stack: Python, FastAPI, pytest, SQLAlchemy, LangChain

## Commands
- `pip install -e .`
- `python -m pytest`
- `make setup`
- `make test`
- `make lint`
- `make backend`
- `make ingest`

## Layout
```
agents/  (3 files)
backend/  (44 files)
database/  (7 files)
docs/  (5 files)
frontend/  (1 files)
integrations/  (5 files)
internal/  (32 files)
  design_evolution/
  explain_codebase/
  Infra_design_evolution/
  QnA/
memory/  (4 files)
rag/  (6 files)
sample_data/  (25 files)
src/  (0 files)
tests/  (32 files)
CLAUDE.md
Makefile
MEMORY.md
PLAN.md
PLAN_PHASE.md
pyproject.toml
README.md
TASK.md
```

Entry points: backend/app/main.py

## Conventions
- (add the conventions of this project here)
