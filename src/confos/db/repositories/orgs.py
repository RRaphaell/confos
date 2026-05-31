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


def top(
    conn: sqlite3.Connection, *, venue: str | None = None, limit: int = 50
) -> list[sqlite3.Row]:
    """Organisations ranked by distinct paper count (sparse until Phase 3 enriches)."""
    clauses = []
    params: dict[str, object] = {"limit": limit}
    if venue is not None:
        clauses.append("p.venue_slug = :venue")
        params["venue"] = venue
    where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
    return conn.execute(
        "SELECT o.id, o.name, o.country, COUNT(DISTINCT p.id) AS papers "
        "FROM orgs o "
        "JOIN author_affiliations aa ON aa.org_id = o.id "
        "JOIN paper_authors pa ON pa.author_id = aa.author_id "
        "JOIN papers p ON p.id = pa.paper_id "
        f"{where}"
        "GROUP BY o.id ORDER BY papers DESC, o.name ASC, o.id ASC LIMIT :limit",
        params,
    ).fetchall()


def find_by_name(conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    """Resolve an org by display name (matched on its normalized-name slug)."""
    org_id = org_slug(name)
    row: sqlite3.Row | None = conn.execute("SELECT * FROM orgs WHERE id = ?", (org_id,)).fetchone()
    return row
