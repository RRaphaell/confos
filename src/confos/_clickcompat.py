"""Compatibility shim for click's exception classes.

typer >= 0.16 vendors click as ``typer._click``; earlier typer depends on the
external ``click`` package. ``standalone_mode=False`` re-raises *click's* exception
objects, so we must catch the exact classes typer uses internally — otherwise
``isinstance`` checks miss. We prefer the vendored module and fall back to external
click for older typer.
"""

from __future__ import annotations

try:  # typer >= 0.16 (vendored click)
    from typer import _click as _vendored

    _exc = _vendored.exceptions
except (ImportError, AttributeError):  # pragma: no cover - older typer with external click
    import click as _vendored  # type: ignore[import-not-found, no-redef]

    _exc = _vendored.exceptions

ClickUsageError = _exc.UsageError
ClickExit = _exc.Exit
ClickAbort = _exc.Abort

__all__ = ["ClickAbort", "ClickExit", "ClickUsageError"]
