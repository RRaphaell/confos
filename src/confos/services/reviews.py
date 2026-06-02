"""Review aggregation — turn a paper's parsed Official_Reviews into ranking signals.

Pure functions (no I/O). The aggregates land in the ``papers`` row at upsert time so
``papers top`` / ``papers controversial`` rank with a single indexed query. ``rating_std``
(population std) is the controversy signal: high variance = reviewers disagreed.
"""

from __future__ import annotations

from statistics import mean, pstdev
from typing import Any

from ..models import NormalizedReview


def aggregate(reviews: list[NormalizedReview]) -> dict[str, Any]:
    """Summarise a paper's reviews. Means are over reviews that carry that score; a venue's
    rating scale isn't comparable across venues, so callers scope ranking to one venue."""
    ratings = [r.rating for r in reviews if r.rating is not None]
    confidences = [r.confidence for r in reviews if r.confidence is not None]
    return {
        "review_count": len(reviews),
        "rating_mean": mean(ratings) if ratings else None,
        "rating_std": pstdev(ratings) if ratings else None,  # 0.0 for a single rating
        "confidence_mean": mean(confidences) if confidences else None,
    }
