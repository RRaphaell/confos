"""``confos schema <command>`` — print the JSON schema of a command's output.

Stub until Phase 5.
"""

from typing import Annotated

import typer

from ..console import bind_command
from ..errors import NotImplementedYetError


def run(
    ctx: typer.Context,
    command: Annotated[
        str, typer.Argument(help="Command to describe, e.g. papers.search or export.context.")
    ],
) -> None:
    """Print the JSON schema for a command's --json output (versioned contract).

    Examples:
      confos schema papers.search
      confos schema export.context
    """
    bind_command(ctx, "schema")
    raise NotImplementedYetError("schema", phase="Phase 5")
