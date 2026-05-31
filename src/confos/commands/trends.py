"""``confos trends`` — topic/compare. Stub until Phase 4."""

from typing import Annotated

import typer

from ..console import bind_command, global_output_options
from ..errors import NotImplementedYetError

app = typer.Typer(no_args_is_help=False, help="Track how topics move across venues/years.")


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
    """Show how a topic moves across a list of venues/years."""
    bind_command(ctx, "trends.topic")
    raise NotImplementedYetError("trends topic", phase="Phase 4")


@app.command()
@global_output_options
def compare(
    ctx: typer.Context,
    venue_a: Annotated[str, typer.Argument(help="First venue slug.")],
    venue_b: Annotated[str, typer.Argument(help="Second venue slug.")],
    topic: Annotated[str, typer.Option("--topic", help="Topic to compare head-to-head.")],
) -> None:
    """Compare a topic across two venues head-to-head."""
    bind_command(ctx, "trends.compare")
    raise NotImplementedYetError("trends compare", phase="Phase 4")
