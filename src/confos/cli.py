"""confos command-line entry point.

Builds the typer app, resolves global flags into an :class:`AppContext`, wires every
command group, and maps exceptions to the stable exit codes (CLI_CONTRACT §5). This
module deliberately avoids ``from __future__ import annotations`` so that typer can
introspect the ``Annotated[...]`` option types at runtime.
"""

import os
import sys
from contextvars import ContextVar
from pathlib import Path
from typing import Annotated

import typer

from . import __version__
from ._clickcompat import ClickAbort, ClickExit, ClickUsageError
from .commands import (
    authors,
    doctor,
    export,
    index,
    ingest,
    init,
    orgs,
    papers,
    schema,
    stats,
    trends,
    venues,
    viz,
)
from .config import load_config
from .console import (
    AppContext,
    OutputMode,
    build_consoles,
    global_output_options,
    should_use_color,
    stream_is_tty,
)
from .errors import EXIT_INTERRUPTED, EXIT_OK, EXIT_USAGE, ConfosError, UsageError
from .output import json as jsonout
from .paths import Paths

# The active context for the current invocation, so the top-level error handler can
# render failures in the right mode even when the failure happens mid-command.
_ACTIVE: ContextVar[AppContext | None] = ContextVar("confos_active_context", default=None)

app = typer.Typer(
    name="confos",
    help="Conference intelligence in your terminal — for humans and agents.",
    no_args_is_help=True,
    add_completion=False,  # CLI_CONTRACT §3 doesn't promise completion flags
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"confos {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    ctx: typer.Context,
    json_: Annotated[
        bool, typer.Option("--json", help="Emit stable JSON to stdout (and only JSON).")
    ] = False,
    plain: Annotated[
        bool, typer.Option("--plain", help="Best-effort line/TSV output for scripts.")
    ] = False,
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Suppress non-essential stderr.")
    ] = False,
    verbose: Annotated[
        int,
        typer.Option(
            "--verbose", "-v", count=True, help="More diagnostics on stderr (repeatable)."
        ),
    ] = 0,
    no_input: Annotated[
        bool, typer.Option("--no-input", help="Never prompt; fail if input is required.")
    ] = False,
    no_color: Annotated[
        bool,
        typer.Option(
            "--no-color", help="Disable colour (also honours NO_COLOR / TERM=dumb / non-TTY)."
        ),
    ] = False,
    home: Annotated[
        str | None,
        typer.Option(
            "--home",
            metavar="PATH",
            help="Override the data dir (else $CONFOS_HOME else ~/.confos).",
        ),
    ] = None,
    venue: Annotated[
        str | None,
        typer.Option("--venue", metavar="SLUG", help="Default venue for the command."),
    ] = None,
    limit: Annotated[
        int | None, typer.Option("--limit", metavar="N", help="Cap result count.")
    ] = None,
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_version_callback, is_eager=True, help="Print version and exit."
        ),
    ] = False,
) -> None:
    """Set up global state shared by every command."""
    use_color = should_use_color(no_color, stream_is_tty=stream_is_tty())
    out, err = build_consoles(use_color)

    if json_ and plain:
        raise UsageError(
            "--json and --plain are mutually exclusive.",
            hint="Pick one output mode (default human, or --json, or --plain).",
        )
    mode = OutputMode.JSON if json_ else OutputMode.PLAIN if plain else OutputMode.HUMAN

    if limit is not None and limit < 0:
        raise UsageError("--limit must be >= 0.")

    paths = Paths.resolve(home)
    config_env = os.environ.get("CONFOS_CONFIG")
    config_path = Path(config_env) if config_env else paths.config
    config = load_config(config_path)

    resolved_venue = venue if venue is not None else config.default_venue

    app_ctx = AppContext(
        mode=mode,
        quiet=quiet,
        verbose=verbose,
        no_input=no_input,
        use_color=use_color,
        paths=paths,
        config=config,
        venue=resolved_venue,
        limit=limit,
        out=out,
        err=err,
    )
    ctx.obj = app_ctx
    _ACTIVE.set(app_ctx)


