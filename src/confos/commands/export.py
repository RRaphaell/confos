"""``confos export`` — context packs (the headline agent artifact) + bulk CSV/JSONL."""

from collections.abc import Callable
from typing import Annotated, Any

import typer

from ..console import AppContext, bind_command, global_output_options
from ..errors import UsageError
from ..paths import Paths
from ..services import export as export_service
from ._render import validate_venue

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
    resolved_venue = venue or app_ctx.venue
    validate_venue(app_ctx, resolved_venue)
    pack = export_service.build_context_pack(app_ctx.paths, topic, venue=resolved_venue)
    query = {"topic": topic, "venue": resolved_venue}
    if format == "markdown" and not app_ctx.is_json:
        app_ctx.emit(export_service.context_pack_markdown(pack))
        return
    app_ctx.render_json(pack, query=query, venue=resolved_venue)


def _emit_bulk_export(
    app_ctx: AppContext,
    venue: str | None,
    fmt: str | None,
    rows_fn: Callable[[Paths, str | None], list[dict[str, Any]]],
    string_fn: Callable[..., str],
) -> None:
    """Shared body for ``export papers`` / ``export authors``.

    Honours ``--json`` (the agent contract — every command speaks JSON, CLI_CONTRACT §4)
    by emitting the row list in the standard envelope; otherwise ``--format`` csv/jsonl
    drives the bulk text dump. Combining ``--json`` with an explicit ``--format csv`` is a
    usage error rather than silently dropping one of them.
    """
    if fmt is not None and fmt not in ("csv", "jsonl"):
        raise UsageError(f"Unknown --format {fmt!r}.", hint="Use csv or jsonl.")
    resolved_venue = venue or app_ctx.venue
    validate_venue(app_ctx, resolved_venue)
    if app_ctx.is_json:
        if fmt == "csv":
            raise UsageError(
                "--json conflicts with --format csv.",
                hint="Use --json for the JSON envelope, or --format csv for CSV — not both.",
            )
        app_ctx.render_json(
            rows_fn(app_ctx.paths, resolved_venue),
            query={"venue": resolved_venue},
            venue=resolved_venue,
        )
        return
    app_ctx.emit(string_fn(app_ctx.paths, venue=resolved_venue, fmt=fmt or "csv"))


@app.command()
@global_output_options
def papers(
    ctx: typer.Context,
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
    format: Annotated[
        str | None,
        typer.Option("--format", help="Bulk format: csv (default) or jsonl. Ignored under --json."),
    ] = None,
) -> None:
    """Export papers as CSV or JSONL (or a JSON envelope under --json).

    Examples:
      confos export papers --venue neurips-2025 --format csv > papers.csv
      confos export papers --venue neurips-2025 --format jsonl
      confos export papers --venue neurips-2025 --json | jq '.data[].title'
    """
    app_ctx = bind_command(ctx, "export.papers")
    _emit_bulk_export(
        app_ctx, venue, format, export_service.paper_export_rows, export_service.export_papers
    )


@app.command()
@global_output_options
def authors(
    ctx: typer.Context,
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
    format: Annotated[
        str | None,
        typer.Option("--format", help="Bulk format: csv (default) or jsonl. Ignored under --json."),
    ] = None,
) -> None:
    """Export authors as CSV or JSONL (or a JSON envelope under --json).

    Examples:
      confos export authors --venue neurips-2025 --format csv > authors.csv
      confos export authors --venue neurips-2025 --format jsonl
      confos export authors --venue neurips-2025 --json | jq '.data[].display_name'
    """
    app_ctx = bind_command(ctx, "export.authors")
    _emit_bulk_export(
        app_ctx, venue, format, export_service.author_export_rows, export_service.export_authors
    )
