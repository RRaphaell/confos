"""``confos export`` — context/papers/authors. Stub until Phase 5."""

from typing import Annotated

import typer

from ..console import bind_command, global_output_options
from ..errors import NotImplementedYetError

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
    """Build a self-contained, fully-cited context pack for a topic."""
    bind_command(ctx, "export.context")
    raise NotImplementedYetError("export context", phase="Phase 5")


@app.command()
@global_output_options
def papers(
    ctx: typer.Context,
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
    format: Annotated[str, typer.Option("--format", help="Output format: csv or jsonl.")] = "csv",
) -> None:
    """Export papers as CSV or JSONL."""
    bind_command(ctx, "export.papers")
    raise NotImplementedYetError("export papers", phase="Phase 5")


@app.command()
@global_output_options
def authors(
    ctx: typer.Context,
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
    format: Annotated[str, typer.Option("--format", help="Output format: csv or jsonl.")] = "csv",
) -> None:
    """Export authors as CSV or JSONL."""
    bind_command(ctx, "export.authors")
    raise NotImplementedYetError("export authors", phase="Phase 5")
