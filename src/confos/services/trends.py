"""Topic trends across venues/years (SCHEMAS §5).

For each venue: how many papers match the topic, out of how many total (share), plus the
top authors/orgs *by simple count* among the matched set (NOT the bm25-weighted
`authors find` score — that ranker is find-only, per DECISIONS). The delta compares the
first and last points in the series.
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from typing import Any

from ..aliases import load_topic_aliases
from ..db.connection import connect
from ..db.migrate import migrate
from ..db.repositories import papers as papers_repo
from ..db.repositories import stats as stats_repo
from ..db.repositories import venues as venues_repo
from ..fts import topic_query
from ..paths import Paths

_MATCH_CAP = 5000
_TOP_N = 5


def trends_topic(paths: Paths, topic: str, venues: list[str]) -> dict[str, Any]:
    conn = connect(paths.db)
    try:
        migrate(conn)
        fts = topic_query(topic, load_topic_aliases(paths))
        series = [_venue_point(conn, fts, venue) for venue in venues]
        return {"topic": topic, "series": series, "delta": _delta(series)}
    finally:
        conn.close()


def trends_compare(paths: Paths, venue_a: str, venue_b: str, topic: str) -> dict[str, Any]:
    """Head-to-head: a two-venue trend (same shape, with the delta a→b)."""
    return trends_topic(paths, topic, [venue_a, venue_b])


def _venue_point(conn: sqlite3.Connection, fts: str, venue: str) -> dict[str, Any]:
    rows = papers_repo.search(conn, fts, venue=venue, limit=_MATCH_CAP)
    matched = len(rows)
    total = stats_repo.papers_total(conn, venue)
    venue_row = venues_repo.get_venue(conn, venue)
    year = venue_row["year"] if venue_row is not None else None

    top_authors, top_orgs = _top_contributors(conn, rows)
    return {
        "venue": venue,
        "year": year,
        "matched": matched,
        "total": total,
        "share": round(matched / total, 4) if total else 0.0,
        "top_authors": top_authors,
        "top_orgs": top_orgs,
    }


def _top_contributors(
    conn: sqlite3.Connection, rows: list[sqlite3.Row]
) -> tuple[list[str], list[str]]:
    """Top authors (by matched-paper count) and top orgs (by matched papers)."""
    if not rows:
        return [], []
    authors_by_paper = papers_repo.authors_for_papers(conn, [r["id"] for r in rows])
    author_papers: Counter[str] = Counter()
    author_name: dict[str, str] = {}
    for briefs in authors_by_paper.values():
        for brief in briefs:
            author_papers[brief["author_id"]] += 1
            author_name.setdefault(brief["author_id"], brief["raw_name"])

    affiliations = _affiliations(conn, list(author_papers))
    org_papers: Counter[str] = Counter()
    for briefs in authors_by_paper.values():
        orgs_on_paper: set[str] = set()
        for brief in briefs:
            org = affiliations.get(brief["author_id"])
            if org:
                orgs_on_paper.add(org)
        for org in orgs_on_paper:
            org_papers[org] += 1

    top_authors = [author_name[aid] for aid, _ in _ranked(author_papers)]
    top_orgs = [org for org, _ in _ranked(org_papers)]
    return top_authors, top_orgs


def _affiliations(conn: sqlite3.Connection, author_ids: list[str]) -> dict[str, str | None]:
    from ..db.repositories import authors as authors_repo

    rows = authors_repo.get_many(conn, author_ids)
    return {aid: row["affiliation_current"] for aid, row in rows.items()}


def _ranked(counter: Counter[str]) -> list[tuple[str, int]]:
    # count desc, then key asc — deterministic.
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:_TOP_N]


def _delta(series: list[dict[str, Any]]) -> dict[str, float]:
    if len(series) < 2:
        return {"matched_abs": 0, "share_pp": 0.0}
    first, last = series[0], series[-1]
    return {
        "matched_abs": last["matched"] - first["matched"],
        "share_pp": round((last["share"] - first["share"]) * 100, 4),
    }
