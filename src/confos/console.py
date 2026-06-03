"""Runtime context + stdout/stderr discipline.

The single most important contract in confos is the channel split (CLI_CONTRACT §4):

* **stdout** carries the requested *data* and nothing else — under ``--json`` it is
  valid JSON with no log lines mixed in.
* **stderr** carries progress, warnings and diagnostics.

:class:`AppContext` is the resolved global state for one CLI invocation. It is built
once in the typer callback, stashed on ``ctx.obj``, and threaded into every command.
Putting it here (a leaf module) keeps ``commands/`` and ``cli.py`` free of import
cycles.
"""

from __future__ import annotations

import functools
import inspect
import os
import sys
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.theme import Theme

from .config import Config
from .errors import ConfosError, UsageError
from .output import json as jsonout
from .paths import Paths


class OutputMode(StrEnum):
    """Mutually exclusive rendering modes (CLI_CONTRACT §3)."""

    HUMAN = "human"
    JSON = "json"
    PLAIN = "plain"


def should_use_color(no_color_flag: bool, *, stream_is_tty: bool) -> bool:
    """Resolve colour per the contract: ``--no-color`` / ``NO_COLOR`` / ``TERM=dumb`` / non-TTY."""
    if no_color_flag:
        return False
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return stream_is_tty


