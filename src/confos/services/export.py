"""Export: the context pack (headline agent artifact) + bulk CSV/JSONL.

The context pack (SCHEMAS §6) is one self-contained, fully-cited object an agent ingests
to plan a literature review / thread / outreach. v1 is LLM-FREE — it contains only data
confos derives + cites. ``thin_areas`` is a clearly-labelled heuristic (under-represented
subtopics within the matched set), NOT LLM-synthesized "open questions" (D9).
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter
from typing import Any

from ..aliases import load_topic_aliases
from ..db.connection import connect
from ..db.migrate import migrate
from ..db.repositories import authors as authors_repo
from ..db.repositories import papers as papers_repo
from ..db.repositories import stats as stats_repo
from ..fts import topic_query
from ..paths import Paths
from ..serialize import author_brief, paper_dict
from .ranking import find_authors
from .search import assemble_papers

_PACK_CAP = 5000  # matched papers considered for stats/orgs/thin_areas
_THIN_MAX = 10  # cap on listed thin areas

_PACK_NOTES = (
    "All fields derived locally from OpenReview with provenance; no LLM synthesis. "
    "'thin_areas' is a heuristic (subtopics with few matched papers), not a claim."
)


def build_context_pack(
    paths: Paths,
    topic: str,
    *,
    venue: str | None = None,
    paper_limit: int = 20,
    author_limit: int = 10,
) -> dict[str, Any]:
    conn = connect(paths.db)
    try:
        migrate(conn)
        fts = topic_query(topic, load_topic_aliases(paths))
        rows = papers_repo.search(conn, fts, venue=venue, limit=_PACK_CAP)
        matched = len(rows)
        total = stats_repo.papers_total(conn, venue)

        papers = assemble_papers(conn, rows[:paper_limit], include_abstract=True, with_bm25=True)
        orgs = _top_orgs(conn, rows)
        thin_areas = _thin_areas(conn, [r["id"] for r in rows])
        status_mix = Counter(r["status"] for r in rows)
        stats = {
            "matched": matched,
            "total": total,
            "share": round(matched / total, 4) if total else 0.0,
            "by_status": dict(sorted(status_mix.items())),
        }
    finally:
        conn.close()

    # Ranked authors (its own connection); carries why_relevant + matched_papers.
    authors = find_authors(paths, topic, venue=venue, limit=author_limit)["authors"]

    return {
        "type": "confos.context_pack",
        "topic": topic,
        "venue": venue,
        "papers": papers,
        "authors": authors,
        "orgs": orgs,
        "stats": stats,
        "thin_areas": thin_areas,
        "notes": _PACK_NOTES,
    }


def _top_orgs(conn: Any, rows: list[Any], *, limit: int = 10) -> list[dict[str, Any]]:
    if not rows:
        return []
    authors_by_paper = papers_repo.authors_for_papers(conn, [r["id"] for r in rows])
    author_ids = {b["author_id"] for briefs in authors_by_paper.values() for b in briefs}
    aff = {
        aid: row["affiliation_current"]
        for aid, row in authors_repo.get_many(conn, list(author_ids)).items()
    }
    org_papers: Counter[str] = Counter()
    for briefs in authors_by_paper.values():
        orgs_on_paper = {aff[b["author_id"]] for b in briefs if aff.get(b["author_id"])}
        for org in orgs_on_paper:
            org_papers[org] += 1
    ranked = sorted(org_papers.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    return [{"name": name, "papers": count} for name, count in ranked]


def _thin_areas(conn: Any, paper_ids: list[str]) -> list[str]:
    """Subtopics appearing on the fewest matched papers (heuristic, labelled)."""
    counts = stats_repo.topic_counts_for_papers(conn, paper_ids)
    # rows come back ascending by count then topic; take the rarest (>1 matched paper total).
    if len(paper_ids) <= 1:
        return []
    thin = [row["key"] for row in counts if row["papers"] == 1]
    return thin[:_THIN_MAX]


def context_pack_markdown(pack: dict[str, Any]) -> str:
    """Render a context pack as Markdown (a human/doc-friendly view of the same data)."""
    venue = pack["venue"] or "all venues"
    lines = [f"# Context pack: {pack['topic']} ({venue})", "", f"_{pack['notes']}_", ""]

    stats = pack["stats"]
    lines.append(
        f"**Coverage:** {stats['matched']} of {stats['total']} papers match "
        f"({stats['share'] * 100:.2f}%). Status: "
        + ", ".join(f"{k} {v}" for k, v in stats["by_status"].items())
    )
    lines.append("")

    lines.append(f"## Papers ({len(pack['papers'])})")
    for paper in pack["papers"]:
        authors = ", ".join(a["name"] for a in paper["authors"])
        lines.append(f"- [{paper['title']}]({paper['url']}) — {authors} · _{paper['status']}_")
    lines.append("")

    lines.append(f"## People to know ({len(pack['authors'])})")
    for author in pack["authors"]:
        lines.append(
            f"- **{author['display_name']}** ({author['affiliation_current']}) — "
            f"{author['why_relevant']}"
        )
    lines.append("")

    if pack["orgs"]:
        lines.append("## Organisations")
        for org in pack["orgs"]:
            lines.append(f"- {org['name']}: {org['papers']} paper(s)")
        lines.append("")

    if pack["thin_areas"]:
        lines.append("## Thin areas (heuristic — under-represented subtopics)")
        lines.append(", ".join(pack["thin_areas"]))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# --- bulk dumps --------------------------------------------------------------

_PAPER_COLUMNS = [
    "paper_id",
    "title",
    "status",
    "acceptance_type",
    "venue",
    "url",
    "pdf_url",
    "supplementary_url",
    "authors",
    "keywords",
    "bibtex",
]
_AUTHOR_COLUMNS = [
    "author_id",
    "display_name",
    "affiliation_current",
    "affiliation_country",
    "data_quality",
    "profile_url",
    "homepage",
    "gscholar",
    "dblp",
    "expertise",
]


def _paper_rows(paths: Paths, venue: str | None) -> list[dict[str, Any]]:
    conn = connect(paths.db)
    try:
        migrate(conn)
        rows = papers_repo.list_all(conn, venue)
        authors_by_paper = papers_repo.authors_for_papers(conn, [r["id"] for r in rows])
        return [
            paper_dict(
                row,
                [author_brief(a) for a in authors_by_paper.get(row["id"], [])],
                include_artifacts=True,
            )
            for row in rows
        ]
    finally:
        conn.close()


def _author_rows(paths: Paths, venue: str | None) -> list[dict[str, Any]]:
    conn = connect(paths.db)
    try:
        migrate(conn)
        return [
            {
                "author_id": r["id"],
                "display_name": r["display_name"],
                "affiliation_current": r["affiliation_current"] or "Unknown",
                "affiliation_country": r["affiliation_country"] or "",
                "data_quality": r["data_quality"],
                "profile_url": r["profile_url"],
                "homepage": r["homepage"] or "",
                "gscholar": r["gscholar"] or "",
                "dblp": r["dblp"] or "",
                "expertise": "; ".join(json.loads(r["expertise_json"] or "[]")),
            }
            for r in authors_repo.list_for_export(conn, venue)
        ]
    finally:
        conn.close()


def export_papers(paths: Paths, *, venue: str | None, fmt: str) -> str:
    rows = _paper_rows(paths, venue)
    flat = [
        {
            "paper_id": p["paper_id"],
            "title": p["title"],
            "status": p["status"],
            "acceptance_type": p["acceptance_type"] or "",
            "venue": p["venue"],
            "url": p["url"],
            "pdf_url": p["pdf_url"] or "",
            "supplementary_url": p["supplementary_url"] or "",
            "authors": "; ".join(a["name"] for a in p["authors"]),
            "keywords": "; ".join(p["keywords"]),
            "bibtex": p["bibtex"] or "",
        }
        for p in rows
    ]
    return _render_bulk(flat, _PAPER_COLUMNS, fmt)


def export_authors(paths: Paths, *, venue: str | None, fmt: str) -> str:
    rows = _author_rows(paths, venue)
    return _render_bulk(rows, _AUTHOR_COLUMNS, fmt)


def _csv_safe(value: Any) -> Any:
    """Neutralise spreadsheet formula injection.

    A cell is dangerous if its first *non-whitespace* character is one of =,+,-,@:
    spreadsheet apps strip leading whitespace before evaluating, so the guard looks past
    it, then prefixes the original (untrimmed) value with a quote. We strip a leading BOM
    too (consumers often discard it, re-exposing the formula char) and use str.lstrip(),
    which covers all Unicode whitespace (NBSP, vertical tab, form feed, …), not just ASCII.
    """
    if isinstance(value, str) and value.lstrip("\ufeff").lstrip()[:1] in ("=", "+", "-", "@"):
        return "'" + value
    return "" if value is None else value


def _render_bulk(rows: list[dict[str, Any]], columns: list[str], fmt: str) -> str:
    if fmt == "jsonl":
        return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: _csv_safe(row.get(k)) for k in columns})
    return buffer.getvalue().rstrip("\n")
