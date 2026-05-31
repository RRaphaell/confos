"""Shared human-mode renderers for paper/author lists (command layer only)."""

from __future__ import annotations

from typing import Any

from ..console import AppContext
from ..output.table import data_table


def _authors_label(authors: list[dict[str, Any]]) -> str:
    names: list[str] = [str(a["name"]) for a in authors]
    if not names:
        return "—"
    if len(names) == 1:
        return names[0]
    return f"{names[0]} +{len(names) - 1}"


def render_papers(
    ctx: AppContext, papers: list[dict[str, Any]], *, show_score: bool = True
) -> None:
    columns = ["#", "title", "authors", "venue", "status"]
    if show_score:
        columns.append("score")
    rows: list[list[str]] = []
    for index, paper in enumerate(papers, start=1):
        row = [
            str(index),
            paper["title"],
            _authors_label(paper["authors"]),
            paper["venue"],
            paper["status"],
        ]
        if show_score:
            row.append(str(paper.get("bm25", "")))
        rows.append(row)
    data_table(ctx.out, columns, rows)


def papers_tsv(papers: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    return [(p["paper_id"], p["title"], p["venue"], p["status"], p.get("bm25", "")) for p in papers]


def render_authors(ctx: AppContext, authors: list[dict[str, Any]]) -> None:
    rows = [
        (
            a["display_name"],
            a["affiliation_current"],
            str(a.get("paper_count", "")),
            a["data_quality"],
        )
        for a in authors
    ]
    data_table(ctx.out, ["author", "affiliation", "papers", "quality"], rows)
