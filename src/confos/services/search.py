"""Paper search + show + related (offline, FTS5/bm25).

Builds an FTS query, runs it through the papers repository, and assembles SCHEMAS §2
Paper dicts (with their authors batched to avoid N+1). All offline and deterministic.
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from ..db.connection import connect
from ..db.migrate import migrate
from ..db.repositories import papers as papers_repo
from ..errors import NotFoundError
from ..fts import match_query, match_query_or
from ..normalize.orgs import org_slug
from ..paths import Paths
from ..serialize import author_brief, paper_dict

# Drop short/common tokens when deriving "related" terms from a title.
_STOP = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "via",
    "using",
    "into",
    "are",
    "our",
    "new",
    "towards",
    "toward",
    "based",
    "this",
    "that",
    "can",
    "how",
    "all",
    "not",
    "but",
}
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9-]{2,}")


def assemble_papers(
    conn: sqlite3.Connection,
    rows: list[sqlite3.Row],
    *,
    include_abstract: bool,
    with_bm25: bool,
    include_reviews: bool = False,
) -> list[dict[str, Any]]:
    ids = [row["id"] for row in rows]
    authors_map = papers_repo.authors_for_papers(conn, ids)
    out: list[dict[str, Any]] = []
    for row in rows:
        briefs = [author_brief(a) for a in authors_map.get(row["id"], [])]
        # with_bm25 callers pass search() rows, which always carry a 'relevance' column.
        bm25 = row["relevance"] if with_bm25 else None
        out.append(
            paper_dict(
                row,
                briefs,
                include_abstract=include_abstract,
                include_reviews=include_reviews,
                bm25=bm25,
            )
        )
    return out


def top_papers(
    paths: Paths,
    *,
    order: str,
    topic: str | None = None,
    venue: str | None = None,
    year: int | None = None,
    min_reviews: int = 1,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Reviewed papers ranked by a review signal (``rating`` | ``controversy``), optionally
    scoped to a topic (FTS) + venue/year. Carries the review signals in each Paper object."""
    conn = connect(paths.db)
    try:
        migrate(conn)
        fts = match_query(topic) if topic else None
        rows = papers_repo.ranked_by_reviews(
            conn,
            order=order,
            fts_query=fts,
            venue=venue,
            year=year,
            min_reviews=min_reviews,
            limit=limit,
        )
        return assemble_papers(
            conn, rows, include_abstract=False, with_bm25=False, include_reviews=True
        )
    finally:
        conn.close()


def search_papers(
    paths: Paths,
    query: str,
    *,
    venue: str | None = None,
    year: int | None = None,
    org: str | None = None,
    accepted_only: bool = False,
    limit: int = 20,
) -> list[dict[str, Any]]:
    conn = connect(paths.db)
    try:
        migrate(conn)
        rows = papers_repo.search(
            conn,
            match_query(query),
            venue=venue,
            year=year,
            org_id=org_slug(org) if org else None,
            accepted_only=accepted_only,
            limit=limit,
        )
        return assemble_papers(conn, rows, include_abstract=False, with_bm25=True)
    finally:
        conn.close()


def recent_papers(
    paths: Paths, *, venue: str | None = None, limit: int = 20
) -> list[dict[str, Any]]:
    """Most-recent papers in a venue (the `brief` fallback when no reviews are ingested)."""
    conn = connect(paths.db)
    try:
        migrate(conn)
        rows = papers_repo.recent(conn, venue=venue, limit=limit)
        return assemble_papers(conn, rows, include_abstract=False, with_bm25=False)
    finally:
        conn.close()


def get_paper(paths: Paths, paper_id: str, *, with_related: bool = False) -> dict[str, Any]:
    conn = connect(paths.db)
    try:
        migrate(conn)
        row = papers_repo.get(conn, paper_id)
        if row is None:
            raise NotFoundError(
                f"Paper '{paper_id}' is not in the local store.",
                hint="Ingest its venue first (confos ingest <venue>).",
            )
        briefs = [
            author_brief(a) for a in papers_repo.authors_for_papers(conn, [paper_id])[paper_id]
        ]
        data = paper_dict(
            row, briefs, include_abstract=True, include_artifacts=True, include_reviews=True
        )
        if with_related:
            data["related"] = _related_for_row(conn, row, limit=10)
        return data
    finally:
        conn.close()


def related_papers(paths: Paths, paper_id: str, *, limit: int = 10) -> list[dict[str, Any]]:
    conn = connect(paths.db)
    try:
        migrate(conn)
        row = papers_repo.get(conn, paper_id)
        if row is None:
            raise NotFoundError(
                f"Paper '{paper_id}' is not in the local store.",
                hint="Ingest its venue first (confos ingest <venue>).",
            )
        return _related_for_row(conn, row, limit=limit)
    finally:
        conn.close()


def _related_for_row(
    conn: sqlite3.Connection, row: sqlite3.Row, *, limit: int
) -> list[dict[str, Any]]:
    """Related papers via an FTS OR-query built from the source title + keywords (D-rec)."""
    fts = match_query_or(_related_terms(row))
    if not fts:
        return []
    # Fetch a few extra so we can drop the source paper itself.
    rows = papers_repo.search(conn, fts, limit=limit + 1)
    rows = [r for r in rows if r["id"] != row["id"]][:limit]
    return assemble_papers(conn, rows, include_abstract=False, with_bm25=True)


def _related_terms(row: sqlite3.Row) -> list[str]:
    terms: list[str] = list(json.loads(row["keywords_json"] or "[]"))
    for word in _WORD.findall(row["title"] or ""):
        lowered = word.lower()
        if lowered not in _STOP:
            terms.append(word)
    # Dedup case-insensitively, preserve order, cap to keep the FTS query bounded.
    seen: set[str] = set()
    deduped: list[str] = []
    for term in terms:
        key = term.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(term)
    return deduped[:12]
