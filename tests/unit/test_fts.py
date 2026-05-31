"""FTS5 MATCH query building (safe, deterministic)."""

from __future__ import annotations

import pytest

from confos.errors import UsageError
from confos.fts import match_query, match_query_or, topic_query


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


def test_topic_query_and_within_group() -> None:
    assert topic_query("agent memory") == '("agent" AND "memory")'


def test_topic_query_comma_is_or() -> None:
    assert topic_query("agent memory, long-running agents") == (
        '("agent" AND "memory") OR ("long-running" AND "agents")'
    )


def test_topic_query_alias_expansion() -> None:
    aliases = {"evals": ["evals", "evaluation", "benchmark"]}
    assert topic_query("evals", aliases) == '("evals" OR "evaluation" OR "benchmark")'
    # token-level expansion inside a multi-token group
    assert topic_query("agent evals", aliases) == (
        '("agent" AND ("evals" OR "evaluation" OR "benchmark"))'
    )


def test_topic_query_empty_raises() -> None:
    with pytest.raises(UsageError):
        topic_query("  ,  ")
