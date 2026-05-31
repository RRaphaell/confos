"""``confos viz`` — terminal bar charts (topics/orgs) + co-authorship graph (network)."""

from typing import Annotated

import typer

from ..console import AppContext, bind_command, global_output_options
from ..errors import UsageError
from ..output.graph import to_html, to_mermaid
from ..output.plain import tsv_rows
from ..output.table import bar_chart, data_table
from ..services import stats as stats_service
from ..services import viz as viz_service
from ._render import resolve_limit

app = typer.Typer(no_args_is_help=False, help="Visualise the landscape (charts + graphs).")


def _bar_command(app_ctx: AppContext, result: dict[str, object], *, label: str) -> None:
    rows = result["rows"]
    assert isinstance(rows, list)
    if app_ctx.is_json:
        app_ctx.render_json(result, query={})
        return
    if app_ctx.is_plain:
        tsv_rows(app_ctx.out, [(r["key"], r["papers"]) for r in rows])
        return
    if not rows:
        app_ctx.out.print("No data to chart yet.")
        return
    bar_chart(app_ctx.out, [(str(r["key"]), int(r["papers"])) for r in rows], title=f"Top {label}")


@app.command()
@global_output_options
def topics(
    ctx: typer.Context,
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
) -> None:
    """Terminal bar chart of top topics."""
    app_ctx = bind_command(ctx, "viz.topics")
    resolved_venue = venue or app_ctx.venue
    limit = resolve_limit(None, app_ctx.limit, 20)
    result = stats_service.topics(app_ctx.paths, resolved_venue, limit=limit)
    _bar_command(app_ctx, result, label="topics")


@app.command()
@global_output_options
def orgs(
    ctx: typer.Context,
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
) -> None:
    """Terminal bar chart of top organisations."""
    app_ctx = bind_command(ctx, "viz.orgs")
    resolved_venue = venue or app_ctx.venue
    limit = resolve_limit(None, app_ctx.limit, 20)
    result = stats_service.orgs(app_ctx.paths, resolved_venue, limit=limit)
    _bar_command(app_ctx, result, label="organisations")


@app.command()
@global_output_options
def network(
    ctx: typer.Context,
    topic: Annotated[
        str, typer.Option("--topic", help="Topic to build the co-authorship graph for.")
    ],
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
    format: Annotated[
        str, typer.Option("--format", help="Output format: terminal, mermaid, or html.")
    ] = "terminal",
) -> None:
    """Co-authorship graph for a topic (terminal / mermaid / html).

    Examples:
      confos viz network --topic "agents" --venue neurips-2025 --format mermaid
      confos viz network --topic "agents" --format html > agents.html
    """
    app_ctx = bind_command(ctx, "viz.network")
    if format not in ("terminal", "mermaid", "html"):
        raise UsageError(f"Unknown --format {format!r}.", hint="Use terminal, mermaid, or html.")
    resolved_venue = venue or app_ctx.venue
    graph = viz_service.build_coauthor_graph(app_ctx.paths, topic, venue=resolved_venue)
    nodes = graph["nodes"]
    edges = graph["edges"]

    if app_ctx.is_json:
        app_ctx.render_json(
            graph, query={"topic": topic, "venue": resolved_venue, "format": format}
        )
        return
    if format == "mermaid":
        app_ctx.emit(to_mermaid(nodes, edges))
        return
    if format == "html":
        app_ctx.emit(to_html(f"confos co-authorship: {topic}", to_mermaid(nodes, edges)))
        return
    if not nodes:
        app_ctx.out.print(f"No co-authorship graph for topic {topic!r} (no matching papers).")
        return
    app_ctx.out.print(
        f"Co-authorship for [bold]{topic}[/bold]: {graph['node_count']} authors, "
        f"{graph['edge_count']} edges, from {graph['matched_papers']} matching paper(s)"
        + (" (truncated to top-degree nodes)" if graph["truncated"] else "")
    )
    data_table(
        app_ctx.out,
        ["author", "co-authors"],
        [(str(n["label"]), str(n["degree"])) for n in nodes[:15]],
        title="Most-connected authors",
    )
