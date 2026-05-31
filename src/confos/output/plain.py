"""Best-effort ``--plain`` output for shell scripts.

Per DECISIONS (Phase-2 open item): ``--plain`` is *best-effort* line/TSV output;
**JSON is the contract**. We emit tab-separated rows so ``cut``/``awk`` work, but we
do not version the column layout — scripts that need stability use ``--json``.
"""

from __future__ import annotations

from collections.abc import Sequence

from rich.console import Console


def _clean(cell: object) -> str:
    """Flatten a cell to a single TSV-safe line (tabs/newlines collapsed to spaces)."""
    return str(cell).replace("\t", " ").replace("\n", " ").replace("\r", " ")


def tsv_rows(console: Console, rows: Sequence[Sequence[object]]) -> None:
    """Print tab-separated rows to stdout, one record per line.

    Writes raw bytes via ``console.file`` rather than ``console.print`` so rich never
    swallows the TAB separators or soft-wraps a long value across physical lines — both
    of which would break ``cut``/``awk`` consumers (the whole point of ``--plain``).
    """
    for row in rows:
        console.file.write("\t".join(_clean(cell) for cell in row) + "\n")
    console.file.flush()


def key_value_plain(console: Console, rows: Sequence[tuple[str, object]]) -> None:
    """Print ``key<TAB>value`` lines (used by ``doctor`` / status views)."""
    tsv_rows(console, [(k, v) for k, v in rows])
