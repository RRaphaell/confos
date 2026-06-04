"""Shared command-layer helpers: limit resolution + human paper/author tables.

Free-text cells (titles, names, why-relevant) are escaped before they reach Rich so a
bracket in a title can never be mis-parsed as markup; status/score styling uses the themed
vocabulary (``console.confos_theme``), which collapses to plain text without colour. All of
this lives on the human path only — ``--json``/``--plain`` go through separate emitters.
"""

from __future__ import annotations

from typing import Any

from rich.box import ASCII, ROUNDED
from rich.console import Group
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from ..console import AppContext
from ..errors import NotFoundError, UsageError
from ..services import venues as venues_service


def resolve_limit(cmd_limit: int | None, ctx_limit: int | None, default: int) -> int:
    """Resolve a result cap: command flag > root --limit > default. Honours an explicit 0.

    A negative limit is rejected here (exit 2). This is the single funnel every subcommand
    ``--limit`` passes through, and SQLite reads a negative ``LIMIT`` as *unbounded* — so an
    unvalidated ``--limit -5`` silently returns the entire result set, a quiet contract
    violation. (The root ``--limit`` is also checked in the CLI callback; this covers the
    per-command flags.)
    """
    chosen = cmd_limit if cmd_limit is not None else ctx_limit if ctx_limit is not None else default
    if chosen < 0:
        raise UsageError("--limit must be >= 0.", hint="Use a non-negative result cap.")
    return chosen


def validate_venue(app_ctx: AppContext, slug: str | None) -> None:
    """Reject an unknown ``--venue`` loudly instead of silently returning an empty result.

    A typo'd slug is otherwise indistinguishable from a real but empty venue (``ok:true``,
    zero rows, exit 0), which quietly corrupts an agent's conclusions. ``None`` (all venues)
    and a real local venue pass silently; a known builtin alias that isn't ingested yet
    legitimately has no rows, so it passes with a stderr note rather than an error; only a
    genuinely-unknown slug raises (mirrors ``venues show``).
    """
    if not slug:
        return
    if venues_service.get_local_venue(app_ctx.paths, slug) is not None:
        return
    if slug in venues_service.builtin_aliases():
        app_ctx.info(
            f"venue '{slug}' is a known alias but not ingested yet — run `confos ingest {slug}`."
        )
        return
    raise NotFoundError(
        f"Venue '{slug}' is not known locally.",
        hint="See `confos venues list` (or `confos venues search <query>`).",
    )


def _authors_label(authors: list[dict[str, Any]]) -> str:
    names: list[str] = [str(a["name"]) for a in authors]
    if not names:
        return "—"
    if len(names) == 1:
        return names[0]
    return f"{names[0]} +{len(names) - 1}"


# Acceptance status → themed style; finer acceptance types (oral/spotlight/poster) win when
# present. Everything resolves to plain text under no-colour, so scanning still works there.
_STATUS_STYLE: dict[str, str] = {
    "accepted": "status.accepted",
    "rejected": "status.rejected",
    "desk_rejected": "status.rejected",
    "withdrawn": "status.withdrawn",
    "under_review": "status.active",
    "active": "status.active",
}
_ACCEPTANCE_STYLE: dict[str, str] = {
    "oral": "status.oral",
    "spotlight": "status.spotlight",
    "poster": "status.poster",
}


def _status_cell(paper: dict[str, Any]) -> str:
    """Status as themed markup so accepted work pops and rejected/withdrawn recede."""
    acceptance = str(paper.get("acceptance_type") or "").lower()
    if acceptance in _ACCEPTANCE_STYLE:
        return f"[{_ACCEPTANCE_STYLE[acceptance]}]{acceptance}[/]"
    status = str(paper.get("status") or "")
    style = _STATUS_STYLE.get(status)
    return f"[{style}]{escape(status)}[/]" if style else escape(status)


def render_papers(
    ctx: AppContext, papers: list[dict[str, Any]], *, show_score: bool = True
) -> None:
    """A readable results table: titles ellipsize (no word-per-line wrap), and when every
    result shares one venue the venue column collapses into the caption (FU1)."""
    venue_set = {p["venue"] for p in papers}
    single_venue = next(iter(venue_set)) if len(venue_set) == 1 else None

    table = Table(
        caption=f"venue: {single_venue}" if single_venue else None,
        caption_justify="left",
        expand=True,
    )
    table.add_column("#", justify="right", no_wrap=True)
    table.add_column("title", overflow="ellipsis", no_wrap=True, ratio=3)
    table.add_column("authors", overflow="ellipsis", no_wrap=True, ratio=1)
    if single_venue is None:
        table.add_column("venue", no_wrap=True)
    table.add_column("status", no_wrap=True, min_width=9)
    if show_score:
        table.add_column("score", justify="right", no_wrap=True, min_width=5)

    for index, paper in enumerate(papers, start=1):
        title = escape(str(paper["title"]))
        if ctx.supports_hyperlinks:
            # clickable in iTerm2/WezTerm/kitty/VS Code; Rich strips the link elsewhere.
            title = f"[link=https://openreview.net/forum?id={paper['paper_id']}]{title}[/link]"
        row = [str(index), title, escape(_authors_label(paper["authors"]))]
        if single_venue is None:
            row.append(escape(str(paper["venue"])))
        row.append(_status_cell(paper))
        if show_score:
            score = f"{float(paper.get('bm25') or 0):.1f}"
            # subtle heat: the strongest match pops, so a scanned list has an obvious #1.
            row.append(f"[score.hi]{score}[/]" if index == 1 else score)
        table.add_row(*row)
    ctx.out.print(table)


