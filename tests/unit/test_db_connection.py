"""DB connection pragmas — WAL for concurrent readers/writer on the shared store (P1-10)."""

from __future__ import annotations

from pathlib import Path

from confos.db.connection import connect


def test_connect_enables_wal(tmp_path: Path) -> None:
    # The store is meant to be read by parallel agents while a writer ingests, so it must
    # open in WAL mode (rollback-journal mode blocks readers behind the writer).
    conn = connect(tmp_path / "store.db")
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()
