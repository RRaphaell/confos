"""``confos index`` — rebuild the derived index from raw JSONL (no network) + status."""

import typer

from ..console import bind_command, global_output_options
from ..output.plain import key_value_plain
from ..output.table import data_table, key_value_table
from ..services import index as index_service

app = typer.Typer(no_args_is_help=False, help="Manage the derived SQLite index.")


@app.command()
@global_output_options
def rebuild(ctx: typer.Context) -> None:
    """Re-normalise from raw JSONL into a fresh index (no network).

    Drops the derived tables and re-derives papers/authors/orgs/FTS from the raw
    snapshots; sync watermarks are preserved. Run this after editing alias files
    (topics.yml / orgs.yml / countries.yml) so the new mappings take effect.

    Examples:
      confos index rebuild
      confos index rebuild --json
    """
    app_ctx = bind_command(ctx, "index.rebuild")
    app_ctx.info("Rebuilding index from raw JSONL …")
    result = index_service.rebuild(app_ctx.paths)
    if app_ctx.is_json:
        app_ctx.render_json(result, query={})
        return
    if app_ctx.is_plain:
        key_value_plain(
            app_ctx.out,
            [
                ("venues", result["venues"]),
                ("papers", result["papers"]),
                ("failed", result["failed"]),
            ],
        )
        return
    app_ctx.out.print(
        f"Rebuilt index: [bold]{result['papers']}[/bold] paper(s) "
        f"across {result['venues']} venue(s)."
    )
    if result["failed"]:
        app_ctx.warn(f"{result['failed']} raw note(s) failed to normalize and were skipped.")


@app.command()
@global_output_options
def status(ctx: typer.Context) -> None:
    """Show index status: table row counts and per-venue paper counts.

    Examples:
      confos index status
      confos index status --json
    """
    app_ctx = bind_command(ctx, "index.status")
    result = index_service.status(app_ctx.paths)
    if app_ctx.is_json:
        app_ctx.render_json(result, query={})
        return
    if app_ctx.is_plain:
        key_value_plain(app_ctx.out, list(result["counts"].items()))
        return
    key_value_table(
        app_ctx.out,
        [(table, str(count)) for table, count in result["counts"].items()],
        title="Index row counts",
    )
    if result["venues"]:
        data_table(
            app_ctx.out,
            ["venue", "papers", "last ingested"],
            [(v["slug"], str(v["papers"]), v["last_ingested_at"] or "—") for v in result["venues"]],
            title="Venues",
        )
