"""``confos ingest <venue>`` — pull a venue into the local store (network).

Stub until Phase 1. There is no separate ``sync`` command: re-running ``ingest``
performs the incremental update via stored watermarks (D6); ``--force`` does a full
re-pull.
"""

from typing import Annotated

import typer

from ..console import bind_command
from ..errors import NotImplementedYetError


def run(
    ctx: typer.Context,
    venue: Annotated[str, typer.Argument(help="Venue slug to ingest, e.g. neurips-2025.")],
    include_decisions: Annotated[
        bool,
        typer.Option("--include-decisions", help="Also fetch Decision notes (acceptance type)."),
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", help="Ignore sync watermarks and do a full re-pull.")
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Report would-fetch/insert/update counts; write nothing."),
    ] = False,
) -> None:
    """Pull a venue's full submission set into the local store (network).

    Status is derived locally from each note's raw venueid (ARCHITECTURE §8), so
    --accepted-only is a read-time filter, not an ingest option.

    Examples:
      confos ingest neurips-2025
      confos ingest neurips-2025 --force
    """
    bind_command(ctx, "ingest")
    raise NotImplementedYetError("ingest", phase="Phase 1")
