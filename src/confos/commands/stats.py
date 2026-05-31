"""``confos stats`` — overview/topics/orgs/countries. Stub until Phase 3."""

from typing import Annotated

import typer

from ..console import bind_command, global_output_options
from ..errors import NotImplementedYetError

app = typer.Typer(no_args_is_help=False, help="Aggregate statistics (honest about uncertainty).")


@app.command()
@global_output_options
def overview(
    ctx: typer.Context,
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
) -> None:
    """High-level counts for a venue (papers, authors, orgs, status mix)."""
    bind_command(ctx, "stats.overview")
    raise NotImplementedYetError("stats overview", phase="Phase 3")


@app.command()
@global_output_options
def topics(
    ctx: typer.Context,
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
) -> None:
    """Top topics (normalised keywords) with coverage."""
    bind_command(ctx, "stats.topics")
    raise NotImplementedYetError("stats topics", phase="Phase 3")


@app.command()
@global_output_options
def orgs(
    ctx: typer.Context,
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
) -> None:
    """Top organisations with data-quality reporting."""
    bind_command(ctx, "stats.orgs")
    raise NotImplementedYetError("stats orgs", phase="Phase 3")


@app.command()
@global_output_options
def countries(
    ctx: typer.Context,
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
    explain: Annotated[
        bool, typer.Option("--explain", help="Show known/unknown/low-confidence counts and method.")
    ] = False,
) -> None:
    """Country distribution, with explicit known/unknown counts."""
    bind_command(ctx, "stats.countries")
    raise NotImplementedYetError("stats countries", phase="Phase 3")
