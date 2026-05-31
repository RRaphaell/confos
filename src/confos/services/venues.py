"""Venue operations: local list/show/add (offline) + network search."""

from __future__ import annotations

import sqlite3
from typing import Any

from ..adapters.openreview import BUILTIN_VENUE_ALIASES, OpenReviewAdapter
from ..db.connection import connect
from ..db.migrate import migrate
from ..db.repositories import venues as venues_repo
from ..errors import UsageError
from ..paths import Paths

_VENUE_FIELDS = (
    "slug",
    "source",
    "source_venue_id",
    "display_name",
    "year",
    "submission_name",
    "last_ingested_at",
    "paper_count",
)


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    keys = row.keys()
    return {field: (row[field] if field in keys else None) for field in _VENUE_FIELDS}


def list_local_venues(paths: Paths) -> list[dict[str, Any]]:
    """All locally-known venues (ingested or registered), offline."""
    paths.ensure()
    conn = connect(paths.db)
    try:
        migrate(conn)
        return [_row_to_dict(row) for row in venues_repo.list_venues(conn)]
    finally:
        conn.close()


def get_local_venue(paths: Paths, slug: str) -> dict[str, Any] | None:
    paths.ensure()
    conn = connect(paths.db)
    try:
        migrate(conn)
        row = venues_repo.list_venues(conn)
        match = next((r for r in row if r["slug"] == slug), None)
        return _row_to_dict(match) if match is not None else None
    finally:
        conn.close()


def add_local_venue(paths: Paths, slug: str, source_venue_id: str) -> dict[str, Any]:
    """Register a custom slug → OpenReview id mapping (local-write)."""
    if "/" not in source_venue_id:
        raise UsageError(
            f"'{source_venue_id}' doesn't look like an OpenReview venue id.",
            hint="Expected something like NeurIPS.cc/2025/Conference.",
        )
    paths.ensure()
    conn = connect(paths.db)
    try:
        migrate(conn)
        existing = venues_repo.get_venue(conn, slug)
        if (
            existing is not None
            and existing["last_ingested_at"]
            and existing["source_venue_id"] != source_venue_id
        ):
            raise UsageError(
                f"Venue '{slug}' is already ingested as {existing['source_venue_id']}; "
                "remapping it would orphan its papers.",
                hint="Pick a different slug, or remove the store and re-ingest.",
            )
        with conn:
            venues_repo.register_venue(conn, slug, source_venue_id)
    finally:
        conn.close()
    result = get_local_venue(paths, slug)
    assert result is not None  # we just registered it
    return result


def search_venues(
    adapter: OpenReviewAdapter, query: str, *, limit: int = 25
) -> list[dict[str, str]]:
    """Find venues matching a query (network)."""
    return adapter.search_venues(query, limit=limit)


def builtin_aliases() -> dict[str, str]:
    """The built-in venue alias map (offline)."""
    return dict(BUILTIN_VENUE_ALIASES)
