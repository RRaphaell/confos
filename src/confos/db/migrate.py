"""Schema application, gated by ``PRAGMA user_version`` (apply-once, no Alembic).

The full v1 schema lives in ``schema.sql`` and is applied exactly once. We bump
``user_version`` to :data:`SCHEMA_VERSION` afterward so re-opening an initialised
store is a no-op. ``index rebuild`` (a later phase) reuses :func:`drop_derived` +
:func:`create_derived` to rebuild the FTS layer from raw JSONL without touching the
core tables.
"""

from __future__ import annotations

import sqlite3
from importlib.resources import files

from ..errors import ConfigError

SCHEMA_VERSION = 1

# Derived (rebuildable) FTS tables — dropped/recreated by `index rebuild`.
_DERIVED_TABLES = ("papers_fts", "authors_fts", "orgs_fts")


def _schema_sql() -> str:
    return files("confos.db").joinpath("schema.sql").read_text(encoding="utf-8")


def current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0])


def migrate(conn: sqlite3.Connection) -> bool:
    """Apply the schema if the database is fresh. Returns True if it applied.

    Raises :class:`ConfigError` if the store was created by a newer confos than this
    one (a forward-incompatible ``user_version``).
    """
    version = current_version(conn)
    if version == SCHEMA_VERSION:
        return False
    if version == 0:
        conn.executescript(_schema_sql())
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
        return True
    raise ConfigError(
        f"Store schema version {version} is newer than this confos supports ({SCHEMA_VERSION}).",
        hint="Upgrade confos, or remove the store and re-ingest.",
    )


def drop_derived(conn: sqlite3.Connection) -> None:
    """Drop the FTS5 tables (used by ``index rebuild`` before repopulating).

    Does not commit — the caller owns the surrounding transaction so a rebuild is
    atomic (it must not leave the FTS tables dropped if a later step fails).
    """
    for table in _DERIVED_TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {table}")


def create_derived(conn: sqlite3.Connection) -> None:
    """Recreate the FTS5 tables from the schema's CREATE VIRTUAL TABLE statements.

    Does not commit — the caller owns the transaction.
    """
    for stmt in _virtual_table_statements(_schema_sql()):
        conn.execute(stmt)


def _virtual_table_statements(sql: str) -> list[str]:
    """Extract the ``CREATE VIRTUAL TABLE`` statements from schema.sql.

    Each ``;``-delimited chunk may carry a leading section comment, so we slice from
    the ``CREATE VIRTUAL TABLE`` keyword rather than requiring the chunk to start with
    it.
    """
    statements: list[str] = []
    for raw in sql.split(";"):
        idx = raw.upper().find("CREATE VIRTUAL TABLE")
        if idx != -1:
            statements.append(raw[idx:].strip())
    return statements
