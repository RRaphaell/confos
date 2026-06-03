"""Author explore: search by name, show profile + stats, list papers (offline).

``authors find --topic`` (the ranked people-discovery differentiator) lands in Phase 3.
"""

from __future__ import annotations

from typing import Any

from ..db.connection import connect
from ..db.migrate import migrate
from ..db.repositories import authors as authors_repo
from ..db.repositories import papers as papers_repo
from ..errors import NotFoundError
from ..paths import Paths
from ..serialize import author_dict
from .search import assemble_papers


def search_authors(paths: Paths, name: str, *, limit: int = 25) -> list[dict[str, Any]]:
    conn = connect(paths.db)
    try:
        migrate(conn)
        rows = authors_repo.search_by_name(conn, name, limit=limit)
        return [{**author_dict(row), "paper_count": row["paper_count"]} for row in rows]
    finally:
        conn.close()


def top_authors(paths: Paths, *, venue: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """Most-prolific authors in a venue (for the venue-wide `brief` people list)."""
    conn = connect(paths.db)
    try:
        migrate(conn)
        rows = authors_repo.top_by_paper_count(conn, venue=venue, limit=limit)
        return [{**author_dict(row), "paper_count": row["paper_count"]} for row in rows]
    finally:
        conn.close()


def show_author(paths: Paths, author_id: str) -> dict[str, Any]:
    conn = connect(paths.db)
    try:
        migrate(conn)
        row = authors_repo.get_with_stats(conn, author_id)
        if row is None:
            raise NotFoundError(
                f"Author '{author_id}' is not in the local store.",
                hint="Find them with `confos authors search <name>`.",
            )
        data = author_dict(row)
        data["paper_count"] = row["paper_count"]
        data["venues"] = [
            {"venue": v["venue"], "papers": v["papers"]}
            for v in authors_repo.venues_for_author(conn, author_id)
        ]
        return data
    finally:
        conn.close()


def author_papers(
    paths: Paths, author_id: str, *, venue: str | None = None, limit: int = 50
) -> dict[str, Any]:
    conn = connect(paths.db)
    try:
        migrate(conn)
        author = authors_repo.get_with_stats(conn, author_id)
        if author is None:
            raise NotFoundError(
                f"Author '{author_id}' is not in the local store.",
                hint="Find them with `confos authors search <name>`.",
            )
        rows = papers_repo.list_by_author(conn, author_id, venue=venue, limit=limit)
        papers = assemble_papers(conn, rows, include_abstract=False, with_bm25=False)
        return {"author": author_dict(author), "papers": papers}
    finally:
        conn.close()
