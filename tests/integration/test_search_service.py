"""Search + explore services over a known synthetic corpus (offline, deterministic)."""

from __future__ import annotations

from pathlib import Path

import pytest

from confos.errors import ConfigError, NotFoundError
from confos.models import IngestOptions
from confos.paths import Paths
from confos.services import authors as authors_service
from confos.services import index as index_service
from confos.services import orgs as orgs_service
from confos.services import search as search_service
from confos.services import stats as stats_service
from confos.services.ingest import ingest_venue
from tests.synthetic import FAKE_REF, FakeAdapter, make_note

REF_2024 = FAKE_REF.model_copy(
    update={
        "slug": "test-venue-2024",
        "source_venue_id": "Test.cc/2024/Conference",
        "published_venueid": "Test.cc/2024/Conference",
        "submission_venueid": "Test.cc/2024/Conference/Submission",
        "year": 2024,
    }
)


@pytest.fixture
def corpus(tmp_path: Path) -> Paths:
    paths = Paths(home=tmp_path / "store")
    pub = FAKE_REF.published_venueid or ""
    sub = FAKE_REF.submission_venueid or ""
    notes_2025 = [
        make_note("aaa1", title="Agent memory", keywords=["agents", "memory"], venueid=pub),
        make_note(
            "bbb2",
            title="Tool use for language models",
            keywords=["tool use"],
            authors=["Bob Tan"],
            authorids=["bob@mit.edu"],
            venueid=pub,
        ),
        make_note(
            "ccc3",
            title="Evaluating agents",
            keywords=["evals", "agents"],
            venueid=sub,
            venue="Test 2025",
        ),
        make_note("dup-a", title="zeta zeta zeta", keywords=["zeta"], venueid=pub),
        make_note("dup-b", title="zeta zeta zeta", keywords=["zeta"], venueid=pub),
    ]
    ingest_venue(
        paths=paths,
        adapter=FakeAdapter(FAKE_REF, notes_2025),
        handle="test-venue",
        opts=IngestOptions(),
    )
    ingest_venue(
        paths=paths,
        adapter=FakeAdapter(
            REF_2024,
            [
                make_note(
                    "old1",
                    title="Early agents",
                    keywords=["agents"],
                    venueid=REF_2024.published_venueid or "",
                )
            ],
        ),
        handle="test-venue-2024",
        opts=IngestOptions(),
    )
    return paths


def _ids(results: list[dict[str, object]]) -> list[str]:
    return [str(r["paper_id"]) for r in results]


def test_search_matches_across_venues(corpus: Paths) -> None:
    results = search_service.search_papers(corpus, "agents", limit=50)
    assert set(_ids(results)) == {"aaa1", "ccc3", "old1"}


def test_search_venue_filter(corpus: Paths) -> None:
    results = search_service.search_papers(corpus, "agents", venue="test-venue", limit=50)
    assert set(_ids(results)) == {"aaa1", "ccc3"}


def test_search_year_filter(corpus: Paths) -> None:
    results = search_service.search_papers(corpus, "agents", year=2024, limit=50)
    assert _ids(results) == ["old1"]


def test_search_accepted_only(corpus: Paths) -> None:
    results = search_service.search_papers(corpus, "agents", accepted_only=True, limit=50)
    assert set(_ids(results)) == {"aaa1", "old1"}  # ccc3 is under_review


def test_search_org_filter(corpus: Paths) -> None:
    results = search_service.search_papers(corpus, "tool", org="MIT", limit=50)
    assert _ids(results) == ["bbb2"]
    assert search_service.search_papers(corpus, "agents", org="MIT", limit=50) == []


def test_search_is_deterministic_with_id_tiebreak(corpus: Paths) -> None:
    first = _ids(search_service.search_papers(corpus, "zeta", limit=50))
    second = _ids(search_service.search_papers(corpus, "zeta", limit=50))
    assert first == second == ["dup-a", "dup-b"]  # equal bm25 → id asc tiebreak


def test_search_results_carry_provenance(corpus: Paths) -> None:
    paper = search_service.search_papers(corpus, "memory", limit=1)[0]
    assert paper["url"] == "https://openreview.net/forum?id=aaa1"
    assert paper["venue"] == "test-venue"
    assert "bm25" in paper


def test_get_paper_and_related(corpus: Paths) -> None:
    paper = search_service.get_paper(corpus, "aaa1", with_related=True)
    assert paper["title"] == "Agent memory"
    assert "abstract" in paper
    assert "aaa1" not in [p["paper_id"] for p in paper["related"]]  # never itself


def test_get_paper_not_found(corpus: Paths) -> None:
    with pytest.raises(NotFoundError):
        search_service.get_paper(corpus, "no-such-id")


