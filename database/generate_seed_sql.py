from __future__ import annotations

import json
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
SAMPLE_DATA_DIR: Final = ROOT / "sample_data"
OUTPUT_PATH: Final = Path(__file__).resolve().parent / "seed.sql"

SEED_TABLES: Final = (
    (
        "profiles",
        "profiles.json",
        {
            "id": "VARCHAR(36)",
            "email": "VARCHAR(255)",
            "full_name": "VARCHAR(255)",
            "role": "VARCHAR(20)",
        },
    ),
    (
        "customers",
        "customers.json",
        {
            "id": "VARCHAR(36)",
            "name": "VARCHAR(255)",
            "email": "VARCHAR(255)",
            "company": "VARCHAR(255)",
            "plan": "VARCHAR(50)",
        },
    ),
    (
        "subscriptions",
        "subscriptions.json",
        {
            "id": "VARCHAR(36)",
            "customer_id": "VARCHAR(36)",
            "plan": "VARCHAR(50)",
            "status": "VARCHAR(50)",
            "seats": "INTEGER",
            "monthly_price": "DOUBLE PRECISION",
        },
    ),
    (
        "workspaces",
        "workspaces.json",
        {
            "id": "VARCHAR(36)",
            "customer_id": "VARCHAR(36)",
            "name": "VARCHAR(255)",
            "status": "VARCHAR(50)",
            "settings": "JSON",
        },
    ),
    (
        "products",
        "products.json",
        {
            "id": "VARCHAR(36)",
            "name": "VARCHAR(255)",
            "description": "TEXT",
            "metadata_json": "JSON",
        },
    ),
    (
        "incidents",
        "incidents.json",
        {
            "id": "VARCHAR(36)",
            "title": "VARCHAR(500)",
            "status": "VARCHAR(50)",
            "severity": "VARCHAR(20)",
            "details": "JSON",
        },
    ),
    (
        "tickets",
        "tickets.json",
        {
            "id": "VARCHAR(36)",
            "number": "VARCHAR(20)",
            "customer_id": "VARCHAR(36)",
            "workspace_id": "VARCHAR(36)",
            "subject": "VARCHAR(500)",
            "body": "TEXT",
            "channel": "VARCHAR(20)",
            "category": "VARCHAR(32)",
            "severity": "VARCHAR(20)",
            "status": "VARCHAR(30)",
        },
    ),
    (
        "ticket_messages",
        "ticket_messages.json",
        {
            "id": "VARCHAR(36)",
            "ticket_id": "VARCHAR(36)",
            "author_type": "VARCHAR(20)",
            "author_id": "VARCHAR(36)",
            "body": "TEXT",
        },
    ),
)


def render_seed_sql() -> str:
    statements = [
        "-- Generated from sample_data/*.json by database/generate_seed_sql.py.",
        "-- Re-run safely: demo records use stable IDs and conflict rows are skipped.",
        "BEGIN;",
    ]
    for table, filename, columns_and_types in SEED_TABLES:
        records = json.loads((SAMPLE_DATA_DIR / filename).read_text(encoding="utf-8"))
        columns = list(columns_and_types)
        column_list = ", ".join(columns)
        typed_columns = ", ".join(
            f"{column} {sql_type}" for column, sql_type in columns_and_types.items()
        )
        payload = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
        statements.extend(
            [
                f"INSERT INTO {table} ({column_list})",
                f"SELECT {column_list}",
                f"FROM json_to_recordset($seed${payload}$seed$) AS seed_rows({typed_columns})",
                "ON CONFLICT DO NOTHING;",
            ]
        )
    statements.append("COMMIT;")
    return "\n".join(statements) + "\n"


if __name__ == "__main__":
    OUTPUT_PATH.write_text(render_seed_sql(), encoding="utf-8")
