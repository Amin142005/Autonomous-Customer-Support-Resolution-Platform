.DEFAULT_GOAL := test

ifeq ($(OS),Windows_NT)
VENV_PYTHON := .venv/Scripts/python.exe
PYTHONPATH := backend;.
else
VENV_PYTHON := .venv/bin/python
PYTHONPATH := backend:.
endif

PYTHON ?= $(VENV_PYTHON)
BOOTSTRAP_PYTHON ?= python

export PYTHONPATH

.PHONY: setup test lint backend ingest demo

setup:
	$(BOOTSTRAP_PYTHON) -m venv .venv
	$(PYTHON) -m ensurepip --upgrade
	$(PYTHON) -m pip install -e ".[dev]"
	$(PYTHON) -c "from pathlib import Path; env = Path('.env'); env.exists() or env.write_text(Path('.env.example').read_text(encoding='utf-8'), encoding='utf-8')"

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check --select E4,E7,E9,F backend tests

backend:
	$(PYTHON) -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

ingest:
	$(PYTHON) -m backend.app.cli.ingest_knowledge

demo:
	$(PYTHON) -m backend.app.cli.demo
