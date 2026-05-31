"""Human-facing rich tables (default output mode).

Human output may evolve freely (CLI_CONTRACT §4) — only the JSON is a contract. These
are general helpers; commands build their own column layouts on top.
"""

from __future__ import annotations

from collections.abc import Sequence

from rich.console import Console
from rich.table import Table


def key_value_table(
    console: Console,
    rows: Sequence[tuple[str, str]],
    *,
    title: str | None = None,
) -> None:
    """A two-column label/value table (used by ``doctor``, ``show``-style views)."""
    table = Table(show_header=False, box=None, title=title, title_justify="left", pad_edge=False)
    table.add_column("key", style="bold", no_wrap=True)
    table.add_column("value", overflow="fold")
    for key, value in rows:
        table.add_row(key, value)
    console.print(table)


def data_table(
    console: Console,
    columns: Sequence[str],
    rows: Sequence[Sequence[str]],
    *,
    title: str | None = None,
    caption: str | None = None,
) -> None:
    """A standard multi-column results table."""
    table = Table(title=title, title_justify="left", caption=caption, caption_justify="right")
    for col in columns:
        table.add_column(col, overflow="fold")
    for row in rows:
        table.add_row(*[str(cell) for cell in row])
    console.print(table)
