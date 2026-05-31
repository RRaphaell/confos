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


def _replace_authors(conn: sqlite3.Connection, paper: NormalizedPaper) -> None:
    conn.execute("DELETE FROM paper_authors WHERE paper_id = ?", (paper.paper_id,))
    conn.executemany(
        "INSERT INTO paper_authors (paper_id, author_id, position, raw_name) VALUES (?, ?, ?, ?)",
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
