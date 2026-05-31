"""``authors find --topic`` ranking — the product differentiator (RANKING §2).

Ranks the people *actually publishing* on a topic, with an explanation and full
provenance. Deterministic + testable (a fixed-ranking fixture pins "correct"):

    score(a) = matched_paper_count
             + 0.5 * sum(normalized_bm25(p) for p in matched)   # 0..1, best match = 1
             + recency_bonus                                     # 0 for single-venue

Tie-break: score desc, matched_paper_count desc, author_id asc (stable across rebuilds).
"""

from __future__ import annotations

import sqlite3
from typing import Any

from ..aliases import load_topic_aliases
from ..db.connection import connect
from ..db.migrate import migrate
from ..db.repositories import authors as authors_repo
from ..db.repositories import papers as papers_repo
from ..errors import NotFoundError
from ..fts import topic_query
from ..paths import Paths
from ..serialize import author_dict

# Effectively "all matches" — the candidate set is every author on a matching paper.
_CANDIDATE_CAP = 5000
# Bound the per-author matched_papers list in output (still ample provenance).
_MAX_MATCHED_OUT = 25


def find_authors(
    paths: Paths, topic: str, *, venue: str | None = None, limit: int = 20
) -> dict[str, Any]:
    conn = connect(paths.db)
    try:
        migrate(conn)
        fts = topic_query(topic, load_topic_aliases(paths))
        rows = papers_repo.search(conn, fts, venue=venue, limit=_CANDIDATE_CAP)
        warnings: list[str] = []
        if len(rows) >= _CANDIDATE_CAP:
            warnings.append(
                f"candidate set truncated at {_CANDIDATE_CAP} matching papers; "
                "matched_paper_count may be a lower bound — narrow --topic or --venue"
            )
        ranked = _rank(conn, rows, topic=topic, single_venue=venue is not None, limit=limit)
        return {"topic": topic, "venue": venue, "authors": ranked, "warnings": warnings}
    finally:
        conn.close()


def _rank(
    conn: sqlite3.Connection,
    rows: list[sqlite3.Row],
    *,
    topic: str,
    single_venue: bool,
    limit: int,
) -> list[dict[str, Any]]:
    if not rows:
        return []

    max_rel = max((r["relevance"] for r in rows), default=0.0)
    years = [r["venue_year"] for r in rows if r["venue_year"] is not None]
    multi_venue = (not single_venue) and len({r["venue_slug"] for r in rows}) > 1
    min_year = min(years) if years else None
    max_year = max(years) if years else None
    # recency only applies across multiple years of multiple venues (RANKING §2)
    span = (
        (max_year - min_year)
        if (multi_venue and min_year is not None and max_year is not None and max_year > min_year)
        else 0
    )

    authors_by_paper = papers_repo.authors_for_papers(conn, [r["id"] for r in rows])
    candidates: dict[str, list[tuple[sqlite3.Row, float]]] = {}
    for row in rows:
        # Clamp to [0,1]; best match = 1. Ubiquitous-term (<=0 bm25) matches contribute 0.
        norm = max(row["relevance"], 0.0) / max_rel if max_rel > 0 else 0.0
        for author in authors_by_paper.get(row["id"], []):
            candidates.setdefault(author["author_id"], []).append((row, norm))

    author_rows = authors_repo.get_many(conn, list(candidates))
    results: list[dict[str, Any]] = []
    for author_id, matched in candidates.items():
        author_row = author_rows.get(author_id)
        if author_row is None:  # pragma: no cover - FK guarantees presence
            continue
        count = len(matched)
        bm25_sum = sum(norm for _, norm in matched)
        recency = _recency_bonus(matched, min_year, span)
        score = count + 0.5 * bm25_sum + recency
        ordered = sorted(matched, key=lambda m: (-m[0]["relevance"], m[0]["id"]))

        result = author_dict(author_row)
        result.update(
            {
                "matched_paper_count": count,
                "score": round(score, 4),
                "score_components": {
                    "paper_count": count,
                    "bm25_sum": round(bm25_sum, 4),
                    "recency_bonus": round(recency, 4),
                },
                "why_relevant": (
                    f"{count} paper(s) matching {topic!r}; top: {ordered[0][0]['title']}"
                ),
                "matched_papers": [
                    {
                        "paper_id": row["id"],
                        "title": row["title"],
                        "url": row["url"],
                        "bm25": round(row["relevance"], 4),
                    }
                    for row, _ in ordered[:_MAX_MATCHED_OUT]
                ],
            }
        )
        results.append(result)

    results.sort(key=lambda r: (-r["score"], -r["matched_paper_count"], r["author_id"]))
    return results[:limit]


def _recency_bonus(
    matched: list[tuple[sqlite3.Row, float]], min_year: int | None, span: int
) -> float:
    if span <= 0 or min_year is None:
        return 0.0
    newest = max(
        (row["venue_year"] for row, _ in matched if row["venue_year"] is not None), default=min_year
    )
    return 0.3 * (newest - min_year) / span


def coauthors(paths: Paths, author_id: str, *, limit: int = 50) -> dict[str, Any]:
    conn = connect(paths.db)
    try:
        migrate(conn)
        author = authors_repo.get_with_stats(conn, author_id)
        if author is None:
            raise NotFoundError(
                f"Author '{author_id}' is not in the local store.",
                hint="Find them with `confos authors search <name>`.",
            )
        rows = authors_repo.coauthors(conn, author_id, limit=limit)
        return {
            "author": author_dict(author),
            "coauthors": [{**author_dict(r), "shared_papers": r["shared_papers"]} for r in rows],
        }
    finally:
        conn.close()
