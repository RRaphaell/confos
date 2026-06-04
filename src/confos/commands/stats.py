"""``confos stats`` — overview/topics/orgs/countries, always honest about coverage."""

from typing import Annotated

import typer

from ..console import AppContext, bind_command, global_output_options
from ..output.plain import key_value_plain, tsv_rows
from ..output.table import data_table, key_value_table
from ..services import stats as stats_service
from ._render import resolve_limit, validate_venue

app = typer.Typer(no_args_is_help=False, help="Aggregate statistics (honest about uncertainty).")


def _render_breakdown(
    app_ctx: AppContext, result: dict[str, object], *, label: str, explain: bool
) -> None:
    """Human render for a {rows, data_quality} stats payload."""
    rows = result["rows"]
    dq = result["data_quality"]
    assert isinstance(rows, list)
    assert isinstance(dq, dict)
    if not rows:
        app_ctx.out.print("No data yet.")
    else:
        data_table(
            app_ctx.out,
            [label, "papers"],
            [(str(r["key"]), str(r["papers"])) for r in rows],
        )
    total = int(dq["papers_total"])
    signal = int(dq["papers_with_signal"])
    ratio = signal / total if total else 0.0
    # Honest coverage IS the product, so make the number's quality visible: green/yellow/red.
    badge = "dq.high" if ratio >= 0.66 else "dq.med" if ratio >= 0.33 else "dq.low"
    app_ctx.out.print(
        f"coverage: [{badge}]{signal}/{total}[/] papers have signal ({dq['unknown']} unknown)"
    )
    if explain:
        key_value_table(
            app_ctx.out,
            [
                ("papers_total", str(dq["papers_total"])),
                ("papers_with_signal", str(dq["papers_with_signal"])),
                ("unknown", str(dq["unknown"])),
                ("low_confidence", str(dq["low_confidence"])),
                ("method", str(dq["method"])),
            ],
            title="data quality",
        )


@app.command()
@global_output_options
def overview(
    ctx: typer.Context,
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
) -> None:
    """High-level counts for a venue (papers, status mix, authors, orgs, topics).

    Examples:
      confos stats overview --venue neurips-2025
      confos stats overview --json
    """
    app_ctx = bind_command(ctx, "stats.overview")
    resolved_venue = venue or app_ctx.venue
    validate_venue(app_ctx, resolved_venue)
    result = stats_service.overview(app_ctx.paths, resolved_venue)
    if app_ctx.is_json:
        app_ctx.render_json(result, query={"venue": resolved_venue}, venue=resolved_venue)
        return
    if app_ctx.is_plain:
        flat = {k: v for k, v in result.items() if k != "status"}
        key_value_plain(app_ctx.out, list(flat.items()))
        return
    status = result["status"]
    assert isinstance(status, dict)
    key_value_table(
        app_ctx.out,
        [
            ("papers", str(result["papers"])),
            ("authors", str(result["authors"])),
            ("orgs", str(result["orgs"])),
            ("topics", str(result["topics"])),
            ("venues", str(result["venues"])),
        ],
        title=f"Overview: {resolved_venue or 'all venues'}",
    )
    if status:
        data_table(app_ctx.out, ["status", "papers"], [(k, str(v)) for k, v in status.items()])
        note = result.get("status_note")
        if note:
            app_ctx.out.print(f"[confos.muted]{note}[/]" if app_ctx.use_color else str(note))


@app.command()
@global_output_options
def topics(
    ctx: typer.Context,
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
    explain: Annotated[
        bool, typer.Option("--explain", help="Show coverage method + counts.")
    ] = False,
) -> None:
    """Top topics (normalised keywords) with coverage.

    Examples:
      confos stats topics --venue neurips-2025
      confos stats topics --venue neurips-2025 --explain --json
    """
    app_ctx = bind_command(ctx, "stats.topics")
    resolved_venue = venue or app_ctx.venue
    validate_venue(app_ctx, resolved_venue)
    limit = resolve_limit(None, app_ctx.limit, 50)
    result = stats_service.topics(app_ctx.paths, resolved_venue, limit=limit)
    _emit_breakdown(app_ctx, result, venue=resolved_venue, label="topic", explain=explain)


@app.command()
@global_output_options
def orgs(
    ctx: typer.Context,
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
    explain: Annotated[
        bool, typer.Option("--explain", help="Show coverage method + counts.")
    ] = False,
) -> None:
    """Top organisations with data-quality reporting.

    Examples:
      confos stats orgs --venue neurips-2025
      confos stats orgs --venue neurips-2025 --explain
    """
    app_ctx = bind_command(ctx, "stats.orgs")
    resolved_venue = venue or app_ctx.venue
    validate_venue(app_ctx, resolved_venue)
    limit = resolve_limit(None, app_ctx.limit, 50)
    result = stats_service.orgs(app_ctx.paths, resolved_venue, limit=limit)
    _emit_breakdown(app_ctx, result, venue=resolved_venue, label="organisation", explain=explain)


@app.command()
@global_output_options
def countries(
    ctx: typer.Context,
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
    explain: Annotated[
        bool, typer.Option("--explain", help="Show known/unknown/low-confidence counts and method.")
    ] = False,
) -> None:
    """Country distribution, with explicit known/unknown counts.

    Examples:
      confos stats countries --venue neurips-2025
      confos stats countries --venue neurips-2025 --explain --json
    """
    app_ctx = bind_command(ctx, "stats.countries")
    resolved_venue = venue or app_ctx.venue
    validate_venue(app_ctx, resolved_venue)
    limit = resolve_limit(None, app_ctx.limit, 50)
    result = stats_service.countries(app_ctx.paths, resolved_venue, limit=limit)
    _emit_breakdown(app_ctx, result, venue=resolved_venue, label="country", explain=explain)


def _emit_breakdown(
    app_ctx: AppContext,
    result: dict[str, object],
    *,
    venue: str | None,
    label: str,
    explain: bool,
) -> None:
    if app_ctx.is_json:
        app_ctx.render_json(result, query={"venue": venue}, venue=venue)
        return
    if app_ctx.is_plain:
        rows = result["rows"]
        assert isinstance(rows, list)
        tsv_rows(app_ctx.out, [(r["key"], r["papers"]) for r in rows])
        return
    _render_breakdown(app_ctx, result, label=label, explain=explain)
