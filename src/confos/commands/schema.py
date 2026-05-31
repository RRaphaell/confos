"""``confos schema <command>`` — print the output contract for a command's --json."""

import json
from typing import Annotated

import typer

from ..console import bind_command
from ..errors import UsageError
from ..schemas import SCHEMA_VERSION, available_commands, schema_for


def run(
    ctx: typer.Context,
    command: Annotated[
        str, typer.Argument(help="Command to describe, e.g. papers.search or export.context.")
    ],
) -> None:
    """Print the JSON output contract for a command (versioned; field names are stable).

    Examples:
      confos schema papers.search
      confos schema export.context
    """
    app_ctx = bind_command(ctx, "schema")
    schema = schema_for(command)
    if schema is None:
        raise UsageError(
            f"No schema for {command!r}.",
            hint="Available: " + ", ".join(available_commands()),
        )
    payload = {"command": command, "schema_version": SCHEMA_VERSION, **schema}
    if app_ctx.is_json:
        app_ctx.render_json(payload, query={"command": command}, sources=[])
        return
    # plain/human: the schema itself is the artifact — pretty JSON to stdout.
    app_ctx.emit(json.dumps(payload, indent=2, ensure_ascii=False))
