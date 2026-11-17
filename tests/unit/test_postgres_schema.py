import re
from pathlib import Path

from backend.app.models.entities import Base


ROOT = Path(__file__).resolve().parents[2]
DATABASE_DIR = ROOT / "database"
TABLE_PATTERN = re.compile(r"CREATE TABLE\s+([a-z_]+)", re.IGNORECASE)


def _created_tables(sql: str) -> set[str]:
    return {match.lower() for match in TABLE_PATTERN.findall(sql)}


def test_schema_and_initial_migration_cover_all_entities():
    entity_tables = set(Base.metadata.tables)
    schema = (DATABASE_DIR / "schema.sql").read_text(encoding="utf-8")
    initial_migration = (
        DATABASE_DIR / "migrations" / "0001_initial_schema.sql"
    ).read_text(encoding="utf-8")

    assert _created_tables(schema) == entity_tables
    assert _created_tables(initial_migration) == entity_tables
    assert "JSONB" not in schema.upper()


def test_every_entity_has_updated_at_and_trigger():
    schema = (DATABASE_DIR / "schema.sql").read_text(encoding="utf-8")

    assert all("updated_at" in table.columns for table in Base.metadata.tables.values())
    for table_name in Base.metadata.tables:
        assert f"CREATE TRIGGER {table_name}_set_updated_at" in schema


def test_rls_and_read_policies_cover_all_entities_without_client_writes():
    tables = set(Base.metadata.tables)
    policy_sql = (DATABASE_DIR / "rls_policies.sql").read_text(encoding="utf-8")
    migration_sql = (
        DATABASE_DIR / "migrations" / "0002_enable_rls.sql"
    ).read_text(encoding="utf-8")

    for table_name in tables:
        assert f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY" in policy_sql
        assert f"CREATE POLICY {table_name}_read" in policy_sql
    assert "REVOKE ALL ON TABLE" in policy_sql
    assert "GRANT SELECT ON TABLE" in policy_sql
    assert "GRANT ALL ON TABLE" in policy_sql
    assert _created_tables(migration_sql) == set()


def test_migrations_are_ordered_and_non_destructive():
    migrations = sorted((DATABASE_DIR / "migrations").glob("*.sql"))

    assert [path.name for path in migrations] == [
        "0001_initial_schema.sql",
        "0002_enable_rls.sql",
    ]
    for migration in migrations:
        sql = migration.read_text(encoding="utf-8")
        assert not re.search(r"\bDROP\s+(TABLE|COLUMN|SCHEMA)\b", sql, re.IGNORECASE)
