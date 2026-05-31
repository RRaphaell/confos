"""Venue + ingest-run repository."""

from __future__ import annotations

import sqlite3

from ...models import VenueRef
from . import now_iso


def upsert_venue(conn: sqlite3.Connection, ref: VenueRef, *, last_ingested_at: str | None) -> None:
    """Insert or refresh a venue's metadata."""
    conn.execute(
        """
        INSERT INTO venues (
            slug, source, source_venue_id, published_venueid, submission_venueid,
            withdrawn_venueid, desk_rejected_venueid, submission_name, display_name,
            year, url, last_ingested_at
        ) VALUES (
            :slug, :source, :source_venue_id, :published_venueid, :submission_venueid,
            :withdrawn_venueid, :desk_rejected_venueid, :submission_name, :display_name,
            :year, :url, :last_ingested_at
        )
        ON CONFLICT(slug) DO UPDATE SET
            source=excluded.source,
            source_venue_id=excluded.source_venue_id,
            published_venueid=excluded.published_venueid,
            submission_venueid=excluded.submission_venueid,
            withdrawn_venueid=excluded.withdrawn_venueid,
            desk_rejected_venueid=excluded.desk_rejected_venueid,
            submission_name=excluded.submission_name,
            display_name=excluded.display_name,
            year=excluded.year,
            url=excluded.url,
            last_ingested_at=COALESCE(excluded.last_ingested_at, venues.last_ingested_at)
        """,
        {
            "slug": ref.slug,
            "source": ref.source,
            "source_venue_id": ref.source_venue_id,
            "published_venueid": ref.published_venueid,
            "submission_venueid": ref.submission_venueid,
            "withdrawn_venueid": ref.withdrawn_venueid,
            "desk_rejected_venueid": ref.desk_rejected_venueid,
            "submission_name": ref.submission_name,
            "display_name": ref.display_name,
            "year": ref.year,
            "url": ref.url,
            "last_ingested_at": last_ingested_at,
        },
    )


def register_venue(
    conn: sqlite3.Connection, slug: str, source_venue_id: str, *, source: str = "openreview"
) -> None:
    """Register a custom slug → source id mapping (``venues add``); not yet ingested."""
    conn.execute(
        """
        INSERT INTO venues (slug, source, source_venue_id) VALUES (?, ?, ?)
        ON CONFLICT(slug) DO UPDATE SET
            source=excluded.source, source_venue_id=excluded.source_venue_id
        """,
        (slug, source, source_venue_id),
    )


def get_venue(conn: sqlite3.Connection, slug: str) -> sqlite3.Row | None:
    row: sqlite3.Row | None = conn.execute(
        "SELECT * FROM venues WHERE slug = ?", (slug,)
    ).fetchone()
    return row


def list_venues(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT v.*, (SELECT COUNT(*) FROM papers p WHERE p.venue_slug = v.slug) AS paper_count
        FROM venues v ORDER BY v.slug
        """
    ).fetchall()


def latest_watermark(conn: sqlite3.Connection, slug: str) -> tuple[int | None, int | None]:
    """Most recent (max_tcdate, max_tmdate) from a successful/partial run for the venue."""
    row = conn.execute(
        """
        SELECT max_tcdate, max_tmdate FROM ingest_runs
        WHERE venue_slug = ? AND status IN ('ok', 'partial')
        ORDER BY id DESC LIMIT 1
        """,
        (slug,),
    ).fetchone()
    if row is None:
        return None, None
    return row["max_tcdate"], row["max_tmdate"]


def insert_ingest_run(
    conn: sqlite3.Connection,
    *,
    venue_slug: str,
    status: str,
    started_at: str,
    finished_at: str | None,
    items_seen: int,
    items_added: int,
    items_updated: int,
    max_tcdate: int | None,
    max_tmdate: int | None,
    error: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO ingest_runs (
            venue_slug, status, started_at, finished_at, items_seen, items_added,
            items_updated, max_tcdate, max_tmdate, error
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            venue_slug,
            status,
            started_at,
            finished_at or now_iso(),
            items_seen,
            items_added,
            items_updated,
            max_tcdate,
            max_tmdate,
            error,
        ),
    )
