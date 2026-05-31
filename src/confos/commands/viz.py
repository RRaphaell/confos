"""``confos viz`` — topics/orgs/network. Stub until Phase 4."""

from typing import Annotated

import typer

from ..console import bind_command, global_output_options
from ..errors import NotImplementedYetError

app = typer.Typer(no_args_is_help=False, help="Visualise the landscape (charts + graphs).")


@app.command()
@global_output_options
def topics(
    ctx: typer.Context,
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
) -> None:
    """Terminal bar chart of top topics."""
    bind_command(ctx, "viz.topics")
    raise NotImplementedYetError("viz topics", phase="Phase 4")


@app.command()
@global_output_options
def orgs(
    ctx: typer.Context,
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
) -> None:
    """Terminal bar chart of top organisations."""
    bind_command(ctx, "viz.orgs")
    raise NotImplementedYetError("viz orgs", phase="Phase 4")


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
    """Co-authorship graph for a topic (terminal / mermaid / html)."""
    bind_command(ctx, "viz.network")
    raise NotImplementedYetError("viz network", phase="Phase 4")
