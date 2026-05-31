"""``confos index`` — rebuild/status. Stub until Phase 2."""

import typer

from ..console import bind_command, global_output_options
from ..errors import NotImplementedYetError

app = typer.Typer(no_args_is_help=False, help="Manage the derived SQLite index.")


@app.command()
@global_output_options
def rebuild(ctx: typer.Context) -> None:
    """Re-normalise from raw JSONL into a fresh index (no network)."""
    bind_command(ctx, "index.rebuild")
    raise NotImplementedYetError("index rebuild", phase="Phase 2")


@app.command()
@global_output_options
def status(ctx: typer.Context) -> None:
    """Show index status: tables, row counts, last ingest per venue."""
    bind_command(ctx, "index.status")
    raise NotImplementedYetError("index status", phase="Phase 2")
