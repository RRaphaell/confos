"""``confos init`` — create the local store at ~/.confos (idempotent)."""

import typer

from ..console import bind_command
from ..db.connection import connect
from ..db.migrate import SCHEMA_VERSION, migrate
from ..output.plain import key_value_plain
from ..output.table import key_value_table


def run(ctx: typer.Context) -> None:
    """Create the local confos store (directories + SQLite schema).

    Idempotent: running it again on an existing store is a no-op. The store lives at
    ~/.confos by default (override with --home or $CONFOS_HOME).

    Examples:
      confos init
      confos --home /tmp/confos-demo init --json
    """
    app_ctx = bind_command(ctx, "init")
    paths = app_ctx.paths

    already = paths.exists()
    paths.ensure()
    conn = connect(paths.db)
    try:
        applied = migrate(conn)
    finally:
        conn.close()

    fresh = applied or not already
    data = {
        "home": str(paths.home),
        "db": str(paths.db),
        "schema_version": SCHEMA_VERSION,
        "created": fresh,
    }

    if app_ctx.is_json:
        app_ctx.render_json(data, query={"home": str(paths.home)}, sources=[])
        return
    if app_ctx.is_plain:
        key_value_plain(app_ctx.out, list(data.items()))
        return

    headline = "Initialised confos store:" if fresh else "confos store already initialised:"
    app_ctx.out.print(f"{headline} [bold]{paths.home}[/bold]")
    key_value_table(
        app_ctx.out,
        [
            ("home", str(paths.home)),
            ("database", str(paths.db)),
            ("schema version", str(SCHEMA_VERSION)),
        ],
    )
    app_ctx.info('Next: `confos venues search "NeurIPS 2025"`, then `confos ingest <slug>`.')
