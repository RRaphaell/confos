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
