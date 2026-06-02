"""Row → public-contract dict mappers (SCHEMAS §2 Paper, §3 Author).

Pure functions, no I/O. The exact field set + order here IS the agent contract, so
search/show/related, orgs/authors listings, and the Phase-5 context pack all go through
these to stay consistent.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any


def author_brief(row: sqlite3.Row) -> dict[str, Any]:
    """The compact per-paper author entry: ``{author_id, name, position}``."""
    return {"author_id": row["author_id"], "name": row["raw_name"], "position": row["position"]}


def paper_dict(
    row: sqlite3.Row,
    authors: list[dict[str, Any]],
    *,
    include_abstract: bool = False,
    include_artifacts: bool = False,
    bm25: float | None = None,
) -> dict[str, Any]:
    """A Paper object (SCHEMAS §2). ``abstract`` and the ``pdf_url``/``bibtex``/
    ``supplementary_url`` artifacts are included only when asked (lean by default for
    list/search/context views); ``bm25`` (positive, bigger = more relevant) only on
    search/find results. Callers that pass ``include_artifacts`` must select those columns
    (``SELECT *`` / ``p.*`` rows carry them)."""
    data: dict[str, Any] = {"paper_id": row["id"], "title": row["title"]}
    if include_abstract:
        data["abstract"] = row["abstract"]
    data["authors"] = authors
    data["keywords"] = json.loads(row["keywords_json"] or "[]")
    data["status"] = row["status"]
    data["acceptance_type"] = row["acceptance_type"]
    data["venue"] = row["venue_slug"]
    data["url"] = row["url"]
    if include_artifacts:
        data["pdf_url"] = row["pdf_url"]
        data["bibtex"] = row["bibtex"]
        data["supplementary_url"] = row["supplementary_url"]
    if bm25 is not None:
        data["bm25"] = round(bm25, 4)
    return data


def author_dict(row: sqlite3.Row) -> dict[str, Any]:
    """An Author object (SCHEMAS §3). Affiliation falls back to ``"Unknown"`` (honest)."""
    return {
        "author_id": row["id"],
        "display_name": row["display_name"],
        "affiliation_current": row["affiliation_current"] or "Unknown",
        "data_quality": row["data_quality"],
        "profile_url": row["profile_url"],
    }
