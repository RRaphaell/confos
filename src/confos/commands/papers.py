"""``confos papers`` — search/show/related (offline, ranked, cited)."""

from typing import Annotated

import typer

from ..console import bind_command, global_output_options
from ..output.plain import key_value_plain, tsv_rows
from ..output.table import key_value_table
from ..services import search as search_service
from ._render import papers_tsv, render_papers

app = typer.Typer(no_args_is_help=False, help="Search and explore papers.")


@app.command()
@global_output_options
def search(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Full-text query over title, abstract, keywords.")],
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
    year: Annotated[int | None, typer.Option("--year", help="Limit to a year.")] = None,
    org: Annotated[str | None, typer.Option("--org", help="Limit to an organisation.")] = None,
    accepted_only: Annotated[
        bool, typer.Option("--accepted-only", help="Only accepted papers (local filter).")
    ] = False,
    limit: Annotated[int | None, typer.Option("--limit", help="Cap result count.")] = None,
) -> None:
    """Search papers by full text, ranked by relevance, with provenance.

    Examples:
      confos papers search "long-running agents" --venue neurips-2025
      confos papers search "tool use" --accepted-only --limit 50 --json
    """
    app_ctx = bind_command(ctx, "papers.search")
    resolved_venue = venue or app_ctx.venue
    resolved_limit = limit or app_ctx.limit or 20
    results = search_service.search_papers(
        app_ctx.paths,
        query,
        venue=resolved_venue,
        year=year,
        org=org,
        accepted_only=accepted_only,
        limit=resolved_limit,
    )
    query_echo = {
        "q": query,
        "venue": resolved_venue,
        "year": year,
        "org": org,
        "accepted_only": accepted_only,
        "limit": resolved_limit,
    }
    if app_ctx.is_json:
        app_ctx.render_json(results, query=query_echo, venue=resolved_venue)
        return
    if app_ctx.is_plain:
        tsv_rows(app_ctx.out, papers_tsv(results))
        return
    if not results:
        app_ctx.out.print(f"No papers matched {query!r}.")
        return
    render_papers(app_ctx, results)
    app_ctx.info(f"{len(results)} result(s).")


@app.command()
@global_output_options
def show(
    ctx: typer.Context,
    paper_id: Annotated[str, typer.Argument(help="OpenReview note id.")],
    with_: Annotated[
        str | None, typer.Option("--with", help="Comma-separated extras (currently: related).")
    ] = None,
) -> None:
    """Show a single paper, with authors (and optionally related papers)."""
    app_ctx = bind_command(ctx, "papers.show")
    extras = {e.strip() for e in (with_ or "").split(",") if e.strip()}
    paper = search_service.get_paper(app_ctx.paths, paper_id, with_related="related" in extras)
    if app_ctx.is_json:
        app_ctx.render_json(paper, query={"paper_id": paper_id, "with": sorted(extras)})
        return
    if app_ctx.is_plain:
        key_value_plain(app_ctx.out, [(k, v) for k, v in paper.items() if k != "related"])
        return
    authors = ", ".join(a["name"] for a in paper["authors"]) or "—"
    key_value_table(
        app_ctx.out,
        [
            ("title", paper["title"]),
            ("authors", authors),
            ("venue", paper["venue"]),
            ("status", paper["status"]),
            ("type", str(paper["acceptance_type"] or "—")),
            ("url", paper["url"]),
            ("abstract", paper.get("abstract", "")),
        ],
        title=paper["paper_id"],
    )
    related = paper.get("related") or []
    if related:
        app_ctx.out.print("\n[bold]Related[/bold]:" if app_ctx.use_color else "\nRelated:")
        render_papers(app_ctx, related)


@app.command()
@global_output_options
def related(
    ctx: typer.Context,
    paper_id: Annotated[str, typer.Argument(help="OpenReview note id.")],
    limit: Annotated[int | None, typer.Option("--limit", help="Cap result count.")] = None,
) -> None:
    """Show papers related to a given paper (by title/keyword overlap)."""
    app_ctx = bind_command(ctx, "papers.related")
    resolved_limit = limit or app_ctx.limit or 10
    results = search_service.related_papers(app_ctx.paths, paper_id, limit=resolved_limit)
    if app_ctx.is_json:
        app_ctx.render_json(results, query={"paper_id": paper_id, "limit": resolved_limit})
        return
    if app_ctx.is_plain:
        tsv_rows(app_ctx.out, papers_tsv(results))
        return
    if not results:
        app_ctx.out.print("No related papers found.")
        return
    render_papers(app_ctx, results)
