"""``index rebuild`` (re-normalize from raw JSONL, no network) + ``index status``.

Rebuild is the proof that the SQLite layer is disposable (D3): it drops the derived
tables and re-derives papers/authors/orgs/topics/FTS purely from the raw JSONL snapshots
+ venue.json. Sync state (``ingest_runs`` watermarks + ``last_ingested_at``) is preserved
— rebuild changes the index, not what's been fetched. The snapshot is current-state
(one line per id, D17), so rebuild needs no dedup.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..adapters.base import SourceAdapter
from ..adapters.openreview import OpenReviewAdapter
from ..db.connection import connect
from ..db.migrate import create_derived, drop_derived, migrate
from ..db.repositories import venues as venues_repo
from ..errors import ConfigError
from ..models import VenueRef
from ..paths import Paths
from .ingest import upsert_normalized_paper

_CORE_COUNT_TABLES = ("venues", "papers", "authors", "orgs", "paper_authors", "paper_topics")


def _adapter_for(source: str) -> SourceAdapter:
    if source == "openreview":
        return OpenReviewAdapter()
    raise ConfigError(f"No adapter for source '{source}' (snapshot cannot be rebuilt).")


def _snapshots(paths: Paths) -> list[Path]:
    """Venue snapshot directories that have both venue.json and submissions.jsonl."""
    if not paths.raw.is_dir():
        return []
    found: list[Path] = []
    for source_dir in sorted(paths.raw.iterdir()):
        if not source_dir.is_dir():
            continue
        for venue_dir in sorted(source_dir.iterdir()):
            if (venue_dir / "venue.json").exists() and (venue_dir / "submissions.jsonl").exists():
                found.append(venue_dir)
    return found


def rebuild(paths: Paths) -> dict[str, Any]:
    conn = connect(paths.db)
    try:
        migrate(conn)
        snapshots = _snapshots(paths)
        venues_done = 0
        papers_done = 0
        failed = 0
        with conn:  # one transaction: drop + re-derive everything
            drop_derived(conn)
            create_derived(conn)
            conn.execute("DELETE FROM papers")  # cascades paper_authors, paper_topics
            conn.execute("DELETE FROM authors")  # cascades author_affiliations
            conn.execute("DELETE FROM orgs")
            for venue_dir in snapshots:
                ref = VenueRef.model_validate_json((venue_dir / "venue.json").read_text("utf-8"))
                adapter = _adapter_for(ref.source)
                venues_repo.upsert_venue(conn, ref, last_ingested_at=None)  # keep existing
                for line in (venue_dir / "submissions.jsonl").read_text("utf-8").splitlines():
                    if not line.strip():
                        continue
                    try:
                        paper = adapter.normalize(json.loads(line), ref)
                    except Exception:  # skip an unparseable line, keep rebuilding
                        failed += 1
                        continue
                    upsert_normalized_paper(conn, paper)
                    papers_done += 1
                venues_done += 1
        return {
            "venues": venues_done,
            "papers": papers_done,
            "failed": failed,
            "snapshots": [str(p) for p in snapshots],
        }
    finally:
        conn.close()


def status(paths: Paths) -> dict[str, Any]:
    conn = connect(paths.db)
    try:
        migrate(conn)
        counts = {
            table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in _CORE_COUNT_TABLES
        }
        venues = [
            {
                "slug": row["slug"],
                "papers": row["paper_count"],
                "last_ingested_at": row["last_ingested_at"],
            }
            for row in venues_repo.list_venues(conn)
        ]
        return {"counts": counts, "venues": venues, "db": str(paths.db)}
    finally:
        conn.close()
