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
from ..aliases import load_normalize_aliases
from ..db.connection import connect
from ..db.migrate import create_derived, drop_derived, migrate
from ..db.repositories import count_table, reset_entities
from ..db.repositories import venues as venues_repo
from ..errors import ConfigError
from ..jsonl import read_jsonl_records
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
        # PREPARE (read-only, fail-soft): load venue refs + normalize all notes BEFORE any
        # destructive write. A malformed venue.json / unknown source raises here, leaving
        # the existing index untouched (never a half-wiped FTS); bad note lines are skipped.
        aliases = load_normalize_aliases(paths)
        prepared: list[tuple[VenueRef, list[Any]]] = []
        failed = 0
        for venue_dir in _snapshots(paths):
            ref = _load_ref(venue_dir)
            adapter = _adapter_for(ref.source)
            profiles = _load_profiles(venue_dir)  # optional Phase-1 enrichment snapshot
            papers = []
            for line in read_jsonl_records(venue_dir / "submissions.jsonl"):
                try:
                    papers.append(
                        adapter.normalize(json.loads(line), ref, aliases=aliases, profiles=profiles)
                    )
                except Exception:  # skip an unparseable/invalid note line, keep going
                    failed += 1
            prepared.append((ref, papers))

        # APPLY (single transaction; the data is pre-validated, so this won't raise).
        papers_done = 0
        with conn:
            drop_derived(conn)
            create_derived(conn)
            reset_entities(conn)
            for ref, papers in prepared:
                venues_repo.upsert_venue(conn, ref, last_ingested_at=None)  # keep watermarks
                for paper in papers:
                    upsert_normalized_paper(conn, paper)
                    papers_done += 1
        return {"venues": len(prepared), "papers": papers_done, "failed": failed}
    finally:
        conn.close()


def _load_profiles(venue_dir: Path) -> dict[str, Any]:
    """Load ``profiles.jsonl`` (handle → raw profile) if present, else an empty map.

    Best-effort: bad lines and profiles missing usable content (e.g. ``not_found``
    markers, kept so we don't re-fetch them) are skipped. The map drives author
    enrichment during rebuild with no network (D3).
    """
    path = venue_dir / "profiles.jsonl"
    if not path.exists():
        return {}
    profiles: dict[str, Any] = {}
    for line in read_jsonl_records(path):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        handle = record.get("id")
        if isinstance(handle, str) and record.get("content"):
            profiles[handle] = record
    return profiles


def _load_ref(venue_dir: Path) -> VenueRef:
    try:
        return VenueRef.model_validate_json((venue_dir / "venue.json").read_text("utf-8"))
    except Exception as exc:
        raise ConfigError(
            f"Cannot rebuild: {venue_dir / 'venue.json'} is missing or malformed ({exc}).",
            hint="Fix or remove that snapshot, or re-ingest the venue.",
        ) from exc


def status(paths: Paths) -> dict[str, Any]:
    conn = connect(paths.db)
    try:
        migrate(conn)
        counts = {table: count_table(conn, table) for table in _CORE_COUNT_TABLES}
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
