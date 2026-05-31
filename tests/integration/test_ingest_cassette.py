"""End-to-end ingest against a RECORDED OpenReview venue (vcrpy replay).

This proves the real OpenReviewAdapter resolves a venue, paginates the submission set,
and normalizes/upserts real API responses — without hitting the network in CI. The
cassette (``tests/fixtures/cassettes/mlmp_workshop.yaml``) is recorded once against
ICLR.cc/2025/Workshop/MLMP (33 papers). Re-record with::

    CONFOS_RECORD=1 uv run pytest tests/integration/test_ingest_cassette.py
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import vcr

from confos.adapters.openreview import OpenReviewAdapter
from confos.db.connection import connect
from confos.models import IngestOptions
from confos.paths import Paths
from confos.services.ingest import ingest_venue

CASSETTE_DIR = Path(__file__).parent.parent / "fixtures" / "cassettes"
CASSETTE = "mlmp_workshop.yaml"
VENUE_ID = "ICLR.cc/2025/Workshop/MLMP"
EXPECTED_PAPERS = 33

_recording = bool(os.environ.get("CONFOS_RECORD"))
_vcr = vcr.VCR(
    cassette_library_dir=str(CASSETTE_DIR),
    record_mode="once" if _recording else "none",
    match_on=["method", "host", "path", "query"],
    filter_headers=["authorization", "Authorization", "Cookie", "Set-Cookie"],
    decode_compressed_response=True,
)

pytestmark = pytest.mark.skipif(
    not _recording and not (CASSETTE_DIR / CASSETTE).exists(),
    reason="cassette not recorded; run with CONFOS_RECORD=1 once (needs network)",
)


def test_ingest_replays_real_venue(tmp_path: Path) -> None:
    paths = Paths(home=tmp_path / "store")
    adapter = OpenReviewAdapter()
    with _vcr.use_cassette(CASSETTE):
        result = ingest_venue(paths=paths, adapter=adapter, handle=VENUE_ID, opts=IngestOptions())

    assert result.status == "ok"
    assert result.items_seen == EXPECTED_PAPERS
    assert result.items_added == EXPECTED_PAPERS
    assert result.max_tcdate is not None

    conn = connect(paths.db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0] == EXPECTED_PAPERS
        assert conn.execute("SELECT COUNT(*) FROM papers_fts").fetchone()[0] == EXPECTED_PAPERS
        # Every paper carries a derived status and a forum URL (provenance).
        bad = conn.execute(
            "SELECT COUNT(*) FROM papers WHERE status = 'unknown' OR url NOT LIKE 'https://openreview.net/forum?id=%'"
        ).fetchone()[0]
        assert bad == 0
        # FTS is queryable.
        hits = conn.execute(
            "SELECT COUNT(*) FROM papers_fts WHERE papers_fts MATCH ?", ("neural",)
        ).fetchone()[0]
        assert hits > 0
    finally:
        conn.close()
