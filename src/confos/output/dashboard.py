"""Dashboard primitives for the human ``confos brief`` view (ft-style).

Bold-accent UPPERCASE section headers with a dim subtitle, a stacked composition bar with a
legend, a stat line, and clean entry lists. Human path only — every piece collapses to plain
text under no-colour and degrades to ASCII without Unicode, so ``brief | cat`` stays clean.
"""

from __future__ import annotations

from collections.abc import Sequence

from rich.console import Console
from rich.markup import escape


def section(console: Console, title: str, subtitle: str | None = None) -> None:
    """A blank line, a bold-accent UPPERCASE header, and an optional dim subtitle."""
    console.print()
    console.print(f"[confos.heading]{escape(title.upper())}[/]")
    if subtitle:
        console.print(f"[confos.muted]{escape(subtitle)}[/]")


def stat_line(console: Console, stats: Sequence[tuple[int, str]]) -> None:
    """``N papers · M authors · …`` — bold counts, dim labels and separators."""
    parts = [
        f"[confos.count]{count:,}[/] [confos.muted]{escape(label)}[/]" for count, label in stats
    ]
    console.print("  " + " [confos.muted]·[/] ".join(parts))


def composition_bar(
    console: Console,
    segments: Sequence[tuple[str, int, str]],
    *,
    width: int = 48,
    unicode: bool = True,
) -> None:
    """One stacked proportion bar (each segment = label, count, style) + a legend line."""
    present = [(label, count, style) for label, count, style in segments if count]
    if not present:
        return
    total = sum(count for _, count, _ in present)
    block = "█" if unicode else "#"
    # Largest-remainder allocation so the segments fill exactly `width` cells.
    exact = [count / total * width for _, count, _ in present]
    cells = [int(x) for x in exact]
    for _, idx in sorted(((exact[i] - cells[i], i) for i in range(len(present))), reverse=True)[
        : width - sum(cells)
    ]:
        cells[idx] += 1
    bar = "".join(
        f"[{style}]{block * n}[/]" for (_, _, style), n in zip(present, cells, strict=True) if n
    )
    legend = "   ".join(
        f"[{style}]▆[/] [confos.muted]{escape(label)} {count} ({round(count / total * 100)}%)[/]"
        for label, count, style in present
    )
    console.print(f"  {bar}")
    console.print(f"  {legend}")


def entry(
    console: Console,
    marker: str,
    primary: str,
    secondary: str | None = None,
    *,
    link: str | None = None,
    supports_hyperlinks: bool = False,
) -> None:
    """One list item: ``● primary`` (optionally a link) + an indented dim secondary line."""
    title = escape(primary)
    if link and supports_hyperlinks:
        title = f"[link={link}]{title}[/link]"
    console.print(f"  [confos.accent]{escape(marker)}[/] {title}")
    if secondary:
        console.print(f"    [confos.muted]{escape(secondary)}[/]")