def should_use_unicode(*, stream: Any = None) -> bool:
    """Whether to render Unicode glyphs (block bars, sparklines, box borders).

    Deliberately *separate* from colour: a no-colour TTY still draws block glyphs fine,
    but ``TERM=dumb``, an opt-out (``CONFOS_ASCII``), or a non-UTF-8 stream cannot — degrade
    to ASCII then. See VISUAL.md §2.2.
    """
    if os.environ.get("CONFOS_ASCII"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    target = stream if stream is not None else sys.stdout
    encoding = (getattr(target, "encoding", None) or "").lower()
    return "utf" in encoding


@dataclass
class AppContext:
    """Everything a command needs about the current invocation."""

    mode: OutputMode
    quiet: bool
    verbose: int
    no_input: bool
    use_color: bool
    use_unicode: bool
    supports_hyperlinks: bool
    paths: Paths
    config: Config
    venue: str | None
    limit: int | None
    out: Console
    err: Console
    command: str = "confos"

    # --- machine output (stdout) --------------------------------------------
    def emit(self, text: str) -> None:
        """Write a verbatim line to stdout — bypasses rich so JSON/TSV stays exact."""
        self.out.file.write(text + "\n")
        self.out.file.flush()

    def render_json(
        self,
        data: Any,
        *,
        query: dict[str, Any],
        sources: list[str] | None = None,
        venue: str | None = None,
        warnings: list[str] | None = None,
        ok: bool = True,
    ) -> None:
        """Emit the standard data envelope for the current command (SCHEMAS §1)."""
        provenance = jsonout.make_provenance(self._db_display(), sources=sources, venue=venue)
        envelope = jsonout.success_envelope(
            self.command, query, data, provenance=provenance, warnings=warnings, ok=ok
        )
        self.emit(jsonout.dumps(envelope))

    def render_error(self, error: ConfosError, *, exc: BaseException | None = None) -> None:
        """Render an error to the right channel: JSON envelope, or a clean stderr line."""
        if self.is_json:
            self.emit(jsonout.dumps(jsonout.error_envelope(self.command, error)))
        else:
            label = "[red]error:[/red]" if self.use_color else "error:"
            self.err.print(f"{label} {error.message}")
            if error.hint:
                hint = f"[dim]hint:[/dim] {error.hint}" if self.use_color else f"hint: {error.hint}"
                self.err.print(hint)
        if exc is not None and self.verbose >= 2:
            self.err.print("".join(traceback.format_exception(exc)))

    def _db_display(self) -> str:
        """Path to the DB for provenance, abbreviated to ``~`` when under home."""
        db = self.paths.db
        try:
            return f"~/{db.relative_to(os.path.expanduser('~'))}"
        except ValueError:
            return str(db)

    # --- diagnostics (stderr) ------------------------------------------------
    def info(self, message: str) -> None:
        """Non-essential progress; suppressed by ``--quiet``."""
        if not self.quiet:
            self.err.print(f"[dim]{message}[/dim]" if self.use_color else message)

    def warn(self, message: str) -> None:
        """A non-fatal warning; always shown (it matters even when quiet)."""
        self.err.print(
            f"[yellow]warning:[/yellow] {message}" if self.use_color else f"warning: {message}"
        )

    def debug(self, message: str) -> None:
        """Shown at ``-v`` and above."""
        if self.verbose >= 1:
            self.err.print(
                f"[dim]debug: {message}[/dim]" if self.use_color else f"debug: {message}"
            )

    def trace(self, message: str) -> None:
        """Shown at ``-vv`` and above."""
        if self.verbose >= 2:
            self.err.print(
                f"[dim]trace: {message}[/dim]" if self.use_color else f"trace: {message}"
            )

    @property
    def is_json(self) -> bool:
        return self.mode is OutputMode.JSON

    @property
    def is_plain(self) -> bool:
        return self.mode is OutputMode.PLAIN


def confos_theme() -> Theme:
    """The single colour vocabulary (VISUAL.md §2.1).

    Named styles so call sites express *meaning* (``[status.oral]``, ``[dq.high]``) rather
    than raw colours, and so everything collapses to plain text automatically under
    ``no_color`` / ``NO_COLOR`` / a dumb terminal.
    """
    return Theme(
        {
            "confos.success": "green",
            "confos.warn": "yellow",
            "confos.error": "bold red",
            "confos.muted": "dim",
            # Branded truecolor palette (violet primary + teal secondary). Rich coerces hex to
            # the nearest 256/ANSI colour on lesser terminals and strips it under no-colour.
            "confos.accent": "bold #a78bfa",  # violet — primary
            "confos.accent2": "#2dd4bf",  # teal — secondary
            "confos.heading": "bold #c4b5fd",  # section headers (lighter violet)
            "confos.brand": "bold #a78bfa",
            "confos.bar": "#a78bfa",  # violet bar fill
            "confos.bar2": "#2dd4bf",  # teal bar fill
            "confos.count": "bold",
            "status.oral": "bold magenta",
            "status.spotlight": "magenta",
            "status.poster": "cyan",
            "status.accepted": "green",
            "status.active": "yellow",
            "status.rejected": "dim red",
            "status.withdrawn": "dim",
            "dq.high": "green",
            "dq.med": "yellow",
            "dq.low": "red",
            "score.hi": "bold",
            "score.lo": "dim",
        }
    )


def build_consoles(use_color: bool) -> tuple[Console, Console]:
    """Create (stdout, stderr) consoles honouring the resolved colour decision.

    Both carry :func:`confos_theme` so ``[status.*]`` / ``[dq.*]`` markup resolves
    everywhere; ``no_color`` strips the colour while leaving the text intact.
    """
    theme = confos_theme()
    out = Console(no_color=not use_color, highlight=False, soft_wrap=False, theme=theme)
    err = Console(stderr=True, no_color=not use_color, highlight=False, theme=theme)
    return out, err


def stream_is_tty(stream: Any = None) -> bool:
    """Whether stdout is an interactive terminal (used for colour + prompt gating)."""
    target = stream if stream is not None else sys.stdout
    try:
        return bool(target.isatty())
    except (AttributeError, ValueError):
        return False


def bind_command(typer_ctx: typer.Context, command: str) -> AppContext:
    """Fetch the :class:`AppContext` off the typer context and stamp the command name.

    Every command calls this first so both success and error envelopes carry the right
    dotted ``command`` (e.g. ``papers.search``).
    """
    ctx = typer_ctx.obj
    if not isinstance(ctx, AppContext):  # pragma: no cover - defensive
        raise RuntimeError("AppContext was not initialised by the CLI callback.")
    ctx.command = command
    return ctx


# --- global output flags, usable AFTER the subcommand ------------------------
# The docs (AGENTS.md, PRODUCT, README) put --json/--quiet/etc. after the command
# (e.g. `confos doctor --json`). typer only parses group options *before* the
# subcommand, so we inject these flags onto every command and OR-merge them into the
# base AppContext built by the root callback. That makes both positions work:
# `confos --json doctor` and `confos doctor --json`.

_GLOBAL_FLAG_NAMES = ("g_json", "g_plain", "g_quiet", "g_verbose", "g_no_input", "g_no_color")


def _global_output_parameters() -> list[inspect.Parameter]:
    kw = inspect.Parameter.KEYWORD_ONLY
    mk = inspect.Parameter
    return [
        mk(
            "g_json",
            kw,
            default=False,
            annotation=Annotated[
                bool, typer.Option("--json", help="Emit stable JSON to stdout (and only JSON).")
            ],
        ),
        mk(
            "g_plain",
            kw,
            default=False,
            annotation=Annotated[
                bool, typer.Option("--plain", help="Best-effort line/TSV output for scripts.")
            ],
        ),
        mk(
            "g_quiet",
            kw,
            default=False,
            annotation=Annotated[
                bool, typer.Option("--quiet", "-q", help="Suppress non-essential stderr.")
            ],
        ),
        mk(
            "g_verbose",
            kw,
            default=0,
            annotation=Annotated[
                int,
                typer.Option(
                    "--verbose", "-v", count=True, help="More diagnostics on stderr (repeatable)."
                ),
            ],
        ),
        mk(
            "g_no_input",
            kw,
            default=False,
            annotation=Annotated[
                bool, typer.Option("--no-input", help="Never prompt; fail if input is required.")
            ],
        ),
        mk(
            "g_no_color",
            kw,
            default=False,
            annotation=Annotated[bool, typer.Option("--no-color", help="Disable colour output.")],
        ),
    ]


def merge_global_flags(
    ctx: AppContext,
    *,
    g_json: bool,
    g_plain: bool,
    g_quiet: bool,
    g_verbose: int,
    g_no_input: bool,
    g_no_color: bool,
) -> None:
    """OR-merge command-level global flags into the base context."""
    effective_json = g_json or ctx.mode is OutputMode.JSON
    effective_plain = g_plain or ctx.mode is OutputMode.PLAIN
    if effective_json and effective_plain:
        raise UsageError(
            "--json and --plain are mutually exclusive.",
            hint="Pick one output mode (default human, or --json, or --plain).",
        )
    if effective_json:
        ctx.mode = OutputMode.JSON
    elif effective_plain:
        ctx.mode = OutputMode.PLAIN
    ctx.quiet = ctx.quiet or g_quiet
    # max, not sum: a single -v in each of the two valid positions must not become -vv.
    ctx.verbose = max(ctx.verbose, g_verbose)
    ctx.no_input = ctx.no_input or g_no_input
    if g_no_color and ctx.use_color:
        ctx.use_color = False
        ctx.out, ctx.err = build_consoles(False)


def global_output_options(func: Callable[..., None]) -> Callable[..., None]:
    """Decorator: add the shared output/behaviour flags to a command.

    Applied at each ``@app.command()`` site (inner decorator). It appends the global
    flags to the command's signature so typer parses them after the subcommand, then
    merges them into the :class:`AppContext` before the command body runs.
    """
    orig_sig = inspect.signature(func)
    orig_params = list(orig_sig.parameters.values())
    ctx_name = next((p.name for p in orig_params if p.annotation is typer.Context), None)
    extra = _global_output_parameters()

    @functools.wraps(func)
    def wrapper(**kwargs: Any) -> None:
        flags = {name: kwargs.pop(name) for name in _GLOBAL_FLAG_NAMES}
        if ctx_name is not None:
            typer_ctx = kwargs[ctx_name]
            if isinstance(typer_ctx.obj, AppContext):
                merge_global_flags(typer_ctx.obj, **flags)
        func(**kwargs)

    wrapper.__signature__ = orig_sig.replace(parameters=orig_params + extra)  # type: ignore[attr-defined]
    wrapper.__annotations__ = {**func.__annotations__, **{p.name: p.annotation for p in extra}}
    return wrapper
