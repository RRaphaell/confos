"""Typed SQL repositories — the only place that owns SQL strings (ARCHITECTURE §4).

Repositories take an open ``sqlite3.Connection`` and never open connections, make
network calls, or format output. The ingest service coordinates them inside a single
transaction so one paper's rows land atomically.
"""

from __future__ import annotations

from datetime import UTC, datetime


def now_iso() -> str:
    """Current UTC timestamp as ISO-8601 (used for created_at/updated_at/ingest times)."""
    return datetime.now(UTC).isoformat()
