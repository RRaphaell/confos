"""Aggregate statistics — always honest about coverage (PRODUCT principle #4).

Every breakdown ships a ``data_quality`` block (SCHEMAS §4): how many papers carried
the signal, how many are unknown, how many are low-confidence, and the method label. We
never present a clean number while hiding that, e.g., 90% of affiliations are unknown.
"""

from __future__ import annotations

from typing import Any

from ..db.connection import connect
from ..db.migrate import migrate
from ..db.repositories import stats as stats_repo
from ..paths import Paths

# Surfaced wherever the accepted/rejected status mix is shown, so the number is never
# misread as a venue acceptance rate (OpenReview only exposes a subset of rejections).
STATUS_COVERAGE_NOTE = (
    "Status mix reflects publicly-visible submissions only — OpenReview hides most "
    "rejected papers, so this is not the venue's acceptance rate."
)


def overview(paths: Paths, venue: str | None = None) -> dict[str, Any]:
    conn = connect(paths.db)
    try:
        migrate(conn)
        distinct = stats_repo.distinct_entity_counts(conn, venue)
        status = {r["key"]: r["papers"] for r in stats_repo.status_counts(conn, venue)}
        result: dict[str, Any] = {
            "venue": venue,
            "papers": stats_repo.papers_total(conn, venue),
            "status": status,
            "authors": distinct["authors"],
            "orgs": distinct["orgs"],
            "topics": distinct["topics"],
            "venues": distinct["venues"],
        }
        # Honesty guard (PRODUCT principle #4): the status mix is the *publicly-visible*
        # subset, not a venue acceptance rate — OpenReview hides most rejections, so a bare
        # "accepted 5286 / rejected 254" must not be read as ~95% accepted.
        if status:
            result["status_note"] = STATUS_COVERAGE_NOTE
        return result
    finally:
        conn.close()


def topics(paths: Paths, venue: str | None = None, *, limit: int = 50) -> dict[str, Any]:
    conn = connect(paths.db)
    try:
        migrate(conn)
        total = stats_repo.papers_total(conn, venue)
        with_signal = stats_repo.papers_with_keywords(conn, venue)
        rows = [
            {"key": r["key"], "papers": r["papers"]}
            for r in stats_repo.topic_counts(conn, venue, limit=limit)
        ]
        return {
            "rows": rows,
            "data_quality": _quality(total, with_signal, low=0, method="normalized_keyword_v1"),
        }
    finally:
        conn.close()


def orgs(paths: Paths, venue: str | None = None, *, limit: int = 50) -> dict[str, Any]:
    conn = connect(paths.db)
    try:
        migrate(conn)
        total = stats_repo.papers_total(conn, venue)
        with_signal = stats_repo.papers_with_affiliation(conn, venue)
        low = stats_repo.papers_with_affiliation(conn, venue, confidence="low")
        rows = [
            {"key": r["key"], "papers": r["papers"]}
            for r in stats_repo.org_counts(conn, venue, limit=limit)
        ]
        # Affiliations are profile-derived (high) where a profile snapshot exists, else an
        # email-domain guess (low). `low_confidence` reports only the latter (honest).
        return {
            "rows": rows,
            "data_quality": _quality(
                total, with_signal, low=low, method="author_affiliation_profile_v1"
            ),
        }
    finally:
        conn.close()


def countries(paths: Paths, venue: str | None = None, *, limit: int = 50) -> dict[str, Any]:
    conn = connect(paths.db)
    try:
        migrate(conn)
        total = stats_repo.papers_total(conn, venue)
        with_signal = stats_repo.papers_with_country(conn, venue)
        low = stats_repo.papers_with_affiliation(conn, venue, confidence="low")
        rows = [
            {"key": r["key"], "papers": r["papers"]}
            for r in stats_repo.country_counts(conn, venue, limit=limit)
        ]
        # Country comes from the profile's explicit ISO code (authoritative) or, for
        # email-derived affiliations, a domain-TLD guess (low).
        return {
            "rows": rows,
            "data_quality": _quality(
                total, with_signal, low=low, method="affiliation_country_profile_v1"
            ),
        }
    finally:
        conn.close()


def _quality(total: int, with_signal: int, *, low: int, method: str) -> dict[str, Any]:
    return {
        "papers_total": total,
        "papers_with_signal": with_signal,
        "unknown": total - with_signal,
        "low_confidence": low,
        "method": method,
    }
