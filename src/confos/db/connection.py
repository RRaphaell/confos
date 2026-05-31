"""SQLite connection helpers and FTS5 capability check."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def connect(db_path: Path, *, create_parents: bool = True) -> sqlite3.Connection:
    """Open the confos database with sane pragmas and ``Row`` access.

    Foreign keys are enforced; rows come back as :class:`sqlite3.Row` so callers can
    index by column name.
    """
    if create_parents:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def fts5_available() -> bool:
    """Whether this Python's sqlite3 build includes FTS5 (A3).

    Checked against a throwaway in-memory database so it is independent of the store.
    """
    try:
        probe = sqlite3.connect(":memory:")
    except sqlite3.Error:
        return False
    try:
        probe.execute("CREATE VIRTUAL TABLE fts_probe USING fts5(x)")
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        probe.close()


def sqlite_version() -> str:
    """The runtime SQLite library version (for ``doctor``)."""
    return sqlite3.sqlite_version
