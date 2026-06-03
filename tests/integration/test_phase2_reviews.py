"""Phase 2: review capture → aggregates → `papers top`/`controversial`, reproduced offline.

Reviews ride in a note's details.replies; the FakeAdapter passes synthetic reviewed notes
through the real normalize/upsert path, so this exercises parsing, aggregation, the reviews
table, ranking, and the no-network rebuild — all deterministically.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from confos.adapters.base import RawNote
from confos.db.connection import connect
from confos.models import IngestOptions
from confos.paths import Paths
from confos.services import index as index_service
from confos.services import search as search_service
from confos.services.ingest import ingest_venue
from tests.conftest import RunCli
from tests.synthetic import FAKE_REF, FakeAdapter, make_note

PUB = FAKE_REF.published_venueid or ""


def _reviewed_notes() -> list[RawNote]:
    return [
        make_note(
            "hi",
            title="high rated agents",
            keywords=["agents"],
            venueid=PUB,
            reviews=[{"rating": 8}, {"rating": 8}, {"rating": 7}],
            decision="Accept (oral)",
        ),
        make_note(
            "mid",
            title="mid agents",
            keywords=["agents"],
            venueid=PUB,
            reviews=[{"rating": 5}, {"rating": 5}],
            decision="Accept (poster)",
        ),
        make_note(
            "div",
            title="divisive agents",
            keywords=["agents"],
            venueid=PUB,
            reviews=[{"rating": 2}, {"rating": 9}],
            decision="Reject",
        ),  # high variance
        make_note("none", title="unreviewed agents", keywords=["agents"], venueid=PUB),
    ]


def _ingest(home: Path) -> Paths:
    paths = Paths(home=home)
    ingest_venue(
        paths=paths,
        adapter=FakeAdapter(FAKE_REF, _reviewed_notes()),
        handle="test-venue",
        opts=IngestOptions(include_decisions=True),
    )
    return paths


def test_reviews_stored_and_aggregated(tmp_path: Path) -> None:
    paths = _ingest(tmp_path / "store")

    hi = search_service.get_paper(paths, "hi")
    assert hi["review_count"] == 3
    assert hi["rating_mean"] == pytest.approx(7.67, abs=0.01)
    assert hi["decision"] == "Accept (oral)"

    none = search_service.get_paper(paths, "none")
    assert none["review_count"] == 0
    assert none["rating_mean"] is None

    # Raw review rows exist for provenance.
    conn = connect(paths.db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM reviews WHERE paper_id='hi'").fetchone()[0] == 3
        assert conn.execute("SELECT COUNT(*) FROM reviews WHERE paper_id='none'").fetchone()[0] == 0
    finally:
        conn.close()


def test_papers_top_orders_by_rating(tmp_path: Path) -> None:
    paths = _ingest(tmp_path / "store")
    top = search_service.top_papers(paths, order="rating", venue="test-venue")
    ids = [p["paper_id"] for p in top]
    assert ids[0] == "hi"  # highest mean
    assert "none" not in ids  # unreviewed papers are excluded
    # ratings are descending
    ratings = [p["rating_mean"] for p in top]
    assert ratings == sorted(ratings, reverse=True)


def test_papers_controversial_orders_by_variance(tmp_path: Path) -> None:
    paths = _ingest(tmp_path / "store")
    rows = search_service.top_papers(paths, order="controversy", venue="test-venue", min_reviews=2)
    ids = [p["paper_id"] for p in rows]
    assert ids[0] == "div"  # [2,9] → highest std
    assert "none" not in ids  # needs >= 2 reviews


def test_topic_filter_on_top(tmp_path: Path) -> None:
    paths = _ingest(tmp_path / "store")
    top = search_service.top_papers(paths, order="rating", topic="divisive", venue="test-venue")
    assert [p["paper_id"] for p in top] == ["div"]  # FTS-scoped to the topic


def test_rebuild_reproduces_reviews(tmp_path: Path) -> None:
    paths = _ingest(tmp_path / "store")
    index_service.rebuild(paths)  # no network — replays details.replies from raw
    hi = search_service.get_paper(paths, "hi")
    assert hi["review_count"] == 3 and hi["rating_mean"] == pytest.approx(7.67, abs=0.01)
    top = search_service.top_papers(paths, order="rating", venue="test-venue")
    assert top[0]["paper_id"] == "hi"


# --- CLI ---------------------------------------------------------------------


@pytest.fixture
def reviews_home(confos_home: Path) -> Path:
    _ingest(confos_home)
    return confos_home


def test_cli_papers_top_json(run_cli: RunCli, reviews_home: Path) -> None:
    result = run_cli("papers", "top", "--venue", "test-venue", "--json")
    assert result.exit_code == 0
    rows = result.json()["data"]
    assert rows[0]["paper_id"] == "hi"
    assert rows[0]["review_count"] == 3 and "rating_mean" in rows[0]


def test_cli_papers_controversial_json(run_cli: RunCli, reviews_home: Path) -> None:
    result = run_cli("papers", "controversial", "--venue", "test-venue", "--json")
    assert result.exit_code == 0
    assert result.json()["data"][0]["paper_id"] == "div"
