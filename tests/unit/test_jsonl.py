"""read_jsonl_records: split on '\n' only, never on Unicode line separators.

Regression guard for the U+2028 data-loss bug -- a single LINE SEPARATOR inside a note
abstract used to tear the record in two under str.splitlines(), so json.loads failed on
both halves and the paper silently vanished (colm-2024 fell 299->298 on rebuild).
"""

from __future__ import annotations

import json
from pathlib import Path

from confos.jsonl import read_jsonl_records

# U+2028 LINE SEPARATOR, U+2029 PARAGRAPH SEPARATOR, U+0085 NEL -- str.splitlines() breaks on
# all three; the JSONL record separator is only '\n'.
_SEPS = "\u2028\u2029\u0085"


def test_unicode_line_separators_do_not_split_records(tmp_path: Path) -> None:
    records = [
        {"id": "p1", "abstract": f"first{_SEPS}second"},
        {"id": "p2", "abstract": "ordinary text"},
    ]
    path = tmp_path / "submissions.jsonl"
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8"
    )

    lines = read_jsonl_records(path)
    assert len(lines) == 2  # str.splitlines() would have returned 4+ fragments here
    parsed = [json.loads(line) for line in lines]  # every record must still parse cleanly
    assert [r["id"] for r in parsed] == ["p1", "p2"]
    assert _SEPS in parsed[0]["abstract"]  # the separators round-trip verbatim


def test_blank_lines_skipped_and_trailing_newline_harmless(tmp_path: Path) -> None:
    path = tmp_path / "x.jsonl"
    path.write_text('{"id": 1}\n\n{"id": 2}\n', encoding="utf-8")
    assert read_jsonl_records(path) == ['{"id": 1}', '{"id": 2}']
