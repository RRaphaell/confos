"""Schema application + incremental upgrades, gated by ``PRAGMA user_version``.

Two convergent paths, no Alembic:

* **Fresh store** (``user_version == 0``): apply the complete current schema from
  ``schema.sql`` in one shot and jump straight to :data:`SCHEMA_VERSION`. ``schema.sql``
  always reflects the latest shape, so a new store never replays the step ladder.
* **Existing store** (``1 <= user_version < SCHEMA_VERSION``): apply each ordered step in
  :data:`_MIGRATIONS` whose target version is newer than the store, then stamp
  ``user_version``. Steps are additive (``ALTER TABLE … ADD COLUMN`` /
  ``CREATE TABLE IF NOT EXISTS``) and idempotent, so a crash mid-upgrade re-applies cleanly.

Schema froze at v0.1.0 (D18); each enrichment phase that changes the schema appends a step
here and bumps :data:`SCHEMA_VERSION`. ``index rebuild`` reuses :func:`drop_derived` +
:func:`create_derived` to rebuild the FTS layer from raw JSONL without touching core tables.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from importlib.resources import files

from ..errors import ConfigError

# Bumped by each schema-changing phase. v2 = Phase 0 (pdf/bibtex/supplementary columns);
# v3 = Phase 1 (author profile-enrichment columns); v4 = Phase 2 (review aggregates + table).
SCHEMA_VERSION = 4

# Derived (rebuildable) FTS tables — dropped/recreated by `index rebuild`.
_DERIVED_TABLES = ("papers_fts", "authors_fts", "orgs_fts")

_Migration = Callable[[sqlite3.Connection], None]


def _add_columns(table: str, columns: list[tuple[str, str]]) -> _Migration:
    """Build an idempotent migration that adds missing columns to an existing table.

    SQLite has no ``ADD COLUMN IF NOT EXISTS``, so we diff against ``table_info`` and only
    add what's absent — making the step safe to re-run after a partially-applied upgrade.
    ``table``/column names are hard-coded literals (never user input), so the f-string DDL
    is injection-free.
    """

    def _apply(conn: sqlite3.Connection) -> None:
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, decl in columns:
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")

    return _apply


# Phase 2 reviews table (mirrors schema.sql; CREATE … IF NOT EXISTS keeps it idempotent).
_REVIEWS_TABLE = """
    CREATE TABLE IF NOT EXISTS reviews (
        paper_id        TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
        reviewer_key    TEXT NOT NULL,
        rating          INTEGER,
        confidence      INTEGER,
        sub_scores_json TEXT NOT NULL DEFAULT '{}',
        raw_rating      TEXT,
        PRIMARY KEY (paper_id, reviewer_key)
    )
"""


def _phase2_reviews(conn: sqlite3.Connection) -> None:
    """v4: review-aggregate columns on papers + the reviews table (additive, idempotent)."""
    _add_columns(
        "papers",
        [
            ("review_count", "INTEGER NOT NULL DEFAULT 0"),
            ("rating_mean", "REAL"),
            ("rating_std", "REAL"),
            ("confidence_mean", "REAL"),
            ("decision", "TEXT"),
        ],
    )(conn)
    conn.execute(_REVIEWS_TABLE)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_paper ON reviews(paper_id)")


# Ordered upgrade steps for EXISTING stores (a fresh store gets schema.sql directly and
# skips these). Each (target_version, step) runs when target_version > the store's version.
_MIGRATIONS: tuple[tuple[int, _Migration], ...] = (
    (
        2,  # Phase 0 — capture fields confos already downloads but used to drop.
        _add_columns(
            "papers",
            [("pdf_url", "TEXT"), ("bibtex", "TEXT"), ("supplementary_url", "TEXT")],
        ),
    ),
    (
        3,  # Phase 1 — author profile enrichment (homepage/scholar/dblp/expertise).
        _add_columns(
            "authors",
            [
                ("homepage", "TEXT"),
                ("gscholar", "TEXT"),
                ("dblp", "TEXT"),
                ("expertise_json", "TEXT NOT NULL DEFAULT '[]'"),
            ],
        ),
    ),
    (4, _phase2_reviews),  # Phase 2 — review aggregates on papers + the reviews table.
)


def _schema_sql() -> str:
    return files("confos.db").joinpath("schema.sql").read_text(encoding="utf-8")


def current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0])


def migrate(conn: sqlite3.Connection) -> bool:
    """Bring the store up to :data:`SCHEMA_VERSION`. Returns True if anything was applied.

    Raises :class:`ConfigError` if the store was created by a newer confos than this one
    (a forward-incompatible ``user_version``).
    """
    version = current_version(conn)
    if version > SCHEMA_VERSION:
        raise ConfigError(
            f"Store schema version {version} is newer than this confos supports "
            f"({SCHEMA_VERSION}).",
            hint="Upgrade confos, or remove the store and re-ingest.",
        )
    if version == SCHEMA_VERSION:
        return False
    if version == 0:
        conn.executescript(_schema_sql())  # full current schema → latest in one shot
    else:
        for target, apply in _MIGRATIONS:
            if target > version:
                apply(conn)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()
    return True


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