def render_rated_papers(ctx: AppContext, papers: list[dict[str, Any]]) -> None:
    """Review-ranked results table (`papers top`/`controversial`): rating ± std + count."""
    venue_set = {p["venue"] for p in papers}
    single_venue = next(iter(venue_set)) if len(venue_set) == 1 else None
    table = Table(
        caption=f"venue: {single_venue}" if single_venue else None,
        caption_justify="left",
        expand=True,
    )
    table.add_column("#", justify="right", no_wrap=True)
    table.add_column("title", overflow="ellipsis", no_wrap=True, ratio=3)
    table.add_column("authors", overflow="ellipsis", no_wrap=True, ratio=1)
    if single_venue is None:
        table.add_column("venue", no_wrap=True)
    table.add_column("rating", justify="right", no_wrap=True, min_width=6)
    table.add_column("±std", justify="right", no_wrap=True, min_width=5)
    table.add_column("reviews", justify="right", no_wrap=True, min_width=7)
    for index, paper in enumerate(papers, start=1):
        rating, std = paper.get("rating_mean"), paper.get("rating_std")
        row = [str(index), escape(str(paper["title"])), escape(_authors_label(paper["authors"]))]
        if single_venue is None:
            row.append(escape(str(paper["venue"])))
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
    table = Table(expand=True)
    table.add_column("#", justify="right", no_wrap=True)
    table.add_column("author", overflow="ellipsis", no_wrap=True, ratio=2)
    table.add_column("affiliation", overflow="ellipsis", no_wrap=True, ratio=2)
    table.add_column("matched", justify="right", no_wrap=True, min_width=7)
    table.add_column("score", justify="right", no_wrap=True, min_width=5)
    table.add_column("why", overflow="ellipsis", no_wrap=True, ratio=3)
    for index, author in enumerate(authors, start=1):
        table.add_row(
            str(index),
            escape(str(author["display_name"])),
            escape(str(author["affiliation_current"])),
            str(author["matched_paper_count"]),
            f"{author['score']:.2f}",
            escape(str(author["why_relevant"])),
        )
    ctx.out.print(table)


def render_authors(ctx: AppContext, authors: list[dict[str, Any]]) -> None:
    table = Table(expand=True)
    table.add_column("id", no_wrap=True)
    table.add_column("author", overflow="ellipsis", no_wrap=True, ratio=2)
    table.add_column("affiliation", overflow="ellipsis", ratio=2)
    table.add_column("papers", justify="right", no_wrap=True, min_width=6)
    table.add_column("quality", no_wrap=True, min_width=7)
    for author in authors:
        table.add_row(
            str(author["author_id"]),
            escape(str(author["display_name"])),
            escape(str(author["affiliation_current"])),
            str(author.get("paper_count", "")),
            str(author["data_quality"]),
        )
    ctx.out.print(table)


def _links_line(ctx: AppContext, forum: str, pdf: str) -> str:
    """A footer of source links: real OSC-8 links in a capable terminal, else ``label: url``."""

    def link(label: str, url: str) -> str:
        if ctx.supports_hyperlinks:
            return f"[link={url}][confos.accent]{label}[/][/link]"
        return f"[confos.muted]{label}:[/] {escape(url)}"

    parts = [link("forum", forum)]
    if pdf:
        parts.append(link("pdf", pdf))
    return "   ".join(parts)


def render_paper_detail(ctx: AppContext, paper: dict[str, Any]) -> None:
    """A reading-friendly card for ``papers show``: header + abstract + a links footer.

    Human path only — ``--json``/``--plain`` carry the same fields through their own
    emitters. The border degrades to ASCII when the stream isn't Unicode-capable.
    """
    authors = ", ".join(escape(str(a["name"])) for a in paper["authors"]) or "—"
    keywords = "; ".join(escape(str(k)) for k in paper["keywords"]) or "—"
    # _status_cell already shows the finest label (oral/spotlight/poster, else the status).
    status_line = f"{_status_cell(paper)}  [confos.muted]·[/]  {escape(str(paper['venue']))}"

    header = Table.grid(padding=(0, 2))
    header.add_column(style="confos.muted", justify="right", no_wrap=True)
    header.add_column(overflow="fold")
    header.add_row("authors", authors)
    header.add_row("status", status_line)
    # Reviews are the payoff of `--with-reviews`; the human card must show them too, not just
    # --json/--plain (field parity). Only render when the venue actually carries review data.
    if paper.get("review_count"):
        rating = paper.get("rating_mean")
        if rating is not None:
            std = paper.get("rating_std")
            spread = f" ± {std:.2f}" if std is not None else ""
            header.add_row("rating", f"{rating:.2f}{spread}  ({paper['review_count']} reviews)")
        if paper.get("decision"):
            header.add_row("decision", escape(str(paper["decision"])))
    if keywords != "—":
        header.add_row("keywords", keywords)

    forum = str(paper.get("url") or f"https://openreview.net/forum?id={paper['paper_id']}")
    pdf = str(paper.get("pdf_url") or "")

    body: list[Any] = [header]
    abstract = str(paper.get("abstract") or "").strip()
    if abstract:
        body += ["", escape(abstract)]
    body += ["", _links_line(ctx, forum, pdf)]

    title = escape(str(paper["title"]))
    if ctx.supports_hyperlinks:
        title = f"[link={forum}]{title}[/link]"
    ctx.out.print(
        Panel(
            Group(*body),
            title=f"[confos.accent]{title}[/]",
            title_align="left",
            subtitle=f"[confos.muted]{escape(str(paper['paper_id']))}[/]",
            subtitle_align="right",
            box=ROUNDED if ctx.use_unicode else ASCII,
            padding=(1, 2),
        )
    )
