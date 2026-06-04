"""``confos orgs`` — top/papers (org coverage is best-effort in v1; Phase 3 enriches)."""

from typing import Annotated

import typer

from ..console import bind_command, global_output_options
from ..output.plain import tsv_rows
from ..output.table import data_table
from ..services import orgs as orgs_service
from ._render import papers_tsv, render_papers, resolve_limit, validate_venue

app = typer.Typer(no_args_is_help=False, help="Explore organisations.")


@app.command()
@global_output_options
def top(
    ctx: typer.Context,
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
    limit: Annotated[int | None, typer.Option("--limit", help="Cap result count.")] = None,
) -> None:
    """Rank organisations by paper count (best-effort coverage in v1).

    Examples:
      confos orgs top --venue neurips-2025
      confos orgs top --venue neurips-2025 --limit 20 --json
    """
    app_ctx = bind_command(ctx, "orgs.top")
    resolved_venue = venue or app_ctx.venue
    validate_venue(app_ctx, resolved_venue)
    resolved_limit = resolve_limit(limit, app_ctx.limit, 50)
    result = orgs_service.top_orgs(app_ctx.paths, venue=resolved_venue, limit=resolved_limit)
    rows = result["rows"]
    dq = result["data_quality"]
    if app_ctx.is_json:
        app_ctx.render_json(
            result, query={"venue": resolved_venue, "limit": resolved_limit}, venue=resolved_venue
        )
        return
    if app_ctx.is_plain:
        tsv_rows(app_ctx.out, [(o["name"], o["country"] or "", o["papers"]) for o in rows])
        return
    if not rows:
        app_ctx.out.print("No organisation data yet (v1 affiliation coverage is sparse).")
        return
    data_table(
        app_ctx.out,
        ["organisation", "country", "papers"],
        [(o["name"], o["country"] or "—", str(o["papers"])) for o in rows],
        title="Top organisations",
    )
    app_ctx.out.print(
        f"coverage: {dq['papers_with_signal']}/{dq['papers_total']} papers have affiliation "
        f"signal ({dq['unknown']} unknown)"
    )


@app.command()
@global_output_options
def papers(
    ctx: typer.Context,
    org: Annotated[str, typer.Argument(help="Organisation name, e.g. 'Google DeepMind'.")],
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
    limit: Annotated[int | None, typer.Option("--limit", help="Cap result count.")] = None,
) -> None:
    """List papers affiliated with an organisation.

    Examples:
      confos orgs papers "Google DeepMind" --venue neurips-2025
      confos orgs papers "MIT" --limit 25 --json
    """
    app_ctx = bind_command(ctx, "orgs.papers")
    resolved_venue = venue or app_ctx.venue
    validate_venue(app_ctx, resolved_venue)
    resolved_limit = resolve_limit(limit, app_ctx.limit, 50)
    result = orgs_service.org_papers(app_ctx.paths, org, venue=resolved_venue, limit=resolved_limit)
    if app_ctx.is_json:
        app_ctx.render_json(
            result, query={"org": org, "venue": resolved_venue, "limit": resolved_limit}
        )
        return
    if app_ctx.is_plain:
        tsv_rows(app_ctx.out, papers_tsv(result["papers"]))
        return
    app_ctx.out.print(f"[bold]{result['org']['name']}[/bold] — {len(result['papers'])} paper(s)")
    render_papers(app_ctx, result["papers"], show_score=False)
