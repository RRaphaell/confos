"""Paper repository: the papers row plus its author links, topics, and FTS row.

``upsert_paper`` writes everything that is keyed by ``paper_id`` so a re-ingest of the
same note fully refreshes it (child rows are replaced, not accumulated). Authors must be
upserted into ``authors`` first (the service does this) so the FK holds.
"""

from __future__ import annotations

import sqlite3

from ...models import NormalizedPaper
from . import now_iso


def upsert_paper(conn: sqlite3.Connection, paper: NormalizedPaper) -> bool:
    """Insert or update a paper and its child rows. Returns True if newly inserted."""
    existing = conn.execute("SELECT 1 FROM papers WHERE id = ?", (paper.paper_id,)).fetchone()
    now = now_iso()
    conn.execute(
        """
        INSERT INTO papers (
            id, venue_slug, number, title, abstract, tldr, keywords_json, primary_area,
            status, acceptance_type, raw_venueid, venue_string, url, pdate, tcdate, tmdate,
            created_at, updated_at
        ) VALUES (
            :id, :venue_slug, :number, :title, :abstract, :tldr, :keywords_json, :primary_area,
            :status, :acceptance_type, :raw_venueid, :venue_string, :url, :pdate, :tcdate, :tmdate,
            :now, :now
        )
        ON CONFLICT(id) DO UPDATE SET
            venue_slug=excluded.venue_slug,
            number=excluded.number,
            title=excluded.title,
            abstract=excluded.abstract,
            tldr=excluded.tldr,
            keywords_json=excluded.keywords_json,
            primary_area=excluded.primary_area,
            status=excluded.status,
            acceptance_type=excluded.acceptance_type,
            raw_venueid=excluded.raw_venueid,
            venue_string=excluded.venue_string,
            url=excluded.url,
            pdate=excluded.pdate,
            tcdate=excluded.tcdate,
            tmdate=excluded.tmdate,
            updated_at=excluded.updated_at
        """,
        {
            "id": paper.paper_id,
            "venue_slug": paper.venue_slug,
            "number": paper.number,
            "title": paper.title,
            "abstract": paper.abstract,
            "tldr": paper.tldr,
            "keywords_json": _json_list(paper.keywords),
            "primary_area": paper.primary_area,
            "status": paper.status,
            "acceptance_type": paper.acceptance_type,
            "raw_venueid": paper.raw_venueid,
            "venue_string": paper.venue_string,
            "url": paper.url,
            "pdate": paper.pdate,
            "tcdate": paper.tcdate,
            "tmdate": paper.tmdate,
            "now": now,
        },
    )

    _replace_authors(conn, paper)
    _replace_topics(conn, paper)
    _replace_fts(conn, paper)
    return existing is None


def count_papers(conn: sqlite3.Connection, venue_slug: str | None = None) -> int:
    if venue_slug is None:
        row = conn.execute("SELECT COUNT(*) FROM papers").fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) FROM papers WHERE venue_slug = ?", (venue_slug,)
        ).fetchone()
    return int(row[0])


# Column weights for bm25 (papers_fts order: paper_id, title, abstract, keywords,
# author_names, org_names). Title + keywords matter most; paper_id is UNINDEXED (0).
_BM25_WEIGHTS = "0.0, 5.0, 1.0, 3.0, 1.0, 1.0"


def search(
    conn: sqlite3.Connection,
    fts_query: str,
    *,
    venue: str | None = None,
    year: int | None = None,
    org_id: str | None = None,
    accepted_only: bool = False,
    limit: int = 20,
) -> list[sqlite3.Row]:
    """FTS search ranked by bm25 (exposed positive, bigger = better), deterministic order."""
    clauses = ["papers_fts MATCH :q"]
    params: dict[str, object] = {"q": fts_query, "limit": limit}
    if venue is not None:
        clauses.append("p.venue_slug = :venue")
        params["venue"] = venue
    if year is not None:
        clauses.append("v.year = :year")
        params["year"] = year
    if accepted_only:
        clauses.append("p.status = 'accepted'")
    if org_id is not None:
        clauses.append(
            "EXISTS (SELECT 1 FROM paper_authors pa JOIN author_affiliations aa "
            "ON aa.author_id = pa.author_id WHERE pa.paper_id = p.id AND aa.org_id = :org_id)"
        )
        params["org_id"] = org_id
    sql = (
        f"SELECT p.*, -bm25(papers_fts, {_BM25_WEIGHTS}) AS relevance "
        "FROM papers_fts JOIN papers p ON p.id = papers_fts.paper_id "
        "JOIN venues v ON v.slug = p.venue_slug "
        f"WHERE {' AND '.join(clauses)} "
        "ORDER BY relevance DESC, p.id ASC LIMIT :limit"
    )
    return conn.execute(sql, params).fetchall()


