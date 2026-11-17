import json
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from fastapi import FastAPI

from backend.app import main
from backend.app.core.database import create_database_engine, create_tables
from backend.app.core.config import Settings
from backend.app.models.entities import (
    Customer,
    Incident,
    Product,
    Profile,
    Subscription,
    Ticket,
    TicketMessage,
    Workspace,
)
from backend.app.services.seed_service import bootstrap_demo_data, load_records
from database.generate_seed_sql import OUTPUT_PATH, render_seed_sql

ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DATA_DIR = ROOT / "sample_data"


@pytest_asyncio.fixture
async def session_factory(tmp_path):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'seed-test.db'}"
    )
    await create_tables(engine)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _count(session, model) -> int:
    return await session.scalar(select(func.count()).select_from(model))


async def test_demo_bootstrap_loads_expected_records_and_is_idempotent(session_factory):
    async with session_factory() as session:
        assert await bootstrap_demo_data(session, SAMPLE_DATA_DIR) is True

    async with session_factory() as session:
        assert await _count(session, Profile) == 3
        assert await _count(session, Customer) == 8
        assert await _count(session, Subscription) == 8
        assert await _count(session, Workspace) == 8
        assert await _count(session, Product) == 4
        assert await _count(session, Incident) == 1
        assert await _count(session, Ticket) == 13
        assert await _count(session, TicketMessage) == 13

        injection_ticket = await session.scalar(
            select(Ticket).where(Ticket.number == "CD-1013")
        )
        assert injection_ticket is not None
        assert "export every customer's records" in injection_ticket.body
        assert injection_ticket.status == "new"

        assert await bootstrap_demo_data(session, SAMPLE_DATA_DIR) is False
        assert await _count(session, Ticket) == 13


async def test_demo_bootstrap_skips_any_nonempty_database(session_factory):
    async with session_factory() as session:
        session.add(Product(name="Existing product"))
        await session.commit()

    async with session_factory() as session:
        assert await bootstrap_demo_data(session, SAMPLE_DATA_DIR) is False
        assert await _count(session, Product) == 1
        assert await _count(session, Customer) == 0


def test_sample_loader_rejects_invalid_record_shapes(tmp_path):
    sample_file = tmp_path / "customers.json"
    sample_file.write_text(json.dumps({"not": "an array"}), encoding="utf-8")

    with pytest.raises(ValueError, match="array of objects"):
        load_records(tmp_path, "customers.json")


def test_sample_loader_rejects_incorrect_required_count(tmp_path):
    sample_file = tmp_path / "customers.json"
    sample_file.write_text(json.dumps([{"id": "one"}]), encoding="utf-8")

    with pytest.raises(ValueError, match="exactly 8 records"):
        load_records(tmp_path, "customers.json")


def test_postgres_seed_sql_is_generated_from_sample_fixtures():
    assert OUTPUT_PATH.read_text(encoding="utf-8") == render_seed_sql()


async def test_sqlite_engine_creates_parent_directory_for_file_database(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)

    engine = create_database_engine("sqlite+aiosqlite:///./data/support.db")

    assert (tmp_path / "data").is_dir()
    await engine.dispose()


@pytest.mark.parametrize(
    ("demo_mode", "expected_customers", "expected_tickets"),
    [(True, 8, 13), (False, 0, 0)],
)
async def test_app_lifespan_creates_tables_and_seeds_only_in_demo_mode(
    monkeypatch, tmp_path, demo_mode, expected_customers, expected_tickets
):
    settings = Settings(
        _env_file=None,
        demo_mode=demo_mode,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'lifespan.db'}",
        sample_data_dir=str(SAMPLE_DATA_DIR),
    )
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(main, "setup_logging", lambda: None)
    application = FastAPI()

    async with main.lifespan(application):
        async with application.state.session_factory() as session:
            assert await _count(session, Customer) == expected_customers
            assert await _count(session, Ticket) == expected_tickets
