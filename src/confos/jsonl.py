"""Reading JSONL snapshots — with the one correctness rule the format demands.

confos persists its raw snapshots (``submissions.jsonl``, ``profiles.jsonl``) as one JSON
record per ``\\n``, written with ``ensure_ascii=False`` so OpenReview note text round-trips
verbatim (D3: the snapshot is the offline source of truth). That text can legitimately
contain U+2028 / U+2029 / U+0085 — Unicode line separators that appear inside real paper
abstracts and reviews.

``str.splitlines()`` splits on *those* too, not just ``\\n``. So reading a snapshot with
``.splitlines()`` tears a single record into fragments that each fail ``json.loads`` and are
silently skipped — the paper vanishes with no error (a lone U+2028 in a note dropped
``colm-2024`` from 299 to 298 papers on ``index rebuild``). That directly breaks confos's
core promise that every paper is real and traceable.

So every JSONL read must split on ``\\n`` ONLY. This module is the single place that rule
lives; readers should call :func:`read_jsonl_records` rather than ``.splitlines()``.
"""

from __future__ import annotations

from pathlib import Path


def read_jsonl_records(path: Path) -> list[str]:
    """Return the non-blank record lines of a JSONL file, split on ``\\n`` only.

    Callers still ``json.loads`` each returned line (and may apply their own per-line
    error handling); this only guarantees the *record boundaries* are correct.
    """
    return [line for line in path.read_text("utf-8").split("\n") if line.strip()]
