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
        low = stats_repo.papers_with_affiliation(conn, venue, confidence="low")
        return {
            "rows": rows,
            "data_quality": {
                "papers_total": total,
                "papers_with_signal": with_signal,
                "unknown": total - with_signal,
                "low_confidence": low,
                "method": "author_affiliation_profile_v1",
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
            # The org name didn't resolve. Distinguish "nothing is enriched yet" (the whole
            # org index is empty, so NOTHING would resolve) from "this particular org isn't
            # here" — same not-found exit code, but an actionable message instead of one that
            # misleadingly implies this org specifically has zero papers.
            if stats_repo.papers_with_affiliation(conn) == 0:
                raise NotFoundError(
                    f"No organisation data is enriched yet, so '{org}' can't be resolved.",
                    hint="Populate affiliations with `confos enrich profiles --venue <slug>` "
                    "(v1 org coverage is sparse without it).",
                )
            raise NotFoundError(
                f"Organisation '{org}' isn't in the local store.",
                hint="Names use the normalised form — see `confos orgs top` for what's available.",
            )
        rows = papers_repo.list_by_org(conn, org_row["id"], venue=venue, limit=limit)
        papers = assemble_papers(conn, rows, include_abstract=False, with_bm25=False)
        return {"org": {"name": org_row["name"], "country": org_row["country"]}, "papers": papers}
    finally:
        conn.close()
