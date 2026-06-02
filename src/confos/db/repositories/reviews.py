"""Review repository: per-review rows + the aggregate columns on ``papers``.

Keyed by ``paper_id`` like the other child rows — a re-ingest of a note fully replaces its
reviews (no accumulation). Aggregates are written to ``papers`` in the same transaction so
ranking stays a single indexed query.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from ...models import NormalizedReview


def replace_reviews(
    conn: sqlite3.Connection, paper_id: str, reviews: list[NormalizedReview]
) -> None:
    """Replace a paper's review rows (delete + re-insert). OR IGNORE tolerates the rare
    duplicate reviewer signature rather than aborting the paper's whole transaction."""
    conn.execute("DELETE FROM reviews WHERE paper_id = ?", (paper_id,))
    conn.executemany(
        "INSERT OR IGNORE INTO reviews "
        "(paper_id, reviewer_key, rating, confidence, sub_scores_json, raw_rating) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                paper_id,
                review.reviewer_key,
                review.rating,
                review.confidence,
                json.dumps(review.sub_scores, ensure_ascii=False),
                review.raw_rating,
            )
            for review in reviews
        ],
    )


def write_aggregates(conn: sqlite3.Connection, paper_id: str, aggregates: dict[str, Any]) -> None:
    """Write the review-aggregate columns onto the paper row (idempotent; 0/NULL when none)."""
    conn.execute(
        """
        UPDATE papers SET
            review_count=:review_count,
            rating_mean=:rating_mean,
            rating_std=:rating_std,
            confidence_mean=:confidence_mean
        WHERE id=:paper_id
        """,
        {**aggregates, "paper_id": paper_id},
    )


def reviews_for_paper(conn: sqlite3.Connection, paper_id: str) -> list[sqlite3.Row]:
    """Per-review rows for a paper (for `papers show`/provenance), deterministic order."""
    return conn.execute(
        "SELECT reviewer_key, rating, confidence, sub_scores_json, raw_rating "
        "FROM reviews WHERE paper_id = ? ORDER BY reviewer_key",
        (paper_id,),
    ).fetchall()
