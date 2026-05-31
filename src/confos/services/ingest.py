"""Ingest orchestration: fetch → snapshot raw JSONL → normalize → upsert → watermark.

The raw JSONL snapshot under ``raw/<source>/<slug>/`` is the source of truth (D3); the
SQLite rows are derived. A full ingest (first run or ``--force``) rewrites the snapshot;
an incremental re-run (D6) fetches only notes newer than the stored ``max_tcdate``
watermark and appends them. The DB write happens in one transaction so a paper's rows
land atomically.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from pathlib import Path

from ..adapters.base import RawNote, SourceAdapter
from ..db.connection import connect
from ..db.migrate import migrate
from ..db.repositories import authors as authors_repo
from ..db.repositories import now_iso
from ..db.repositories import orgs as orgs_repo
from ..db.repositories import papers as papers_repo
from ..db.repositories import venues as venues_repo
from ..models import IngestOptions, IngestResult, IngestStatus, NormalizedPaper, VenueRef
from ..paths import Paths

ProgressFn = Callable[[str], None]


def _noop(_: str) -> None:
    pass


def _max(*values: int | None) -> int | None:
    present = [v for v in values if v is not None]
    return max(present) if present else None


def ingest_venue(
    *,
    paths: Paths,
    adapter: SourceAdapter,
    handle: str,
    opts: IngestOptions,
    on_progress: ProgressFn = _noop,
) -> IngestResult:
    """Ingest one venue into the local store. Returns counts + watermarks."""
    paths.ensure()
    conn = connect(paths.db)
    try:
        migrate(conn)

        ref = _resolve(conn, adapter, handle)
        on_progress(f"Resolved {ref.slug} → {ref.source_venue_id}")

        last_tcdate, last_tmdate = venues_repo.latest_watermark(conn, ref.slug)
        incremental = last_tcdate is not None and not opts.force
        since = last_tcdate if incremental else None
        on_progress(
            "Incremental update (new + edited submissions)"
            if incremental
            else "Full fetch (this may take a while for a large venue)"
        )

        raw_notes = list(
            adapter.fetch_notes(
                ref, opts, since_tcdate=since, since_tmdate=last_tmdate if incremental else None
            )
        )
        papers: list[NormalizedPaper] = []
        failed = 0
        for raw in raw_notes:
            try:
                papers.append(adapter.normalize(raw, ref))
            except Exception as exc:
                failed += 1
                on_progress(f"skipped note {raw.get('id')!r} (normalize failed: {exc})")
        on_progress(
            f"Fetched {len(raw_notes)} submission(s)" + (f", {failed} skipped" if failed else "")
        )
        status: IngestStatus = "partial" if failed else "ok"
        warnings = [f"{failed} note(s) failed to normalize and were skipped"] if failed else []

        max_tcdate = _max(last_tcdate, *(p.tcdate for p in papers))
        max_tmdate = _max(last_tmdate, *(p.tmdate for p in papers))

        if opts.dry_run:
            return _dry_run_result(
                conn, ref, papers, incremental, max_tcdate, max_tmdate, failed, status, warnings
            )

        raw_dir = paths.raw_venue_dir(ref.source, ref.slug)
        raw_dir.mkdir(parents=True, exist_ok=True)
        # Current-state snapshot keyed by id: full = rewrite, incremental = merge. The
        # merge is idempotent, so a failed DB transaction simply re-merges next run (no
        # duplicate lines), and the snapshot never goes stale for edited notes.
        _persist_snapshot(raw_dir / "submissions.jsonl", raw_notes, full=not incremental)
        _write_json(raw_dir / "venue.json", ref.model_dump())

        started = now_iso()
        added, updated = _write_papers(
            conn, ref, papers, started, status, max_tcdate, max_tmdate, items_seen=len(raw_notes)
        )

        result = IngestResult(
            venue=ref.slug,
            status=status,
            items_seen=len(raw_notes),
            items_added=added,
            items_updated=updated,
            items_failed=failed,
            max_tcdate=max_tcdate,
            max_tmdate=max_tmdate,
            incremental=incremental,
            raw_path=str(raw_dir / "submissions.jsonl"),
            warnings=warnings,
        )
        _write_json(raw_dir / "ingest_run.json", result.model_dump())
        return result
    finally:
        conn.close()


def upsert_normalized_paper(conn: sqlite3.Connection, paper: NormalizedPaper) -> bool:
    """Upsert one normalized paper + its authors/orgs. Returns True if newly inserted.

    Shared by ingest and ``index rebuild``; the caller owns the transaction.
    """
    for author in paper.authors:
        authors_repo.upsert_author(conn, author)
        if author.affiliation:
            org_id = orgs_repo.upsert_org(conn, author.affiliation, author.country)
            orgs_repo.link_affiliation(conn, author.author_id, org_id, confidence="low")
    return papers_repo.upsert_paper(conn, paper)


def _resolve(conn: sqlite3.Connection, adapter: SourceAdapter, handle: str) -> VenueRef:
    """Resolve a handle: a DB-registered slug takes priority, else the adapter's map."""
    row = venues_repo.get_venue(conn, handle)
    if row is not None:
        ref = adapter.resolve_venue(row["source_venue_id"])
        return ref.model_copy(update={"slug": handle})
    return adapter.resolve_venue(handle)


