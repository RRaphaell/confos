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


def list_for_export(conn: sqlite3.Connection, venue: str | None = None) -> list[sqlite3.Row]:
    """All authors (optionally scoped to a venue's papers), ordered by id — bulk export."""
    if venue is None:
        return conn.execute("SELECT * FROM authors ORDER BY id").fetchall()
    return conn.execute(
        "SELECT DISTINCT a.* FROM authors a "
        "JOIN paper_authors pa ON pa.author_id = a.id "
        "JOIN papers p ON p.id = pa.paper_id WHERE p.venue_slug = ? ORDER BY a.id",
        (venue,),
    ).fetchall()


def get_many(conn: sqlite3.Connection, author_ids: list[str]) -> dict[str, sqlite3.Row]:
    """Fetch author rows for a set of ids, keyed by id (for ranking)."""
    if not author_ids:
        return {}
    placeholders = ",".join("?" * len(author_ids))
    rows = conn.execute(
        f"SELECT * FROM authors WHERE id IN ({placeholders})", author_ids
    ).fetchall()
    return {row["id"]: row for row in rows}


def coauthors(conn: sqlite3.Connection, author_id: str, *, limit: int = 50) -> list[sqlite3.Row]:
    """Co-authors ranked by number of shared papers (deterministic tiebreak by id)."""
    return conn.execute(
        """
        SELECT a.*, COUNT(*) AS shared_papers
        FROM paper_authors mine
        JOIN paper_authors theirs ON theirs.paper_id = mine.paper_id
        JOIN authors a ON a.id = theirs.author_id
        WHERE mine.author_id = :author_id AND theirs.author_id != :author_id
        GROUP BY a.id
        ORDER BY shared_papers DESC, a.display_name ASC, a.id ASC
        LIMIT :limit
        """,
        {"author_id": author_id, "limit": limit},
    ).fetchall()


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
