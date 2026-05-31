"""Typed SQL repositories — the only place that owns SQL strings (ARCHITECTURE §4).

Repositories take an open ``sqlite3.Connection`` and never open connections, make
network calls, or format output. The ingest service coordinates them inside a single
transaction so one paper's rows land atomically.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

# Tables holding entities derived from raw JSONL (cleared on a full `index rebuild`).
# venues + ingest_runs are sync state and are NOT reset.
_ENTITY_TABLES = ("venues", "papers", "authors", "orgs", "paper_authors", "paper_topics")


def now_iso() -> str:
    """Current UTC timestamp as ISO-8601 (used for created_at/updated_at/ingest times)."""
    return datetime.now(UTC).isoformat()


def reset_entities(conn: sqlite3.Connection) -> None:
    """Delete derived entities for a full rebuild (cascades handle child rows)."""
    conn.execute("DELETE FROM papers")  # cascades paper_authors, paper_topics
    conn.execute("DELETE FROM authors")  # cascades author_affiliations
    conn.execute("DELETE FROM orgs")


def count_table(conn: sqlite3.Connection, table: str) -> int:
    """Row count for one of the known entity tables (table name is allow-listed)."""
    if table not in _ENTITY_TABLES:
        raise ValueError(f"unknown table {table!r}")
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
