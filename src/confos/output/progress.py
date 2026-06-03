"""Human-mode progress for the one genuinely slow command (``ingest``).

Renders on the **stderr** console only (CLI_CONTRACT §4), and is a strict no-op on a
non-TTY, under ``--quiet``, or in ``--json``/``--plain`` mode — so stdout stays clean and
scripted/piped behaviour is byte-identical to before. See VISUAL.md §3.1.

A live spinner (rather than a determinate bar) because the full fetch is a single blocking
``get_all_notes`` call with no per-page hook; the spinner animates on a background thread
while that call runs, which is exactly the "it's not hung" signal a user needs. A
determinate bar would require paginating the adapter manually — deferred.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from rich.console import Console


@contextmanager
def spinner(console: Console, message: str, *, enabled: bool) -> Iterator[None]:
    """Show a live spinner on ``console`` (the stderr console) while a blocking step runs.

    ``enabled`` should be ``human_mode and console.is_terminal and not quiet``. When it is
    ``False`` this yields immediately with no output, so non-interactive runs are unchanged.
    """
    if not enabled:
        yield
        return
    with console.status(message, spinner="dots"):
        yield
