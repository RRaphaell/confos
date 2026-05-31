"""Schema migration: apply-once, idempotent, derived-table rebuild (ARCHITECTURE §6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from confos.db.connection import connect
from confos.db.migrate import (
    SCHEMA_VERSION,
    create_derived,
    current_version,
    drop_derived,
    migrate,
)
from confos.errors import ConfigError

CORE_TABLES = {
    "venues",
    "papers",
    "authors",
    "paper_authors",
    "orgs",
    "author_affiliations",
    "paper_topics",
    "ingest_runs",
}
FTS_TABLES = {"papers_fts", "authors_fts", "orgs_fts"}


def _table_names(conn: object) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()  # type: ignore[attr-defined]
    return {r[0] for r in rows}


def test_migrate_applies_then_idempotent(tmp_path: Path) -> None:
    conn = connect(tmp_path / "confos.db")
    try:
        assert current_version(conn) == 0
        assert migrate(conn) is True
        assert current_version(conn) == SCHEMA_VERSION
        # idempotent: re-running does nothing.
        assert migrate(conn) is False
        names = _table_names(conn)
        assert CORE_TABLES.issubset(names)
        assert FTS_TABLES.issubset(names)
    finally:
        conn.close()


def test_migrate_recovers_from_partial_apply(tmp_path: Path) -> None:
    # Simulate an interrupted prior apply: tables exist but user_version is still 0.
    # IF NOT EXISTS must let a re-run complete cleanly (D13 idempotency).
    conn = connect(tmp_path / "confos.db")
    try:
        migrate(conn)
        conn.execute("PRAGMA user_version = 0")
        conn.commit()
        assert migrate(conn) is True
        assert current_version(conn) == SCHEMA_VERSION
    finally:
        conn.close()


def test_future_schema_version_rejected(tmp_path: Path) -> None:
    conn = connect(tmp_path / "confos.db")
    try:
        migrate(conn)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
        with pytest.raises(ConfigError):
            migrate(conn)
    finally:
        conn.close()


def test_drop_and_recreate_derived(tmp_path: Path) -> None:
    conn = connect(tmp_path / "confos.db")
    try:
        migrate(conn)
        drop_derived(conn)
        assert not (FTS_TABLES & _table_names(conn))
        create_derived(conn)
        assert FTS_TABLES.issubset(_table_names(conn))
    finally:
        conn.close()
