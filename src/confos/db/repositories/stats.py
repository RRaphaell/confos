"""Aggregation queries for ``stats`` (counts + coverage, scoped to an optional venue).

These power honest stats: every aggregate is paired with how many papers actually
carried the signal (keywords / affiliation / country), so the service can report
known/unknown without faking clean numbers (PRODUCT principle #4).
"""

from __future__ import annotations

import sqlite3


def _scope(venue: str | None) -> tuple[str, dict[str, object]]:
    """Return an extra WHERE fragment (joined with AND) + params for a venue filter."""
    if venue is None:
        return "", {}
    return "p.venue_slug = :venue", {"venue": venue}


def papers_total(conn: sqlite3.Connection, venue: str | None = None) -> int:
    clause, params = _scope(venue)
    where = f"WHERE {clause}" if clause else ""
    return int(conn.execute(f"SELECT COUNT(*) FROM papers p {where}", params).fetchone()[0])


def status_counts(conn: sqlite3.Connection, venue: str | None = None) -> list[sqlite3.Row]:
    clause, params = _scope(venue)
    where = f"WHERE {clause}" if clause else ""
    return conn.execute(
        f"SELECT p.status AS key, COUNT(*) AS papers FROM papers p {where} "
        "GROUP BY p.status ORDER BY papers DESC, key ASC",
        params,
    ).fetchall()


def distinct_entity_counts(conn: sqlite3.Connection, venue: str | None = None) -> dict[str, int]:
    clause, params = _scope(venue)
    where = f"WHERE {clause}" if clause else ""
    join_where = f"WHERE {clause}" if clause else ""
    authors = conn.execute(
        f"SELECT COUNT(DISTINCT pa.author_id) FROM paper_authors pa "
        f"JOIN papers p ON p.id = pa.paper_id {join_where}",
        params,
    ).fetchone()[0]
    topics = conn.execute(
        f"SELECT COUNT(DISTINCT pt.topic) FROM paper_topics pt "
        f"JOIN papers p ON p.id = pt.paper_id {join_where}",
        params,
    ).fetchone()[0]
    venues = conn.execute(
        f"SELECT COUNT(DISTINCT p.venue_slug) FROM papers p {where}", params
    ).fetchone()[0]
    orgs = conn.execute(
        f"SELECT COUNT(DISTINCT aa.org_id) FROM author_affiliations aa "
        f"JOIN paper_authors pa ON pa.author_id = aa.author_id "
        f"JOIN papers p ON p.id = pa.paper_id {join_where}",
        params,
    ).fetchone()[0]
    return {
        "authors": int(authors),
        "topics": int(topics),
        "venues": int(venues),
        "orgs": int(orgs),
    }


def topic_counts(
    conn: sqlite3.Connection, venue: str | None = None, *, limit: int = 50
) -> list[sqlite3.Row]:
    clause, params = _scope(venue)
    where = f"WHERE {clause}" if clause else ""
    params = {**params, "limit": limit}
    return conn.execute(
        f"SELECT pt.topic AS key, COUNT(DISTINCT pt.paper_id) AS papers "
        f"FROM paper_topics pt JOIN papers p ON p.id = pt.paper_id {where} "
        "GROUP BY pt.topic ORDER BY papers DESC, key ASC LIMIT :limit",
        params,
    ).fetchall()


def topic_counts_for_papers(conn: sqlite3.Connection, paper_ids: list[str]) -> list[sqlite3.Row]:
    """Per-topic matched-paper counts over a specific set of papers (for thin_areas)."""
    if not paper_ids:
        return []
    placeholders = ",".join("?" * len(paper_ids))
    return conn.execute(
        f"SELECT topic AS key, COUNT(*) AS papers FROM paper_topics "
        f"WHERE paper_id IN ({placeholders}) GROUP BY topic ORDER BY papers ASC, topic ASC",
        paper_ids,
    ).fetchall()


def papers_with_keywords(conn: sqlite3.Connection, venue: str | None = None) -> int:
    clause, params = _scope(venue)
    where = f"WHERE {clause}" if clause else ""
    return int(
        conn.execute(
            f"SELECT COUNT(DISTINCT pt.paper_id) FROM paper_topics pt "
            f"JOIN papers p ON p.id = pt.paper_id {where}",
            params,
        ).fetchone()[0]
    )


def org_counts(
    conn: sqlite3.Connection, venue: str | None = None, *, limit: int = 50
) -> list[sqlite3.Row]:
    clause, params = _scope(venue)
    where = f"WHERE {clause}" if clause else ""
    params = {**params, "limit": limit}
    return conn.execute(
        "SELECT o.name AS key, COUNT(DISTINCT p.id) AS papers "
        "FROM orgs o JOIN author_affiliations aa ON aa.org_id = o.id "
        "JOIN paper_authors pa ON pa.author_id = aa.author_id "
        f"JOIN papers p ON p.id = pa.paper_id {where} "
        "GROUP BY o.id ORDER BY papers DESC, key ASC LIMIT :limit",
        params,
    ).fetchall()


def country_counts(
    conn: sqlite3.Connection, venue: str | None = None, *, limit: int = 50
) -> list[sqlite3.Row]:
    clause, params = _scope(venue)
    extra = f"AND {clause}" if clause else ""
    params = {**params, "limit": limit}
    return conn.execute(
        "SELECT o.country AS key, COUNT(DISTINCT p.id) AS papers "
        "FROM orgs o JOIN author_affiliations aa ON aa.org_id = o.id "
        "JOIN paper_authors pa ON pa.author_id = aa.author_id "
        f"JOIN papers p ON p.id = pa.paper_id WHERE o.country IS NOT NULL {extra} "
        "GROUP BY o.country ORDER BY papers DESC, key ASC LIMIT :limit",
        params,
    ).fetchall()


def papers_with_affiliation(conn: sqlite3.Connection, venue: str | None = None) -> int:
    clause, params = _scope(venue)
    where = f"WHERE {clause}" if clause else ""
    return int(
        conn.execute(
            "SELECT COUNT(DISTINCT p.id) FROM papers p "
            "JOIN paper_authors pa ON pa.paper_id = p.id "
            f"JOIN author_affiliations aa ON aa.author_id = pa.author_id {where}",
            params,
        ).fetchone()[0]
    )


def papers_with_country(conn: sqlite3.Connection, venue: str | None = None) -> int:
    clause, params = _scope(venue)
    extra = f"AND {clause}" if clause else ""
    return int(
        conn.execute(
            "SELECT COUNT(DISTINCT p.id) FROM papers p "
            "JOIN paper_authors pa ON pa.paper_id = p.id "
            "JOIN author_affiliations aa ON aa.author_id = pa.author_id "
            f"JOIN orgs o ON o.id = aa.org_id WHERE o.country IS NOT NULL {extra}",
            params,
        ).fetchone()[0]
    )
