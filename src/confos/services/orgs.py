"""Organisation explore: top orgs by paper count, papers for an org (offline).

Org coverage is best-effort in v1 (email-domain only); Phase 3 enriches it from author
profiles and reports data quality. Stats here are honest about that sparsity.
"""

from __future__ import annotations

from typing import Any

from ..db.connection import connect
from ..db.migrate import migrate
from ..db.repositories import orgs as orgs_repo
from ..db.repositories import papers as papers_repo
from ..db.repositories import stats as stats_repo
from ..errors import NotFoundError
from ..paths import Paths
from .search import assemble_papers


def top_orgs(paths: Paths, *, venue: str | None = None, limit: int = 50) -> dict[str, Any]:
    """Top orgs by paper count, WITH a data_quality block — the same honesty guardrail
    `stats orgs` carries, so the ranked list never reads as authoritative coverage."""
    conn = connect(paths.db)
    try:
        migrate(conn)
        rows = [
            {"name": row["name"], "country": row["country"], "papers": row["papers"]}
            for row in orgs_repo.top(conn, venue=venue, limit=limit)
        ]
        total = stats_repo.papers_total(conn, venue)
        with_signal = stats_repo.papers_with_affiliation(conn, venue)
        return {
            "rows": rows,
            "data_quality": {
                "papers_total": total,
                "papers_with_signal": with_signal,
                "unknown": total - with_signal,
                "low_confidence": with_signal,
                "method": "author_affiliation_domain_v1",
            },
        }
    finally:
        conn.close()


def org_papers(
    paths: Paths, org: str, *, venue: str | None = None, limit: int = 50
) -> dict[str, Any]:
    conn = connect(paths.db)
    try:
        migrate(conn)
        org_row = orgs_repo.find_by_name(conn, org)
        if org_row is None:
            raise NotFoundError(
                f"Organisation '{org}' has no papers in the local store.",
                hint="Org coverage is best-effort in v1; see `confos orgs top`.",
            )
        rows = papers_repo.list_by_org(conn, org_row["id"], venue=venue, limit=limit)
        papers = assemble_papers(conn, rows, include_abstract=False, with_bm25=False)
        return {"org": {"name": org_row["name"], "country": org_row["country"]}, "papers": papers}
    finally:
        conn.close()
