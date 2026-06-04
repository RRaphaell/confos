"""Phase 0: the `rejected` status bucket + captured pdf/bibtex/supplementary fields.

Exercises the full ingest → store → read path with the FakeAdapter (no network), plus the
headline upgrade path: a `index rebuild` reclassifies post-review rejects and backfills the
new columns from the raw snapshot alone — even when the snapshot's venue.json predates the
`rejected_venueid` field (the real on-disk store's situation).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from confos.adapters.base import RawNote
from confos.models import IngestOptions
from confos.paths import Paths
from confos.services import index as index_service
from confos.services import search as search_service
from confos.services import stats as stats_service
from confos.services.ingest import ingest_venue
from tests.conftest import RunCli
from tests.synthetic import FAKE_REF, FakeAdapter, make_note

PUB = FAKE_REF.published_venueid or ""
REJ = FAKE_REF.rejected_venueid or ""


def _notes() -> list[RawNote]:
    return [
        make_note(
            "acc1",
            venueid=PUB,
            pdf="/pdf/acc1.pdf",
            bibtex="@inproceedings{acc1,title={Accepted}}",
            supplementary_material="/attachment/acc1.zip",
        ),
        make_note("rej1", venueid=REJ, venue="Submitted to Test 2025"),  # post-review reject
    ]


def _ingest(home: Path) -> Paths:
    paths = Paths(home=home)
    ingest_venue(
        paths=paths,
        adapter=FakeAdapter(FAKE_REF, _notes()),
        handle="test-venue",
        opts=IngestOptions(),
    )
    return paths


def test_ingest_labels_rejected_and_captures_artifacts(tmp_path: Path) -> None:
    paths = _ingest(tmp_path / "store")

    status = stats_service.overview(paths, "test-venue")["status"]
    assert status == {"accepted": 1, "rejected": 1}  # no `unknown`

    paper = search_service.get_paper(paths, "acc1")
    assert paper["status"] == "accepted"
    assert paper["pdf_url"] == "https://openreview.net/pdf/acc1.pdf"
    assert paper["bibtex"].startswith("@inproceedings{acc1")
    assert paper["supplementary_url"] == "https://openreview.net/attachment/acc1.zip"


def test_rebuild_reclassifies_rejected_without_rejected_venueid(tmp_path: Path) -> None:
    # Simulate an existing v0.1.0 snapshot: strip `rejected_venueid` from venue.json so the
    # only signal is the `/Rejected_Submission` suffix. A no-network rebuild must still both
    # reclassify the reject AND backfill pdf/bibtex from the raw notes.
    paths = _ingest(tmp_path / "store")
    venue_json = paths.raw_venue_dir("openreview", "test-venue") / "venue.json"
    ref = json.loads(venue_json.read_text())
    ref.pop("rejected_venueid", None)
    venue_json.write_text(json.dumps(ref))

    result = index_service.rebuild(paths)
    assert result["papers"] == 2

    assert stats_service.overview(paths, "test-venue")["status"] == {"accepted": 1, "rejected": 1}
    assert search_service.get_paper(paths, "acc1")["pdf_url"].endswith("/pdf/acc1.pdf")


# --- CLI contract surfaces ---------------------------------------------------


@pytest.fixture
def phase0_home(confos_home: Path) -> Path:
    _ingest(confos_home)
    return confos_home


def test_cli_stats_overview_reports_rejected(run_cli: RunCli, phase0_home: Path) -> None:
    result = run_cli("stats", "overview", "--venue", "test-venue", "--json")
    assert result.exit_code == 0
    status = result.json()["data"]["status"]
    assert status.get("rejected") == 1
    assert "unknown" not in status


def test_cli_papers_show_exposes_pdf_and_bibtex(run_cli: RunCli, phase0_home: Path) -> None:
    result = run_cli("papers", "show", "acc1", "--json")
    assert result.exit_code == 0
    data = result.json()["data"]
    assert data["pdf_url"] == "https://openreview.net/pdf/acc1.pdf"
    assert data["bibtex"].startswith("@inproceedings{acc1")


def test_cli_papers_search_stays_lean_no_bibtex(run_cli: RunCli, phase0_home: Path) -> None:
    # The artifact fields are intentionally omitted from the lean list/search view.
    result = run_cli("papers", "search", "Paper", "--venue", "test-venue", "--json")
    assert result.exit_code == 0
    rows = result.json()["data"]
    assert rows and "bibtex" not in rows[0] and "pdf_url" not in rows[0]


def test_cli_stats_explain_under_plain_emits_coverage(run_cli: RunCli, phase0_home: Path) -> None:
    # P1-7: --explain was silently ignored under --plain; the data-quality block must appear.
    result = run_cli("stats", "topics", "--venue", "test-venue", "--plain", "--explain")
    assert result.exit_code == 0
    assert "data_quality." in result.stdout