# --- command registration ----------------------------------------------------
app.command("init")(global_output_options(init.run))
app.command("doctor")(global_output_options(doctor.run))
app.command("ingest")(global_output_options(ingest.run))
app.command("schema")(global_output_options(schema.run))
app.add_typer(venues.app, name="venues")
app.add_typer(papers.app, name="papers")
app.add_typer(authors.app, name="authors")
app.add_typer(orgs.app, name="orgs")
app.add_typer(stats.app, name="stats")
app.add_typer(trends.app, name="trends")
app.add_typer(viz.app, name="viz")
app.add_typer(export.app, name="export")
app.add_typer(index.app, name="index")


# --- error handling + entry point --------------------------------------------
def _wants_json() -> bool:
    """Whether output should be JSON — from the active context, OR by sniffing argv.

    The argv sniff is not just a pre-context fallback: a command-level ``--json`` (the
    documented agent form, ``papers search ... --json``) is only merged into the context
    *after* successful arg parsing. On a parse/usage error the command body never runs, so
    the context still reads HUMAN — we must fall back to argv so the error stays pure JSON.
    """
    ctx = _ACTIVE.get()
    if ctx is not None and ctx.is_json:
        return True
    return "--json" in sys.argv


def _emit_json_error(command: str, error: ConfosError) -> None:
    """Write an error envelope to stdout (keeps stdout pure JSON under --json)."""
    text = jsonout.dumps(jsonout.error_envelope(command, error))
    ctx = _ACTIVE.get()
    if ctx is not None:
        ctx.emit(text)
    else:
        sys.stdout.write(text + "\n")


def _render_confos_error(exc: ConfosError, *, original: BaseException | None = None) -> None:
    """Render a ConfosError to the right channel (JSON envelope or clean stderr line)."""
    ctx = _ACTIVE.get()
    if ctx is not None:
        ctx.render_error(exc, exc=original)
        return
    # Pre-context failure (e.g. bad global flags): infer mode from argv.
    if _wants_json():
        _emit_json_error("confos", exc)
    else:
        sys.stderr.write(f"error: {exc.message}\n")
        if exc.hint:
            sys.stderr.write(f"hint: {exc.hint}\n")


def _render_click_usage_error(exc: ClickUsageError) -> int:
    """Render a click parse/usage error (unknown option, missing arg, bare group).

    Under --json this stays pure JSON on stdout — click's own ``show()`` would
    otherwise leak Usage/help text (sometimes to stdout) and break agents. Returns the
    exit code to use.
    """
    code = exc.exit_code if isinstance(getattr(exc, "exit_code", None), int) else EXIT_USAGE
    ctx = _ACTIVE.get()
    command = ctx.command if ctx is not None else "confos"
    if _wants_json():
        usage = UsageError((exc.format_message() or "missing command or argument").strip())
        usage.exit_code = code
        _emit_json_error(command, usage)
    else:
        exc.show()
    return code


def main() -> None:
    """Console-script entry point: run the app and map outcomes to exit codes."""
    _ACTIVE.set(None)
    try:
        result = app(prog_name="confos", standalone_mode=False)
    except ConfosError as exc:
        _render_confos_error(exc)
        sys.exit(exc.exit_code)
    except (KeyboardInterrupt, ClickAbort, typer.Abort):
        sys.stderr.write("\ninterrupted\n")
        sys.exit(EXIT_INTERRUPTED)
    except ClickUsageError as exc:
        sys.exit(_render_click_usage_error(exc))
    except (typer.Exit, ClickExit) as exc:
        sys.exit(int(getattr(exc, "exit_code", 0)))
    except SystemExit as exc:
        sys.exit(exc.code if isinstance(exc.code, int) else EXIT_OK)
    except Exception as exc:
        # Last resort: never dump a raw traceback by default. The traceback is genuinely
        # useful for an unexpected crash, so attach it at -vv.
        wrapped = ConfosError(f"unexpected error: {exc}")
        _render_confos_error(wrapped, original=exc)
        sys.exit(wrapped.exit_code)
    else:
        # typer intercepts KeyboardInterrupt and, in non-standalone mode, *returns*
        # Exit(130) as an int rather than re-raising — so the interrupt never reaches
        # the except branch above. Emit the message here so Ctrl-C isn't silent.
        code = result if isinstance(result, int) else EXIT_OK
        if code == EXIT_INTERRUPTED:
            sys.stderr.write("\ninterrupted\n")
        sys.exit(code)


if __name__ == "__main__":  # pragma: no cover
    main()
