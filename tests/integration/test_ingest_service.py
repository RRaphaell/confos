"""Ingest service: full/incremental/dry-run/idempotent/partial (no network)."""

from __future__ import annotations

from pathlib import Path

import pytest

from confos.db.connection import connect
from confos.errors import UsageError
from confos.models import IngestOptions
from confos.paths import Paths
from confos.services.ingest import ingest_venue
from confos.services.venues import add_local_venue
from tests.synthetic import FAKE_REF, FakeAdapter, make_note


def _paths(tmp_path: Path) -> Paths:
    return Paths(home=tmp_path / "store")


def _paper_count(paths: Paths) -> int:
    conn = connect(paths.db)
    try:
        return int(conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0])
    finally:
        conn.close()


def _status(paths: Paths, paper_id: str) -> str:
    conn = connect(paths.db)
    try:
        return str(
            conn.execute("SELECT status FROM papers WHERE id = ?", (paper_id,)).fetchone()[0]
        )
    finally:
        conn.close()


def test_full_ingest_counts_and_snapshot(tmp_path: Path) -> None:
    notes = [
        make_note("p1", tcdate=100),
        make_note("p2", tcdate=200, authors=["Bob Tan"], authorids=["bob@mit.edu"]),
    ]
    paths = _paths(tmp_path)
    result = ingest_venue(
        paths=paths, adapter=FakeAdapter(FAKE_REF, notes), handle="test-venue", opts=IngestOptions()
    )
    assert result.status == "ok"
    assert (result.items_seen, result.items_added, result.items_updated) == (2, 2, 0)
    assert result.max_tcdate == 200
    assert result.incremental is False

    raw = paths.raw_venue_dir("openreview", "test-venue") / "submissions.jsonl"
    assert raw.exists()
    assert len(raw.read_text().strip().splitlines()) == 2
    assert (paths.raw_venue_dir("openreview", "test-venue") / "venue.json").exists()
    assert _paper_count(paths) == 2


def test_idempotent_reingest(tmp_path: Path) -> None:
    notes = [make_note("p1", tcdate=100)]
    paths = _paths(tmp_path)
    ingest_venue(
        paths=paths,
        adapter=FakeAdapter(FAKE_REF, notes),
        handle="test-venue",
        opts=IngestOptions(force=True),
    )
    result = ingest_venue(
        paths=paths,
        adapter=FakeAdapter(FAKE_REF, notes),
        handle="test-venue",
        opts=IngestOptions(force=True),
    )
    assert (result.items_added, result.items_updated) == (0, 1)
    assert _paper_count(paths) == 1
    conn = connect(paths.db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM authors").fetchone()[0] == 1  # no dup
        assert conn.execute("SELECT COUNT(*) FROM paper_authors").fetchone()[0] == 1
    finally:
        conn.close()


def test_incremental_picks_up_only_new_notes(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    ingest_venue(
        paths=paths,
        adapter=FakeAdapter(FAKE_REF, [make_note("p1", tcdate=100)]),
        handle="test-venue",
        opts=IngestOptions(),
    )
    notes2 = [make_note("p1", tcdate=100), make_note("p2", tcdate=300)]
    result = ingest_venue(
        paths=paths,
        adapter=FakeAdapter(FAKE_REF, notes2),
        handle="test-venue",
        opts=IngestOptions(),
    )
    assert result.incremental is True
    assert (result.items_seen, result.items_added) == (1, 1)
    assert result.max_tcdate == 300
    assert _paper_count(paths) == 2
    raw = paths.raw_venue_dir("openreview", "test-venue") / "submissions.jsonl"
    assert len(raw.read_text().strip().splitlines()) == 2  # merged: p1 kept + p2 added


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    result = ingest_venue(
        paths=paths,
        adapter=FakeAdapter(FAKE_REF, [make_note("p1")]),
        handle="test-venue",
        opts=IngestOptions(dry_run=True),
    )
    assert result.dry_run is True
    assert result.items_added == 1
    assert _paper_count(paths) == 0  # no rows written
    assert not (paths.raw_venue_dir("openreview", "test-venue") / "submissions.jsonl").exists()


def test_partial_failure_is_tolerated(tmp_path: Path) -> None:
    notes = [make_note("p1"), make_note("BAD-NOTE"), make_note("p2", tcdate=50)]
    paths = _paths(tmp_path)
    result = ingest_venue(
        paths=paths, adapter=FakeAdapter(FAKE_REF, notes), handle="test-venue", opts=IngestOptions()
    )
    assert result.status == "partial"
    assert result.items_failed == 1
    assert result.items_added == 2
    assert result.warnings
    assert _paper_count(paths) == 2


def test_items_seen_consistent_with_persisted_run(tmp_path: Path) -> None:
    notes = [make_note("p1"), make_note("BAD-NOTE"), make_note("p2", tcdate=50)]
    paths = _paths(tmp_path)
    result = ingest_venue(
        paths=paths, adapter=FakeAdapter(FAKE_REF, notes), handle="test-venue", opts=IngestOptions()
    )
    conn = connect(paths.db)
    try:
        persisted = conn.execute(
            "SELECT items_seen FROM ingest_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
    finally:
        conn.close()
    assert result.items_seen == persisted == 3  # raw notes seen, incl. the failed one


def test_incremental_catches_edited_note_and_status_flip(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    under = make_note(
        "p1", venueid=FAKE_REF.submission_venueid or "", tcdate=50, tmdate=100, venue="Test 2025"
    )
    ingest_venue(
        paths=paths,
        adapter=FakeAdapter(FAKE_REF, [under]),
        handle="test-venue",
        opts=IngestOptions(),
    )
    assert _status(paths, "p1") == "under_review"

    # Same note, edited after decisions: now accepted, higher tmdate (same tcdate).
    accepted = make_note(
        "p1",
        venueid=FAKE_REF.published_venueid or "",
        tcdate=50,
        tmdate=500,
        venue="Test 2025 oral",
    )
    result = ingest_venue(
        paths=paths,
        adapter=FakeAdapter(FAKE_REF, [accepted]),
        handle="test-venue",
        opts=IngestOptions(),
    )
    assert result.incremental is True
    assert (result.items_seen, result.items_added, result.items_updated) == (1, 0, 1)
    assert _status(paths, "p1") == "accepted"  # the edit-catch flipped the status
    raw = paths.raw_venue_dir("openreview", "test-venue") / "submissions.jsonl"
    assert len(raw.read_text().strip().splitlines()) == 1  # merged, not duplicated


def test_venues_add_refuses_remapping_ingested_slug(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    ingest_venue(
        paths=paths,
        adapter=FakeAdapter(FAKE_REF, [make_note("p1")]),
        handle="test-venue",
        opts=IngestOptions(),
    )
    with pytest.raises(UsageError):
        add_local_venue(paths, "test-venue", "Other.cc/2099/Conference")
