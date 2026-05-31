"""``confos orgs`` — top/papers. Stub until Phase 2/3."""

from typing import Annotated

import typer

from ..console import bind_command, global_output_options
from ..errors import NotImplementedYetError

app = typer.Typer(no_args_is_help=False, help="Explore organisations.")


@app.command()
@global_output_options
def top(
    ctx: typer.Context,
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
) -> None:
    """Rank organisations by paper count (with data-quality reporting)."""
    bind_command(ctx, "orgs.top")
    raise NotImplementedYetError("orgs top", phase="Phase 3")


@app.command()
@global_output_options
def papers(
    ctx: typer.Context,
    org: Annotated[str, typer.Argument(help="Organisation name, e.g. 'Google DeepMind'.")],
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
) -> None:
    """List papers affiliated with an organisation."""
    bind_command(ctx, "orgs.papers")
    raise NotImplementedYetError("orgs papers", phase="Phase 2")
