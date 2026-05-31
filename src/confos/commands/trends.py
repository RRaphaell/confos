"""``confos trends`` — how a topic moves across venues/years (topic/compare)."""

from typing import Annotated

import typer

from ..console import AppContext, bind_command, global_output_options
from ..output.plain import tsv_rows
from ..output.table import data_table
from ..services import trends as trends_service

app = typer.Typer(no_args_is_help=False, help="Track how topics move across venues/years.")


def _render(app_ctx: AppContext, result: dict[str, object]) -> None:
    series = result["series"]
    delta = result["delta"]
    assert isinstance(series, list)
    assert isinstance(delta, dict)
    data_table(
        app_ctx.out,
        ["venue", "year", "matched", "total", "share", "top authors"],
        [
            (
                s["venue"],
                str(s["year"] or "—"),
                str(s["matched"]),
                str(s["total"]),
                f"{s['share'] * 100:.2f}%",
                ", ".join(s["top_authors"][:3]) or "—",
            )
            for s in series
        ],
        title=f"Trend: {result['topic']}",
    )
    if len(series) >= 2:
        app_ctx.out.print(
            f"delta ({series[0]['venue']} → {series[-1]['venue']}): "
            f"matched {delta['matched_abs']:+d}, share {delta['share_pp']:+.2f}pp"
        )


def _emit(app_ctx: AppContext, result: dict[str, object], query: dict[str, object]) -> None:
    warnings = result["warnings"]
    assert isinstance(warnings, list)
    if app_ctx.is_json:
        app_ctx.render_json(result, query=query, warnings=warnings)
        return
    if app_ctx.is_plain:
        series = result["series"]
        assert isinstance(series, list)
        tsv_rows(
            app_ctx.out,
            [(s["venue"], s["year"], s["matched"], s["total"], s["share"]) for s in series],
        )
        return
    _render(app_ctx, result)
    for warning in warnings:
        app_ctx.warn(warning)


@app.command()
@global_output_options
def topic(
    ctx: typer.Context,
    topic_query: Annotated[str, typer.Argument(metavar="TOPIC", help="Topic to track.")],
    venues: Annotated[
        str,
        typer.Option(
            "--venues", help="Comma-separated venue slugs, e.g. neurips-2024,neurips-2025."
        ),
    ],
) -> None:
    """Show how a topic moves across a list of venues/years.

    Examples:
      confos trends topic "evals" --venues neurips-2023,neurips-2024,neurips-2025
    """
    app_ctx = bind_command(ctx, "trends.topic")
    venue_list = [v.strip() for v in venues.split(",") if v.strip()]
    result = trends_service.trends_topic(app_ctx.paths, topic_query, venue_list)
    _emit(app_ctx, result, {"topic": topic_query, "venues": venue_list})


@app.command()
@global_output_options
def compare(
    ctx: typer.Context,
    venue_a: Annotated[str, typer.Argument(help="First venue slug.")],
    venue_b: Annotated[str, typer.Argument(help="Second venue slug.")],
    topic: Annotated[str, typer.Option("--topic", help="Topic to compare head-to-head.")],
) -> None:
    """Compare a topic across two venues head-to-head.

    Examples:
      confos trends compare neurips-2024 neurips-2025 --topic "agents" --json
    """
    app_ctx = bind_command(ctx, "trends.compare")
    result = trends_service.trends_compare(app_ctx.paths, venue_a, venue_b, topic)
    _emit(app_ctx, result, {"topic": topic, "venues": [venue_a, venue_b]})
