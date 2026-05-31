"""FTS5 MATCH query building (safe, deterministic)."""

from __future__ import annotations

import pytest

from confos.errors import UsageError
from confos.fts import match_query, match_query_or


def test_match_query_ands_quoted_terms() -> None:
    assert match_query("long-running agents") == '"long-running" AND "agents"'
    assert match_query("  tool   use ") == '"tool" AND "use"'


def test_match_query_escapes_quotes() -> None:
    assert match_query('say "hi"') == '"say" AND """hi"""'


def test_match_query_empty_raises() -> None:
    with pytest.raises(UsageError):
        match_query("   ")


def test_match_query_or() -> None:
    assert match_query_or(["memory", "agents"]) == '"memory" OR "agents"'
    assert match_query_or([]) == ""
    assert match_query_or(["", "  "]) == ""
