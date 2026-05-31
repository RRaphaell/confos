"""``confos venues`` — list/search/show/add venues, show alias map. Stub until Phase 1."""

from typing import Annotated

import typer

from ..console import bind_command, global_output_options
from ..errors import NotImplementedYetError

app = typer.Typer(no_args_is_help=False, help="List, search, and register venues.")


@app.command("list")
@global_output_options
def list_(ctx: typer.Context) -> None:
    """List known and locally-ingested venues (offline)."""
    bind_command(ctx, "venues.list")
    raise NotImplementedYetError("venues list", phase="Phase 1")


@app.command()
@global_output_options
def search(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Venue query, e.g. 'NeurIPS 2025'.")],
) -> None:
    """Find a venue on OpenReview (network)."""
    bind_command(ctx, "venues.search")
    raise NotImplementedYetError("venues search", phase="Phase 1")


@app.command()
@global_output_options
def show(
    ctx: typer.Context,
    slug: Annotated[str, typer.Argument(help="Venue slug, e.g. neurips-2025.")],
) -> None:
    """Show details for a known venue."""
    bind_command(ctx, "venues.show")
    raise NotImplementedYetError("venues show", phase="Phase 1")


@app.command()
@global_output_options
def add(
    ctx: typer.Context,
    slug: Annotated[str, typer.Option("--slug", help="Local handle for the venue.")],
    openreview_id: Annotated[
        str,
        typer.Option(
            "--openreview-id", help="OpenReview venue id, e.g. NeurIPS.cc/2025/Conference."
        ),
    ],
) -> None:
    """Register a custom venue by its OpenReview id (local-write)."""
    bind_command(ctx, "venues.add")
    raise NotImplementedYetError("venues add", phase="Phase 1")


@app.command()
@global_output_options
def aliases(ctx: typer.Context) -> None:
    """Show the built-in venue alias map."""
    bind_command(ctx, "venues.aliases")
    raise NotImplementedYetError("venues aliases", phase="Phase 1")
