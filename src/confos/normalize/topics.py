"""Topic normalization: free-text keywords → normalized topics.

A "topic" stored in ``paper_topics`` is a lowercased, whitespace-collapsed keyword,
optionally collapsed through a user alias map (Phase 3 loads ``aliases/topics.yml``).
The richer FTS-based ``--topic`` *matching* (alias expansion, comma/space grouping)
lives in the search/ranking layer; this is only the per-paper keyword normalization.
"""

from __future__ import annotations

from collections.abc import Iterable


def normalize_topic(keyword: str) -> str:
    """Lowercase + collapse internal whitespace. Returns '' for blank input."""
    return " ".join(keyword.lower().split())


def normalize_keywords(keywords: Iterable[str], aliases: dict[str, str] | None = None) -> list[str]:
    """Normalize a paper's keywords into a deduped, order-preserving topic list."""
    alias_map = aliases or {}
    out: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        topic = normalize_topic(keyword)
        if not topic:
            continue
        topic = alias_map.get(topic, topic)
        if topic not in seen:
            seen.add(topic)
            out.append(topic)
    return out
