"""``confos brief`` — one-command conference landscape (human dashboard + agent JSON).

Composes the whole toolkit (stats, orgs, top papers, people, thin areas) into one cited
object. ``--json`` is the agent primitive (a superset of ``export context``); the default
human form renders it as an ft-style dashboard; ``--plain`` keeps the Markdown view.
"""

from typing import Annotated, Any

import typer
from rich.markup import escape

from ..console import AppContext, bind_command
from ..output.dashboard import composition_bar, entry, section, stat_line
from ..output.table import bar_chart
from ..services import brief as brief_service

# Paper status → composition-bar segment style (themed; collapses to plain without colour).
_STATUS_SEG_STYLE = {
    "accepted": "status.accepted",
    "oral": "status.oral",
    "spotlight": "status.spotlight",
    "poster": "status.poster",
    "under_review": "status.active",
    "active": "status.active",
    "rejected": "status.rejected",
    "desk_rejected": "status.rejected",
    "withdrawn": "status.withdrawn",
    "unknown": "confos.muted",
}


def run(
    ctx: typer.Context,
    venue: Annotated[
        str | None, typer.Option("--venue", help="Venue slug to brief (recommended).")
    ] = None,
    topic: Annotated[
        str | None, typer.Option("--topic", help="Focus the brief on a topic (full-text).")
    ] = None,
) -> None:
    """One-command landscape: top papers, hot topics, orgs, people-to-know, thin areas.

    With --topic it's a focused brief (relevance-ranked papers + ranked people); without, the
    venue landscape (top-rated papers if reviews are ingested, else most-recent). LLM-free.
    Default is a human dashboard; `--json` is the agent primitive; `--plain` is Markdown.

    Examples:
      confos brief --venue neurips-2025
      confos brief --venue neurips-2025 --topic "agent memory"
      confos brief --venue neurips-2025 --json
    """
    app_ctx = bind_command(ctx, "brief")
    resolved_venue = venue or app_ctx.venue
    brief = brief_service.build_brief(app_ctx.paths, venue=resolved_venue, topic=topic)
    query = {"venue": resolved_venue, "topic": topic}
    if app_ctx.is_json:
        app_ctx.render_json(brief, query=query, venue=resolved_venue)
        return
    if app_ctx.is_plain:
        app_ctx.emit(brief_service.brief_markdown(brief))
        return
    render_brief(app_ctx, brief)


def render_brief(app_ctx: AppContext, brief: dict[str, Any]) -> None:
    """The human dashboard: header → overview + status bar → topic/org bars → papers/people."""
    out = app_ctx.out
    uni = app_ctx.use_unicode
    venue = brief["venue"] or "all venues"
    scope = f"{brief['topic']} @ {venue}" if brief["topic"] else venue
    diamond = "◆" if uni else "*"
    out.print(
        f"[confos.brand]{diamond} confos brief[/]  [confos.muted]·[/]  [bold]{escape(scope)}[/]"
    )

    overview = brief["overview"]
    stat_line(
        out,
        [
            (overview["papers"], "papers"),
            (overview["authors"], "authors"),
            (overview["orgs"], "orgs"),
            (overview["topics"], "topics"),
        ],
    )
    segments = [
        (status, count, _STATUS_SEG_STYLE.get(status, "confos.muted"))
        for status, count in (overview.get("status") or {}).items()
    ]
    composition_bar(out, segments, unicode=uni)
    # The bar prints "(95%)" per segment — caption it so that's never read as an acceptance rate.
    if segments and overview.get("status_note"):
        out.print(f"  [confos.muted]{escape(str(overview['status_note']))}[/]")

    if brief["hot_topics"]:
        section(out, "Hot topics", "most-published subtopics here")
        bar_chart(
            out,
            [(t["key"], t["papers"]) for t in brief["hot_topics"]],
            hue="confos.bar",
            unicode=uni,
        )

    section(out, "Organisations", "where the work comes from")
    if brief["rising_orgs"]:
        bar_chart(
            out,
            [(o["name"], o["papers"]) for o in brief["rising_orgs"]],
            hue="confos.bar2",
            unicode=uni,
        )
    else:
        out.print("  [confos.muted]No organisation data yet — run `confos enrich profiles`.[/]")

    papers = brief["top_papers"]
    section(out, "Top papers", f"by {papers['ranked_by']}")
    for index, paper in enumerate(papers["papers"], start=1):
        marker = ("★" if uni else "*") if index == 1 else ("●" if uni else "-")
        names = [a["name"] for a in paper["authors"]]
        meta = ", ".join(names[:3]) + (f" +{len(names) - 3}" if len(names) > 3 else "")
        if paper.get("venue"):
            meta += f" · {paper['venue']}"
        if paper.get("rating_mean") is not None:
            meta += f" · rating {paper['rating_mean']} (n={paper.get('review_count', 0)})"
        url = paper.get("url") or f"https://openreview.net/forum?id={paper['paper_id']}"
        entry(
            out,
            marker,
            str(paper["title"]),
            meta,
            link=url,
            supports_hyperlinks=app_ctx.supports_hyperlinks,
        )

    if brief["people_to_know"]:
        section(out, "People to know", "most-relevant authors here")
        for person in brief["people_to_know"]:
            affiliation = person.get("affiliation_current") or ""
            why = person.get("why_relevant") or f"{person.get('paper_count', 0)} paper(s)"
            secondary = (
                f"{affiliation} · {why}" if affiliation and affiliation != "Unknown" else why
            )
            entry(out, "●" if uni else "-", str(person["display_name"]), secondary)

    if brief["thin_areas"]:
        section(out, "Thin areas", "under-represented subtopics (heuristic)")
        out.print("  [confos.muted]" + escape(", ".join(brief["thin_areas"])) + "[/]")

    out.print()
    out.print(f"[confos.muted]{escape(brief['notes'])}[/]")
