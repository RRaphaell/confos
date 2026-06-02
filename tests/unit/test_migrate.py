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
    "reviews",
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
        # A fresh store (schema.sql path) must end with the SAME columns the incremental
        # _MIGRATIONS ladder produces — locks schema.sql/migration parity (D22).
        cols = {row[1] for row in conn.execute("PRAGMA table_info(papers)")}
        assert {"pdf_url", "bibtex", "supplementary_url"} <= cols
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


# Minimal stand-ins for a real v0.1.0 (v1) store's tables that the incremental steps
# ALTER — enough for the migration ladder to run without the full schema.
_V1_TABLES = (
    "CREATE TABLE papers (id TEXT PRIMARY KEY, title TEXT)",
    "CREATE TABLE authors (id TEXT PRIMARY KEY, display_name TEXT)",
)


def test_incremental_upgrade_v1_to_latest_adds_columns(tmp_path: Path) -> None:
    # An existing v0.1.0 store (user_version=1, no enrichment columns) must upgrade in
    # place: apply every additive ALTER step and stamp the latest version — no re-init.
    conn = connect(tmp_path / "confos.db")
    try:
        for ddl in _V1_TABLES:
            conn.execute(ddl)
        conn.execute("PRAGMA user_version = 1")
        conn.commit()
        assert current_version(conn) == 1
        assert migrate(conn) is True
        assert current_version(conn) == SCHEMA_VERSION
        paper_cols = {row[1] for row in conn.execute("PRAGMA table_info(papers)")}
        assert {"pdf_url", "bibtex", "supplementary_url"} <= paper_cols  # v2
        assert {"review_count", "rating_mean", "rating_std", "decision"} <= paper_cols  # v4
        author_cols = {row[1] for row in conn.execute("PRAGMA table_info(authors)")}
        assert {"homepage", "gscholar", "dblp", "expertise_json"} <= author_cols  # v3
        assert "reviews" in _table_names(conn)  # v4 reviews table created
        assert migrate(conn) is False  # idempotent once caught up
    finally:
        conn.close()


def test_reviews_schema_parity_fresh_vs_migrated(tmp_path: Path) -> None:
    # schema.sql (fresh) and the migrate.py reviews DDL (existing-store upgrade) must agree —
    # else a fresh store and a migrated one diverge. Guards the duplicated reviews table DDL.
    fresh = connect(tmp_path / "fresh.db")
    migrated = connect(tmp_path / "migrated.db")
    try:
        migrate(fresh)
        for ddl in _V1_TABLES:
            migrated.execute(ddl)
        migrated.execute("PRAGMA user_version = 1")
        migrated.commit()
        migrate(migrated)

        def cols(conn: object, table: str) -> set[str]:
            return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}  # type: ignore[attr-defined]

        assert cols(fresh, "reviews") == cols(migrated, "reviews")
        assert {"review_count", "rating_mean", "rating_std", "confidence_mean", "decision"} <= cols(
            fresh, "papers"
        )
    finally:
        fresh.close()
        migrated.close()


def test_incremental_upgrade_is_crash_safe(tmp_path: Path) -> None:
    # Simulate a crash mid-upgrade: one column already added, version still 1. Re-running
    # must add only the missing columns (no "duplicate column name" error).
    conn = connect(tmp_path / "confos.db")
    try:
        for ddl in _V1_TABLES:
            conn.execute(ddl)
        conn.execute("ALTER TABLE papers ADD COLUMN pdf_url TEXT")
        conn.execute("PRAGMA user_version = 1")
        conn.commit()
        assert migrate(conn) is True
        paper_cols = {row[1] for row in conn.execute("PRAGMA table_info(papers)")}
        assert {"pdf_url", "bibtex", "supplementary_url"} <= paper_cols
        author_cols = {row[1] for row in conn.execute("PRAGMA table_info(authors)")}
        assert {"homepage", "gscholar", "dblp", "expertise_json"} <= author_cols
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
