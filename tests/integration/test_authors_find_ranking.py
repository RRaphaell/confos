"""Acceptance test for `authors find` — a fixed, hand-constructed expected ranking.

RANKING §3: a fixture with a KNOWN expected order makes the differentiator testable, not
vibes. The corpus is designed so the order is deterministic regardless of exact bm25:

* Alice is on 3 matching papers, Bob on 2, Carol/Dave/Eve on 1 each. Since
  ``score = count + 0.5·bm25_sum`` with ``bm25_sum ≤ count`` and the count tie-break,
  a higher matched_paper_count ALWAYS ranks first → Alice, then Bob.
* Carol/Dave/Eve each have ONE identical single-author paper → identical bm25 → an exact
  score tie → broken by author_id ascending (Carol < Dave < Eve).

Recency is 0 here (single venue), so it doesn't perturb the order.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from confos.models import IngestOptions
from confos.paths import Paths
from confos.services import ranking as ranking_service
from confos.services.ingest import ingest_venue
from tests.synthetic import FAKE_REF, FakeAdapter, make_note

PUB = FAKE_REF.published_venueid or ""


@pytest.fixture
def ranked_corpus(tmp_path: Path) -> Paths:
    paths = Paths(home=tmp_path / "store")
    notes = [
        make_note(
            "pa1",
            title="zylex one",
            keywords=["zylex"],
            authors=["Alice"],
            authorids=["~Alice_A1"],
            venueid=PUB,
        ),
        make_note(
            "pa2",
            title="zylex two",
            keywords=["zylex"],
            authors=["Alice", "Bob"],
            authorids=["~Alice_A1", "~Bob_B1"],
            venueid=PUB,
        ),
        make_note(
            "pa3",
            title="zylex three",
            keywords=["zylex"],
            authors=["Alice", "Bob"],
            authorids=["~Alice_A1", "~Bob_B1"],
            venueid=PUB,
        ),
        # Carol / Dave / Eve: one identical single-author paper each → exact tie.
        make_note(
            "pc1",
            title="zylex solo",
            keywords=["zylex"],
            authors=["Carol"],
            authorids=["~Carol_C1"],
            venueid=PUB,
        ),
        make_note(
            "pd1",
            title="zylex solo",
            keywords=["zylex"],
            authors=["Dave"],
            authorids=["~Dave_D1"],
            venueid=PUB,
        ),
        make_note(
            "pe1",
            title="zylex solo",
            keywords=["zylex"],
            authors=["Eve"],
            authorids=["~Eve_E1"],
            venueid=PUB,
        ),
        # A non-matching paper, to ensure the topic filter excludes it.
        make_note(
            "px1",
            title="unrelated work",
            keywords=["other"],
            authors=["Zed"],
            authorids=["~Zed_Z1"],
            venueid=PUB,
        ),
    ]
    ingest_venue(
        paths=paths, adapter=FakeAdapter(FAKE_REF, notes), handle="test-venue", opts=IngestOptions()
    )
    return paths


def test_authors_find_reproduces_expected_ranking(ranked_corpus: Paths) -> None:
    result = ranking_service.find_authors(ranked_corpus, "zylex", venue="test-venue", limit=20)
    authors = result["authors"]
    ids = [a["author_id"] for a in authors]
    assert ids == ["~Alice_A1", "~Bob_B1", "~Carol_C1", "~Dave_D1", "~Eve_E1"]
    assert [a["matched_paper_count"] for a in authors] == [3, 2, 1, 1, 1]
    # Zed (non-matching paper) is excluded entirely.
    assert "~Zed_Z1" not in ids
    # scores are non-increasing
    scores = [a["score"] for a in authors]
    assert scores == sorted(scores, reverse=True)
    # single-venue → recency bonus is always 0 (RANKING §2)
    assert all(a["score_components"]["recency_bonus"] == 0.0 for a in authors)


def test_authors_find_provenance_and_explanation(ranked_corpus: Paths) -> None:
    alice = ranking_service.find_authors(ranked_corpus, "zylex", venue="test-venue")["authors"][0]
    assert alice["score_components"]["paper_count"] == 3
    assert len(alice["matched_papers"]) == 3
    assert all(
        m["url"].startswith("https://openreview.net/forum?id=") for m in alice["matched_papers"]
    )
    assert "3 paper(s) matching 'zylex'" in alice["why_relevant"]
    assert "matched_papers" in alice and alice["matched_papers"][0]["bm25"] is not None


def test_coauthors_ranked_by_shared_papers(ranked_corpus: Paths) -> None:
    result = ranking_service.coauthors(ranked_corpus, "~Alice_A1")
    assert result["author"]["author_id"] == "~Alice_A1"
    co = result["coauthors"]
    assert [c["author_id"] for c in co] == ["~Bob_B1"]  # only shared coauthor
    assert co[0]["shared_papers"] == 2  # pa2 + pa3


def test_authors_find_recency_bonus_multi_venue(tmp_path: Path) -> None:
    # Two venues across two years; an author with the newer paper gets a recency bump.
    paths = Paths(home=tmp_path / "store")
    ref_2024 = FAKE_REF.model_copy(
        update={
            "slug": "v2024",
            "source_venue_id": "Test.cc/2024/Conference",
            "published_venueid": "Test.cc/2024/Conference",
            "year": 2024,
        }
    )
    ref_2026 = FAKE_REF.model_copy(
        update={
            "slug": "v2026",
            "source_venue_id": "Test.cc/2026/Conference",
            "published_venueid": "Test.cc/2026/Conference",
            "year": 2026,
        }
    )
    ingest_venue(
        paths=paths,
        adapter=FakeAdapter(
            ref_2024,
            [
                make_note(
                    "old",
                    title="zeta paper",
                    keywords=["zeta"],
                    authors=["Old"],
                    authorids=["~Old_1"],
                    venueid="Test.cc/2024/Conference",
                )
            ],
        ),
        handle="v2024",
        opts=IngestOptions(),
    )
    ingest_venue(
        paths=paths,
        adapter=FakeAdapter(
            ref_2026,
            [
                make_note(
                    "new",
                    title="zeta paper",
                    keywords=["zeta"],
                    authors=["New"],
                    authorids=["~New_1"],
                    venueid="Test.cc/2026/Conference",
                )
            ],
        ),
        handle="v2026",
        opts=IngestOptions(),
    )
    # No --venue → multi-venue scope → recency applies.
    authors = ranking_service.find_authors(paths, "zeta", venue=None)["authors"]
    by_id = {a["author_id"]: a for a in authors}
    assert by_id["~New_1"]["score_components"]["recency_bonus"] > 0.0
    assert by_id["~Old_1"]["score_components"]["recency_bonus"] == 0.0
