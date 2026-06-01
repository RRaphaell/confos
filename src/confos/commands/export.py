"""``confos export`` — context packs (the headline agent artifact) + bulk CSV/JSONL."""

from typing import Annotated

import typer

from ..console import bind_command, global_output_options
from ..errors import UsageError
from ..services import export as export_service

app = typer.Typer(
    no_args_is_help=False, help="Export context packs and bulk data (built for agents)."
)


@app.command()
@global_output_options
def context(
    ctx: typer.Context,
    topic: Annotated[str, typer.Option("--topic", help="Topic for the context pack.")],
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
    format: Annotated[
        str, typer.Option("--format", help="Output format: json or markdown.")
    ] = "json",
) -> None:
    """Build a self-contained, fully-cited context pack for a topic.

    The pack bundles top papers, ranked people, orgs, topic-scoped stats, and (heuristic)
    thin areas — everything an agent needs to plan a literature review, with every claim
    cited. v1 is LLM-free.

    Examples:
      confos export context --topic "agent evals" --venue neurips-2025 --json
      confos export context --topic "agent evals" --venue neurips-2025 --format markdown
    """
    app_ctx = bind_command(ctx, "export.context")
    if format not in ("json", "markdown"):
        raise UsageError(f"Unknown --format {format!r}.", hint="Use json or markdown.")
    pack = export_service.build_context_pack(app_ctx.paths, topic, venue=venue or app_ctx.venue)
    query = {"topic": topic, "venue": venue or app_ctx.venue}
    if format == "markdown" and not app_ctx.is_json:
        app_ctx.emit(export_service.context_pack_markdown(pack))
        return
    app_ctx.render_json(pack, query=query, venue=venue or app_ctx.venue)


@app.command()
@global_output_options
def papers(
    ctx: typer.Context,
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
    format: Annotated[str, typer.Option("--format", help="Output format: csv or jsonl.")] = "csv",
) -> None:
    """Export papers as CSV or JSONL.

    Examples:
      confos export papers --venue neurips-2025 --format csv > papers.csv
      confos export papers --venue neurips-2025 --format jsonl
    """
    app_ctx = bind_command(ctx, "export.papers")
    if format not in ("csv", "jsonl"):
        raise UsageError(f"Unknown --format {format!r}.", hint="Use csv or jsonl.")
    resolved_venue = venue or app_ctx.venue
    app_ctx.emit(export_service.export_papers(app_ctx.paths, venue=resolved_venue, fmt=format))


@app.command()
@global_output_options
def authors(
    ctx: typer.Context,
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
    format: Annotated[str, typer.Option("--format", help="Output format: csv or jsonl.")] = "csv",
) -> None:
    """Export authors as CSV or JSONL.

    Examples:
      confos export authors --venue neurips-2025 --format csv > authors.csv
      confos export authors --venue neurips-2025 --format jsonl
    """
    app_ctx = bind_command(ctx, "export.authors")
    if format not in ("csv", "jsonl"):
        raise UsageError(f"Unknown --format {format!r}.", hint="Use csv or jsonl.")
    resolved_venue = venue or app_ctx.venue
    app_ctx.emit(export_service.export_authors(app_ctx.paths, venue=resolved_venue, fmt=format))
