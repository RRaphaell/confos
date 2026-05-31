"""Organisation repository (best-effort in v1; enriched in Phase 3)."""

from __future__ import annotations

import sqlite3

from ...normalize.orgs import org_slug


def upsert_org(conn: sqlite3.Connection, name: str, country: str | None) -> str:
    """Insert or refresh an org by its normalized-name slug; returns the org id."""
    org_id = org_slug(name)
    conn.execute(
        """
        INSERT INTO orgs (id, name, normalized_name, country, aliases_json)
        VALUES (?, ?, ?, ?, '[]')
        ON CONFLICT(id) DO UPDATE SET country=COALESCE(orgs.country, excluded.country)
        """,
        (org_id, name, name.lower(), country),
    )
    return org_id


def link_affiliation(
    conn: sqlite3.Connection, author_id: str, org_id: str, *, confidence: str
) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO author_affiliations (author_id, org_id, confidence)
        VALUES (?, ?, ?)
        """,
        (author_id, org_id, confidence),
    )