def _write_papers(
    conn: sqlite3.Connection,
    ref: VenueRef,
    papers: list[NormalizedPaper],
    started: str,
    status: IngestStatus,
    max_tcdate: int | None,
    max_tmdate: int | None,
    *,
    items_seen: int,
) -> tuple[int, int]:
    added = updated = 0
    with conn:  # transaction: all-or-nothing
        venues_repo.upsert_venue(conn, ref, last_ingested_at=started)
        for paper in papers:
            if upsert_normalized_paper(conn, paper):
                added += 1
            else:
                updated += 1
        venues_repo.insert_ingest_run(
            conn,
            venue_slug=ref.slug,
            status=status,
            started_at=started,
            finished_at=now_iso(),
            items_seen=items_seen,
            items_added=added,
            items_updated=updated,
            max_tcdate=max_tcdate,
            max_tmdate=max_tmdate,
        )
    return added, updated


def _dry_run_result(
    conn: sqlite3.Connection,
    ref: VenueRef,
    papers: list[NormalizedPaper],
    incremental: bool,
    max_tcdate: int | None,
    max_tmdate: int | None,
    failed: int,
    status: IngestStatus,
    warnings: list[str],
) -> IngestResult:
    added = 0
    for paper in papers:
        if not papers_repo.exists(conn, paper.paper_id):
            added += 1
    return IngestResult(
        venue=ref.slug,
        status=status,
        items_seen=len(papers) + failed,
        items_added=added,
        items_updated=len(papers) - added,
        items_failed=failed,
        max_tcdate=max_tcdate,
        max_tmdate=max_tmdate,
        incremental=incremental,
        dry_run=True,
        warnings=warnings,
    )


def _persist_snapshot(path: Path, notes: list[RawNote], *, full: bool) -> None:
    """Write the raw snapshot as current-state, one line per note id.

    ``full`` rewrites from scratch; otherwise the fetched notes are merged into the
    existing snapshot by id (updating edited notes, adding new ones). Either way the
    file holds exactly one current line per id, so ``index rebuild`` re-normalizes
    truth without any dedup ambiguity.
    """
    by_id: dict[str, RawNote] = {}
    if not full and path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                existing = json.loads(line)
                by_id[str(existing.get("id"))] = existing
    for note in notes:
        by_id[str(note.get("id"))] = note
    with path.open("w", encoding="utf-8") as fh:
        for note in by_id.values():
            fh.write(json.dumps(note, ensure_ascii=False) + "\n")


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
