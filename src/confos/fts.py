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
