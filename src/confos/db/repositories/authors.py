"""Author repository. Identity is keyed on author_id (D5) — never merged by name."""

from __future__ import annotations

import sqlite3

from ...models import NormalizedAuthor


def upsert_author(conn: sqlite3.Connection, author: NormalizedAuthor) -> None:
    """Insert or refresh an author. Existing affiliation/profile are kept if the new
    record lacks them (COALESCE), so a later note can only *add* signal, not erase it."""
    conn.execute(
        """
        INSERT INTO authors (
            id, profile_id, display_name, aliases_json, affiliation_current,
            affiliation_country, data_quality, profile_url
        ) VALUES (?, ?, ?, '[]', ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            display_name=excluded.display_name,
            profile_id=COALESCE(excluded.profile_id, authors.profile_id),
            affiliation_current=COALESCE(excluded.affiliation_current, authors.affiliation_current),
            affiliation_country=COALESCE(excluded.affiliation_country, authors.affiliation_country),
            data_quality=excluded.data_quality,
            profile_url=COALESCE(excluded.profile_url, authors.profile_url)
        """,
        (
            author.author_id,
            author.profile_id,
            author.display_name,
            author.affiliation,
            author.country,
            author.data_quality,
            author.profile_url,
        ),
    )


def search_by_name(conn: sqlite3.Connection, name: str, *, limit: int = 25) -> list[sqlite3.Row]:
    """Case-insensitive substring search on display name, most-prolific first."""
    return conn.execute(
        """
        SELECT a.*,
               (SELECT COUNT(*) FROM paper_authors pa WHERE pa.author_id = a.id) AS paper_count
        FROM authors a
        WHERE LOWER(a.display_name) LIKE :pattern
        ORDER BY paper_count DESC, a.display_name ASC, a.id ASC
        LIMIT :limit
        """,
        {"pattern": f"%{name.lower()}%", "limit": limit},
    ).fetchall()


def get_with_stats(conn: sqlite3.Connection, author_id: str) -> sqlite3.Row | None:
    row: sqlite3.Row | None = conn.execute(
        """
        SELECT a.*,
               (SELECT COUNT(*) FROM paper_authors pa WHERE pa.author_id = a.id) AS paper_count
        FROM authors a WHERE a.id = ?
        """,
        (author_id,),
    ).fetchone()
    return row


def venues_for_author(conn: sqlite3.Connection, author_id: str) -> list[sqlite3.Row]:
    """Per-venue paper counts for an author (most papers first)."""
    return conn.execute(
        """
        SELECT p.venue_slug AS venue, COUNT(*) AS papers
        FROM paper_authors pa JOIN papers p ON p.id = pa.paper_id
        WHERE pa.author_id = ?
        GROUP BY p.venue_slug ORDER BY papers DESC, p.venue_slug ASC
        """,
        (author_id,),
    ).fetchall()