def test_authors_search_show_papers(corpus: Paths) -> None:
    matches = authors_service.search_authors(corpus, "bob", limit=10)
    assert any(a["display_name"] == "Bob Tan" for a in matches)

    shown = authors_service.show_author(corpus, "email:bob@mit.edu")
    assert shown["affiliation_current"] == "MIT"
    assert shown["paper_count"] == 1

    papers = authors_service.author_papers(corpus, "email:bob@mit.edu")
    assert _ids(papers["papers"]) == ["bbb2"]


def test_orgs_top_and_papers(corpus: Paths) -> None:
    top = orgs_service.top_orgs(corpus, limit=10)
    assert any(o["name"] == "MIT" and o["papers"] == 1 for o in top["rows"])
    assert top["data_quality"]["papers_with_signal"] == 1  # coverage parity with stats

    org = orgs_service.org_papers(corpus, "MIT")
    assert _ids(org["papers"]) == ["bbb2"]


def test_search_limit_zero_returns_nothing(corpus: Paths) -> None:
    assert search_service.search_papers(corpus, "agents", limit=0) == []


def test_rebuild_aborts_cleanly_on_malformed_venue_json(corpus: Paths) -> None:
    # A corrupt venue.json must fail BEFORE any destructive write — store untouched,
    # FTS not wiped (CR1/CR3 regression).
    (corpus.raw_venue_dir("openreview", "test-venue") / "venue.json").write_text("not json")
    before = index_service.status(corpus)["counts"]
    with pytest.raises(ConfigError):
        index_service.rebuild(corpus)
    after = index_service.status(corpus)["counts"]
    assert before == after
    assert search_service.search_papers(corpus, "agents", limit=50)  # FTS intact


def test_stats_overview(corpus: Paths) -> None:
    overview = stats_service.overview(corpus)
    assert overview["papers"] == 6
    assert overview["status"]["under_review"] == 1  # ccc3
    assert overview["status"]["accepted"] == 5
    assert overview["venues"] == 2
    # Honesty caveat: the status mix carries a note so it is not read as an acceptance rate.
    assert "acceptance rate" in overview["status_note"]


def test_stats_topics_coverage(corpus: Paths) -> None:
    result = stats_service.topics(corpus)
    keys = {r["key"] for r in result["rows"]}
    assert "agents" in keys
    dq = result["data_quality"]
    assert (dq["papers_total"], dq["papers_with_signal"], dq["unknown"]) == (6, 6, 0)


def test_rebuild_preserves_unicode_line_separator(tmp_path: Path) -> None:
    # Regression: a U+2028 inside note text must survive `index rebuild`. The snapshot is
    # written ensure_ascii=False (D3), so the raw separator lands verbatim in
    # submissions.jsonl; reading it with str.splitlines() used to tear the record in two,
    # fail json.loads on both halves, and silently drop the paper (colm-2024 fell 299->298).
    # See confos.jsonl.read_jsonl_records.
    sep = chr(0x2028)
    paths = Paths(home=tmp_path / "store")
    pub = FAKE_REF.published_venueid or ""
    notes = [
        make_note("u1", title="Clean paper", keywords=["a"], venueid=pub),
        make_note(
            "u2",
            title=f"Sep{sep}arated",
            abstract=f"before{sep}after",
            keywords=["b"],
            venueid=pub,
        ),
    ]
    ingest_venue(
        paths=paths, adapter=FakeAdapter(FAKE_REF, notes), handle="test-venue", opts=IngestOptions()
    )
    assert stats_service.overview(paths)["papers"] == 2

    result = index_service.rebuild(paths)
    assert result["failed"] == 0
    assert result["papers"] == 2  # the U+2028 paper is not dropped on re-read
    assert stats_service.overview(paths)["papers"] == 2


def test_stats_orgs_is_honest_about_sparsity(corpus: Paths) -> None:
    result = stats_service.orgs(corpus)
    dq = result["data_quality"]
    assert dq["papers_total"] == 6
    assert dq["papers_with_signal"] == 1  # only bbb2 (bob@mit.edu) has an affiliation
    assert dq["unknown"] == 5
    assert dq["low_confidence"] == 1  # the email-domain affiliation is low confidence
    assert dq["method"] == "author_affiliation_profile_v1"
    assert any(r["key"] == "MIT" for r in result["rows"])


def test_stats_countries(corpus: Paths) -> None:
    result = stats_service.countries(corpus)
    assert any(r["key"] == "United States" for r in result["rows"])  # MIT → US
    assert result["data_quality"]["method"] == "affiliation_country_profile_v1"


def test_index_rebuild_is_idempotent(corpus: Paths) -> None:
    before = index_service.status(corpus)["counts"]
    result = index_service.rebuild(corpus)
    after = index_service.status(corpus)["counts"]
    assert result["papers"] == 6
    assert before == after  # rebuild reproduces identical counts
    # search still works after a rebuild
    assert set(_ids(search_service.search_papers(corpus, "agents", limit=50))) == {
        "aaa1",
        "ccc3",
        "old1",
    }
