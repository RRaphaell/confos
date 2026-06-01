"""``confos authors`` — find/search/show/papers/coauthors.

search/show/papers land in Phase 2; find (ranked people discovery) + coauthors in Phase 3.
"""

from typing import Annotated

import typer

from ..console import bind_command, global_output_options
from ..output.plain import key_value_plain, tsv_rows
from ..output.table import data_table, key_value_table
from ..services import authors as authors_service
from ..services import ranking as ranking_service
from ._render import (
    papers_tsv,
    render_authors,
    render_found_authors,
    render_papers,
    resolve_limit,
)

app = typer.Typer(no_args_is_help=False, help="Find and explore authors.")


@app.command()
@global_output_options
def find(
    ctx: typer.Context,
    topic: Annotated[str, typer.Option("--topic", help="Topic to rank authors by.")],
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
    limit: Annotated[int | None, typer.Option("--limit", help="Cap result count.")] = None,
) -> None:
    """Rank the people actually publishing on a topic, with why-relevant + provenance.

    Examples:
      confos authors find --topic "agent memory" --venue neurips-2025 --limit 20
      confos authors find --topic "evals" --json
    """
    app_ctx = bind_command(ctx, "authors.find")
    resolved_venue = venue or app_ctx.venue
    resolved_limit = resolve_limit(limit, app_ctx.limit, 20)
    result = ranking_service.find_authors(
        app_ctx.paths, topic, venue=resolved_venue, limit=resolved_limit
    )
    authors = result["authors"]
    warnings = result["warnings"]
    query = {"topic": topic, "venue": resolved_venue, "limit": resolved_limit}
    if app_ctx.is_json:
        app_ctx.render_json(authors, query=query, venue=resolved_venue, warnings=warnings)
        return
    if app_ctx.is_plain:
        tsv_rows(
            app_ctx.out,
            [
                (a["author_id"], a["display_name"], a["matched_paper_count"], a["score"])
                for a in authors
            ],
        )
        return
    if not authors:
        app_ctx.out.print(f"No authors found for topic {topic!r}.")
        return
    render_found_authors(app_ctx, authors)
    for warning in warnings:
        app_ctx.warn(warning)


@app.command()
@global_output_options
def search(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Author name to search for.")],
    limit: Annotated[int | None, typer.Option("--limit", help="Cap result count.")] = None,
) -> None:
    """Search authors by name.

    Examples:
      confos authors search "Yann LeCun"
      confos authors search "Chen" --limit 10 --json
    """
    app_ctx = bind_command(ctx, "authors.search")
    resolved_limit = resolve_limit(limit, app_ctx.limit, 25)
    results = authors_service.search_authors(app_ctx.paths, name, limit=resolved_limit)
    if app_ctx.is_json:
        app_ctx.render_json(results, query={"name": name, "limit": resolved_limit})
        return
    if app_ctx.is_plain:
        tsv_rows(
            app_ctx.out,
            [
                (a["author_id"], a["display_name"], a["affiliation_current"], a["paper_count"])
                for a in results
            ],
        )
        return
    if not results:
        app_ctx.out.print(f"No authors matched {name!r}.")
        return
    render_authors(app_ctx, results)


@app.command()
@global_output_options
def show(
    ctx: typer.Context,
    author_id: Annotated[str, typer.Argument(help="Profile id (or email:/name: fallback).")],
) -> None:
    """Show a single author's profile and headline stats.

    Examples:
      confos authors show "~Yann_LeCun1"
      confos authors show email:someone@mit.edu --json
    """
    app_ctx = bind_command(ctx, "authors.show")
    author = authors_service.show_author(app_ctx.paths, author_id)
    if app_ctx.is_json:
        app_ctx.render_json(author, query={"author_id": author_id})
        return
    if app_ctx.is_plain:
        key_value_plain(app_ctx.out, [(k, v) for k, v in author.items() if k != "venues"])
        return
    key_value_table(
        app_ctx.out,
        [
            ("name", author["display_name"]),
            ("affiliation", author["affiliation_current"]),
            ("data quality", author["data_quality"]),
            ("papers", str(author["paper_count"])),
            ("profile", str(author["profile_url"] or "—")),
        ],
        title=author["author_id"],
    )
    if author["venues"]:
        data_table(
            app_ctx.out,
            ["venue", "papers"],
            [(v["venue"], str(v["papers"])) for v in author["venues"]],
            title="By venue",
        )


@app.command()
@global_output_options
def papers(
    ctx: typer.Context,
    author_id: Annotated[str, typer.Argument(help="Profile id (or email:/name: fallback).")],
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
    limit: Annotated[int | None, typer.Option("--limit", help="Cap result count.")] = None,
) -> None:
    """List an author's papers.

    Examples:
      confos authors papers "~Yann_LeCun1"
      confos authors papers "~Yann_LeCun1" --venue neurips-2025 --json
    """
    app_ctx = bind_command(ctx, "authors.papers")
    resolved_venue = venue or app_ctx.venue
    resolved_limit = resolve_limit(limit, app_ctx.limit, 50)
    result = authors_service.author_papers(
        app_ctx.paths, author_id, venue=resolved_venue, limit=resolved_limit
    )
    if app_ctx.is_json:
        app_ctx.render_json(
            result, query={"author_id": author_id, "venue": resolved_venue, "limit": resolved_limit}
        )
        return
    if app_ctx.is_plain:
        tsv_rows(app_ctx.out, papers_tsv(result["papers"]))
        return
    app_ctx.out.print(
        f"[bold]{result['author']['display_name']}[/bold] — {len(result['papers'])} paper(s)"
    )
    render_papers(app_ctx, result["papers"], show_score=False)


@app.command()
@global_output_options
def coauthors(
    ctx: typer.Context,
    author_id: Annotated[str, typer.Argument(help="Profile id (or email:/name: fallback).")],
    limit: Annotated[int | None, typer.Option("--limit", help="Cap result count.")] = None,
) -> None:
    """List an author's co-authors, ranked by shared papers.

    Examples:
      confos authors coauthors "~Yann_LeCun1"
      confos authors coauthors "~Yann_LeCun1" --limit 10 --json
    """
    app_ctx = bind_command(ctx, "authors.coauthors")
    resolved_limit = resolve_limit(limit, app_ctx.limit, 50)
    result = ranking_service.coauthors(app_ctx.paths, author_id, limit=resolved_limit)
    if app_ctx.is_json:
        app_ctx.render_json(result, query={"author_id": author_id, "limit": resolved_limit})
        return
    if app_ctx.is_plain:
        tsv_rows(
            app_ctx.out,
            [(c["author_id"], c["display_name"], c["shared_papers"]) for c in result["coauthors"]],
        )
        return
    app_ctx.out.print(
        f"[bold]{result['author']['display_name']}[/bold] — {len(result['coauthors'])} co-author(s)"
    )
    data_table(
        app_ctx.out,
        ["author", "affiliation", "shared"],
        [
            (c["display_name"], c["affiliation_current"], str(c["shared_papers"]))
            for c in result["coauthors"]
        ],
    )
