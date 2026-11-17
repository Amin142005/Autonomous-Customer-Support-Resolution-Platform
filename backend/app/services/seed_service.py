from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import (
    Base,
    Customer,
    Incident,
    Product,
    Profile,
    Subscription,
    Ticket,
    TicketMessage,
    Workspace,
)

SEED_FILES: tuple[tuple[type[Base], str], ...] = (
    (Profile, "profiles.json"),
    (Customer, "customers.json"),
    (Subscription, "subscriptions.json"),
    (Workspace, "workspaces.json"),
    (Product, "products.json"),
    (Incident, "incidents.json"),
    (Ticket, "tickets.json"),
    (TicketMessage, "ticket_messages.json"),
)
EXPECTED_COUNTS = {"customers.json": 8, "tickets.json": 13}


def load_records(sample_data_dir: str | Path, filename: str) -> list[dict[str, Any]]:
    path = Path(sample_data_dir) / filename
    try:
        records = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in {path} at line {exc.lineno}, column {exc.colno}"
        ) from exc

    if not isinstance(records, list) or not all(
        isinstance(record, dict) for record in records
    ):
        raise ValueError(f"{path} must contain a JSON array of objects")
    expected_count = EXPECTED_COUNTS.get(filename)
    if expected_count is not None and len(records) != expected_count:
        raise ValueError(
            f"{path} must contain exactly {expected_count} records; got {len(records)}"
        )
    if not records:
        raise ValueError(f"{path} must contain at least one record")
    return records


async def _database_is_empty(session: AsyncSession) -> bool:
    for table in Base.metadata.sorted_tables:
        primary_key = next(iter(table.primary_key.columns))
        existing_id = await session.scalar(select(primary_key).limit(1))
        if existing_id is not None:
            return False
    return True


async def bootstrap_demo_data(
    session: AsyncSession, sample_data_dir: str | Path
) -> bool:
    transaction = (
        session.begin_nested() if session.in_transaction() else session.begin()
    )
    async with transaction:
        if not await _database_is_empty(session):
            return False

        dataset = [
            (model, load_records(sample_data_dir, filename))
            for model, filename in SEED_FILES
        ]
        for model, records in dataset:
            session.add_all(model(**record) for record in records)
            await session.flush()
    return True
