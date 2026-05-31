"""``confos papers`` — search/show/related. Stub until Phase 2."""

from typing import Annotated

import typer

from ..console import bind_command, global_output_options
from ..errors import NotImplementedYetError

app = typer.Typer(no_args_is_help=False, help="Search and explore papers.")


@app.command()
@global_output_options
def search(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Full-text query over title, abstract, keywords.")],
    venue: Annotated[str | None, typer.Option("--venue", help="Limit to a venue slug.")] = None,
    year: Annotated[int | None, typer.Option("--year", help="Limit to a year.")] = None,
    org: Annotated[str | None, typer.Option("--org", help="Limit to an organisation.")] = None,
    accepted_only: Annotated[
        bool, typer.Option("--accepted-only", help="Only accepted papers (local filter).")
    ] = False,
) -> None:
    """Search papers by full text, ranked by relevance, with provenance."""
    bind_command(ctx, "papers.search")
    raise NotImplementedYetError("papers search", phase="Phase 2")


@app.command()
@global_output_options
def show(
    ctx: typer.Context,
    paper_id: Annotated[str, typer.Argument(help="OpenReview note id.")],
    with_: Annotated[
        str | None, typer.Option("--with", help="Comma-separated extras: authors,related,abstract.")
    ] = None,
) -> None:
    """Show a single paper, optionally with authors/related."""
    bind_command(ctx, "papers.show")
    raise NotImplementedYetError("papers show", phase="Phase 2")


@app.command()
@global_output_options
def related(
    ctx: typer.Context,
    paper_id: Annotated[str, typer.Argument(help="OpenReview note id.")],
) -> None:
    """Show papers related to a given paper (by title/keyword overlap)."""
    bind_command(ctx, "papers.related")
    raise NotImplementedYetError("papers related", phase="Phase 2")
