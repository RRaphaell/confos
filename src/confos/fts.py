"""Build safe SQLite FTS5 MATCH expressions from user text (pure functions).

User queries can contain FTS5 syntax characters (quotes, ``*``, ``AND``/``OR``,
parentheses) that would otherwise raise a syntax error. We tokenize on whitespace and
quote each token as a string term, AND-ing them — so ``papers search "long-running
agents"`` becomes ``"long-running" AND "agents"`` and matches papers containing both.
The richer ``--topic`` matcher (comma=OR, alias expansion, RANKING §1) lands in Phase 3.
"""

from __future__ import annotations

import re

from .errors import UsageError

_WS = re.compile(r"\s+")


def _quote(term: str) -> str:
    """Quote a token as an FTS5 string term (escaping embedded double quotes)."""
    return '"' + term.replace('"', '""') + '"'


def match_query(text: str) -> str:
    """Build an AND-of-terms FTS5 MATCH expression. Raises on an empty query."""
    terms = [t for t in _WS.split(text.strip()) if t]
    if not terms:
        raise UsageError("Search query is empty.", hint="Provide one or more words to match.")
    return " AND ".join(_quote(term) for term in terms)


def match_query_or(terms: list[str]) -> str:
    """Build an OR-of-terms FTS5 MATCH expression (used by ``papers related``)."""
    cleaned = [t for t in terms if t.strip()]
    if not cleaned:
        return ""
    return " OR ".join(_quote(t) for t in cleaned)


def topic_query(topic: str, aliases: dict[str, list[str]] | None = None) -> str:
    """Build the ``--topic`` MATCH expression (RANKING §1).

    Lowercases + trims; commas separate OR-groups; whitespace within a group is AND-ed.
    A group (or a token) matching the alias map expands to ``(syn1 OR syn2 OR …)`` —
    e.g. ``evals`` → ``("evals" OR "evaluation" OR "benchmark")``. So
    ``--topic "agent memory, long-running agents"`` →
    ``(("agent" AND "memory")) OR (("long-running" AND "agents"))``.
    """
    alias_map = aliases or {}
    groups = [g.strip() for g in topic.strip().lower().split(",") if g.strip()]
    if not groups:
        raise UsageError("Topic is empty.", hint="e.g. --topic 'agent memory'")

    or_parts: list[str] = []
    for group in groups:
        group_syns = alias_map.get(group)
        if group_syns:
            or_parts.append("(" + " OR ".join(_quote(s) for s in group_syns) + ")")
            continue
        and_parts: list[str] = []
        for token in _WS.split(group):
            if not token:
                continue
            token_syns = alias_map.get(token)
            if token_syns:
                and_parts.append("(" + " OR ".join(_quote(s) for s in token_syns) + ")")
            else:
                and_parts.append(_quote(token))
        if and_parts:
            or_parts.append("(" + " AND ".join(and_parts) + ")")
    return " OR ".join(or_parts)