def get(conn: sqlite3.Connection, paper_id: str) -> sqlite3.Row | None:
    row: sqlite3.Row | None = conn.execute(
        "SELECT * FROM papers WHERE id = ?", (paper_id,)
    ).fetchone()
    return row


def exists(conn: sqlite3.Connection, paper_id: str) -> bool:
    return conn.execute("SELECT 1 FROM papers WHERE id = ?", (paper_id,)).fetchone() is not None


def authors_for_papers(
    conn: sqlite3.Connection, paper_ids: list[str]
) -> dict[str, list[sqlite3.Row]]:
    """Batch-fetch ordered author rows for a set of papers (avoids N+1)."""
    grouped: dict[str, list[sqlite3.Row]] = {pid: [] for pid in paper_ids}
    if not paper_ids:
        return grouped
    placeholders = ",".join("?" * len(paper_ids))
    rows = conn.execute(
        f"SELECT paper_id, author_id, raw_name, position FROM paper_authors "
        f"WHERE paper_id IN ({placeholders}) ORDER BY paper_id, position",
        paper_ids,
    ).fetchall()
    for row in rows:
        grouped[row["paper_id"]].append(row)
    return grouped


def list_by_author(
    conn: sqlite3.Connection, author_id: str, *, venue: str | None = None, limit: int = 50
) -> list[sqlite3.Row]:
    clauses = ["pa.author_id = :author_id"]
    params: dict[str, object] = {"author_id": author_id, "limit": limit}
    if venue is not None:
        clauses.append("p.venue_slug = :venue")
        params["venue"] = venue
    sql = (
        "SELECT p.* FROM papers p JOIN paper_authors pa ON pa.paper_id = p.id "
        f"WHERE {' AND '.join(clauses)} "
        "ORDER BY COALESCE(p.pdate, p.tcdate, 0) DESC, p.id ASC LIMIT :limit"
    )
    return conn.execute(sql, params).fetchall()


def list_by_org(
    conn: sqlite3.Connection, org_id: str, *, venue: str | None = None, limit: int = 50
) -> list[sqlite3.Row]:
    clauses = ["aa.org_id = :org_id"]
    params: dict[str, object] = {"org_id": org_id, "limit": limit}
    if venue is not None:
        clauses.append("p.venue_slug = :venue")
        params["venue"] = venue
    sql = (
        "SELECT DISTINCT p.* FROM papers p "
        "JOIN paper_authors pa ON pa.paper_id = p.id "
        "JOIN author_affiliations aa ON aa.author_id = pa.author_id "
        f"WHERE {' AND '.join(clauses)} "
        "ORDER BY COALESCE(p.pdate, p.tcdate, 0) DESC, p.id ASC LIMIT :limit"
    )
    return conn.execute(sql, params).fetchall()


def _replace_authors(conn: sqlite3.Connection, paper: NormalizedPaper) -> None:
    conn.execute("DELETE FROM paper_authors WHERE paper_id = ?", (paper.paper_id,))
    # OR IGNORE: a note can legitimately list the same authorid twice — keep the first
    # position rather than aborting the whole transaction on the (paper_id, author_id) PK.
    conn.executemany(
        "INSERT OR IGNORE INTO paper_authors (paper_id, author_id, position, raw_name) "
        "VALUES (?, ?, ?, ?)",
        [(paper.paper_id, a.author_id, a.position, a.raw_name) for a in paper.authors],
    )


def _replace_topics(conn: sqlite3.Connection, paper: NormalizedPaper) -> None:
    conn.execute("DELETE FROM paper_topics WHERE paper_id = ?", (paper.paper_id,))
    conn.executemany(
        "INSERT OR IGNORE INTO paper_topics (paper_id, topic, source) VALUES (?, ?, 'keyword')",
        [(paper.paper_id, topic) for topic in paper.topics],
    )


def _replace_fts(conn: sqlite3.Connection, paper: NormalizedPaper) -> None:
    conn.execute("DELETE FROM papers_fts WHERE paper_id = ?", (paper.paper_id,))
    author_names = " ".join(a.raw_name for a in paper.authors)
    org_names = " ".join(a.affiliation for a in paper.authors if a.affiliation)
    conn.execute(
        """
        INSERT INTO papers_fts (paper_id, title, abstract, keywords, author_names, org_names)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            paper.paper_id,
            paper.title,
            paper.abstract,
            " ".join(paper.keywords),
            author_names,
            org_names,
        ),
    )


def _json_list(items: list[str]) -> str:
    import json

    return json.dumps(items, ensure_ascii=False)
