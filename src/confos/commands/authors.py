"""``confos authors`` — find/search/show/papers/coauthors. Stub until Phase 2/3."""

from typing import Annotated

import typer

from ..console import bind_command, global_output_options
from ..errors import NotImplementedYetError

app = typer.Typer(no_args_is_help=False, help="Find and explore authors.")


@app.command()
@global_output_options
def find(
    ctx: typer.Context,
    topic: Annotated[str, typer.Option("--topic", help="Topic to rank authors by.")],
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
) -> None:
    """Rank the people actually publishing on a topic, with why-relevant + provenance."""
    bind_command(ctx, "authors.find")
    raise NotImplementedYetError("authors find", phase="Phase 3")


@app.command()
@global_output_options
def search(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Author name to search for.")],
) -> None:
    """Search authors by name."""
    bind_command(ctx, "authors.search")
    raise NotImplementedYetError("authors search", phase="Phase 2")


@app.command()
@global_output_options
def show(
    ctx: typer.Context,
    author_id: Annotated[str, typer.Argument(help="Profile id (or email:/name: fallback).")],
) -> None:
    """Show a single author's profile and headline stats."""
    bind_command(ctx, "authors.show")
    raise NotImplementedYetError("authors show", phase="Phase 2")


@app.command()
@global_output_options
def papers(
    ctx: typer.Context,
    author_id: Annotated[str, typer.Argument(help="Profile id (or email:/name: fallback).")],
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
) -> None:
    """List an author's papers."""
    bind_command(ctx, "authors.papers")
    raise NotImplementedYetError("authors papers", phase="Phase 2")


@app.command()
@global_output_options
def coauthors(
    ctx: typer.Context,
    author_id: Annotated[str, typer.Argument(help="Profile id (or email:/name: fallback).")],
) -> None:
    """List an author's co-authors, ranked by shared papers."""
    bind_command(ctx, "authors.coauthors")
    raise NotImplementedYetError("authors coauthors", phase="Phase 3")
