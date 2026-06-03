"""``confos papers`` — search/show/related (offline, ranked, cited)."""

from typing import Annotated, Any

import typer

from ..console import bind_command, global_output_options
from ..output.plain import key_value_plain, tsv_rows
from ..services import search as search_service
from ._render import (
    papers_tsv,
    rated_papers_tsv,
    render_paper_detail,
    render_papers,
    render_rated_papers,
    resolve_limit,
)

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
    resolved_limit = resolve_limit(limit, app_ctx.limit, 20)
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
        if resolved_venue:
            app_ctx.out.print(
                f"No papers matched {query!r} in venue {resolved_venue!r}. "
                "(Is it ingested? See `confos venues list`.)"
            )
        else:
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
    """Show a single paper, with authors (and optionally related papers).

    Examples:
      confos papers show aBcD1234
      confos papers show aBcD1234 --with related --json
    """
    app_ctx = bind_command(ctx, "papers.show")
    extras = {e.strip() for e in (with_ or "").split(",") if e.strip()}
    paper = search_service.get_paper(app_ctx.paths, paper_id, with_related="related" in extras)
    if app_ctx.is_json:
        app_ctx.render_json(paper, query={"paper_id": paper_id, "with": sorted(extras)})
        return
    authors = ", ".join(a["name"] for a in paper["authors"]) or "—"
    keywords = "; ".join(paper["keywords"])
    if app_ctx.is_plain:
        flat = {k: v for k, v in paper.items() if k not in ("related", "authors", "keywords")}
        flat["authors"] = authors
        flat["keywords"] = keywords
        key_value_plain(app_ctx.out, list(flat.items()))
        return
    render_paper_detail(app_ctx, paper)
    related = paper.get("related") or []
    if related:
        app_ctx.out.print("\n[bold]Related[/bold]:" if app_ctx.use_color else "\nRelated:")
        render_papers(app_ctx, related)


def _render_rated(
    app_ctx: object,
    results: list[dict[str, Any]],
    *,
    query: dict[str, Any],
    venue: str | None,
    empty: str,
) -> None:
    """Shared rendering for `papers top`/`controversial` (json/plain/human)."""
    from ..console import AppContext

    assert isinstance(app_ctx, AppContext)
    if app_ctx.is_json:
        app_ctx.render_json(results, query=query, venue=venue)
        return
    if app_ctx.is_plain:
        tsv_rows(app_ctx.out, rated_papers_tsv(results))
        return
    if not results:
        app_ctx.out.print(empty)
        return
    render_rated_papers(app_ctx, results)
    app_ctx.info(f"{len(results)} result(s).")


@app.command()
@global_output_options
def top(
    ctx: typer.Context,
    topic: Annotated[
        str | None, typer.Option("--topic", help="Limit to a topic (full-text match).")
    ] = None,
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
    year: Annotated[int | None, typer.Option("--year", help="Limit to a year.")] = None,
    limit: Annotated[int | None, typer.Option("--limit", help="Cap result count.")] = None,
) -> None:
    """Highest-rated papers by mean review rating (needs reviews ingested).

    Ratings come from public Official_Reviews; ingest them with
    `confos ingest <venue> --with-reviews`. Scales differ per venue, so scope with --venue.

    Examples:
      confos papers top --topic "agent memory" --venue neurips-2025
      confos papers top --venue neurips-2025 --limit 10 --json
    """
    app_ctx = bind_command(ctx, "papers.top")
    resolved_venue = venue or app_ctx.venue
    resolved_limit = resolve_limit(limit, app_ctx.limit, 20)
    results = search_service.top_papers(
        app_ctx.paths,
        order="rating",
        topic=topic,
        venue=resolved_venue,
        year=year,
        min_reviews=1,
        limit=resolved_limit,
    )
    query = {"topic": topic, "venue": resolved_venue, "year": year, "limit": resolved_limit}
    _render_rated(
        app_ctx,
        results,
        query=query,
        venue=resolved_venue,
        empty="No rated papers found. (Ingest reviews with `--with-reviews`.)",
    )


@app.command()
@global_output_options
def controversial(
    ctx: typer.Context,
    topic: Annotated[
        str | None, typer.Option("--topic", help="Limit to a topic (full-text match).")
    ] = None,
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
    year: Annotated[int | None, typer.Option("--year", help="Limit to a year.")] = None,
    limit: Annotated[int | None, typer.Option("--limit", help="Cap result count.")] = None,
) -> None:
    """Most divisive papers — highest rating variance across reviewers (needs reviews).

    Requires ≥2 reviews (variance needs disagreement to measure).

    Examples:
      confos papers controversial --venue neurips-2025
      confos papers controversial --topic "alignment" --venue neurips-2025 --json
    """
    app_ctx = bind_command(ctx, "papers.controversial")
    resolved_venue = venue or app_ctx.venue
    resolved_limit = resolve_limit(limit, app_ctx.limit, 20)
    results = search_service.top_papers(
        app_ctx.paths,
        order="controversy",
        topic=topic,
        venue=resolved_venue,
        year=year,
        min_reviews=2,
        limit=resolved_limit,
    )
    query = {"topic": topic, "venue": resolved_venue, "year": year, "limit": resolved_limit}
    _render_rated(
        app_ctx,
        results,
        query=query,
        venue=resolved_venue,
        empty="No multi-review papers found. (Ingest reviews with `--with-reviews`.)",
    )


@app.command()
@global_output_options
def related(
    ctx: typer.Context,
    paper_id: Annotated[str, typer.Argument(help="OpenReview note id.")],
    limit: Annotated[int | None, typer.Option("--limit", help="Cap result count.")] = None,
) -> None:
    """Show papers related to a given paper (by title/keyword overlap).

    Examples:
      confos papers related aBcD1234
      confos papers related aBcD1234 --limit 5 --json
    """
    app_ctx = bind_command(ctx, "papers.related")
    resolved_limit = resolve_limit(limit, app_ctx.limit, 10)
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
