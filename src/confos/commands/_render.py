"""Shared command-layer helpers: limit resolution + human paper/author tables."""

from __future__ import annotations

from typing import Any

from rich.table import Table

from ..console import AppContext


def resolve_limit(cmd_limit: int | None, ctx_limit: int | None, default: int) -> int:
    """Resolve a result cap: command flag > root --limit > default. Honours an explicit 0."""
    if cmd_limit is not None:
        return cmd_limit
    if ctx_limit is not None:
        return ctx_limit
    return default


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
    """A readable results table: titles ellipsize (no word-per-line wrap), and when every
    result shares one venue the venue column collapses into the caption (FU1)."""
    venue_set = {p["venue"] for p in papers}
    single_venue = next(iter(venue_set)) if len(venue_set) == 1 else None

    table = Table(
        caption=f"venue: {single_venue}" if single_venue else None, caption_justify="left"
    )
    table.add_column("#", justify="right", no_wrap=True)
    table.add_column("title", overflow="ellipsis", no_wrap=True)
    table.add_column("authors", overflow="ellipsis", no_wrap=True)
    if single_venue is None:
        table.add_column("venue", no_wrap=True)
    table.add_column("status", no_wrap=True)
    if show_score:
        table.add_column("score", justify="right", no_wrap=True)

    for index, paper in enumerate(papers, start=1):
        row = [str(index), str(paper["title"]), _authors_label(paper["authors"])]
        if single_venue is None:
            row.append(str(paper["venue"]))
        row.append(str(paper["status"]))
        if show_score:
            row.append(f"{float(paper.get('bm25') or 0):.1f}")
        table.add_row(*row)
    ctx.out.print(table)


def render_rated_papers(ctx: AppContext, papers: list[dict[str, Any]]) -> None:
    """Review-ranked results table (`papers top`/`controversial`): rating ± std + count."""
    venue_set = {p["venue"] for p in papers}
    single_venue = next(iter(venue_set)) if len(venue_set) == 1 else None
    table = Table(
        caption=f"venue: {single_venue}" if single_venue else None, caption_justify="left"
    )
    table.add_column("#", justify="right", no_wrap=True)
    table.add_column("title", overflow="ellipsis", no_wrap=True)
    table.add_column("authors", overflow="ellipsis", no_wrap=True)
    if single_venue is None:
        table.add_column("venue", no_wrap=True)
    table.add_column("rating", justify="right", no_wrap=True)
    table.add_column("±std", justify="right", no_wrap=True)
    table.add_column("reviews", justify="right", no_wrap=True)
    for index, paper in enumerate(papers, start=1):
        rating, std = paper.get("rating_mean"), paper.get("rating_std")
        row = [str(index), str(paper["title"]), _authors_label(paper["authors"])]
        if single_venue is None:
            row.append(str(paper["venue"]))
        row += [
            f"{rating:.2f}" if rating is not None else "—",
            f"{std:.2f}" if std is not None else "—",
            str(paper.get("review_count", 0)),
        ]
        table.add_row(*row)
    ctx.out.print(table)


def rated_papers_tsv(papers: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    return [
        (p["paper_id"], p["title"], p["venue"], p.get("rating_mean", ""), p.get("review_count", 0))
        for p in papers
    ]


def papers_tsv(papers: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    return [(p["paper_id"], p["title"], p["venue"], p["status"], p.get("bm25", "")) for p in papers]


def render_found_authors(ctx: AppContext, authors: list[dict[str, Any]]) -> None:
    """Ranked people-discovery table for ``authors find`` (with why-relevant)."""
    table = Table()
    table.add_column("#", justify="right", no_wrap=True)
    table.add_column("author", overflow="ellipsis", no_wrap=True)
    table.add_column("affiliation", overflow="ellipsis", no_wrap=True)
    table.add_column("matched", justify="right", no_wrap=True)
    table.add_column("score", justify="right", no_wrap=True)
    table.add_column("why", overflow="ellipsis", no_wrap=True)
    for index, author in enumerate(authors, start=1):
        table.add_row(
            str(index),
            author["display_name"],
            author["affiliation_current"],
            str(author["matched_paper_count"]),
            f"{author['score']:.2f}",
            author["why_relevant"],
        )
    ctx.out.print(table)


def render_authors(ctx: AppContext, authors: list[dict[str, Any]]) -> None:
    table = Table()
    table.add_column("id", no_wrap=True)
    table.add_column("author", overflow="ellipsis", no_wrap=True)
    table.add_column("affiliation", overflow="ellipsis")
    table.add_column("papers", justify="right", no_wrap=True)
    table.add_column("quality", no_wrap=True)
    for author in authors:
        table.add_row(
            author["author_id"],
            author["display_name"],
            author["affiliation_current"],
            str(author.get("paper_count", "")),
            author["data_quality"],
        )
    ctx.out.print(table)
