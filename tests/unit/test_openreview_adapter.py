"""OpenReviewAdapter.normalize + venue-id mapping (D4 status, D5 identity)."""

from __future__ import annotations

import pytest

from confos.adapters.base import RawNote, extract_year, slugify_venue_id
from confos.adapters.openreview import OpenReviewAdapter
from confos.errors import UsageError
from confos.models import NormalizedPaper
from tests.synthetic import FAKE_REF, make_note

ADAPTER = OpenReviewAdapter()


def _normalize(note: RawNote) -> NormalizedPaper:
    return ADAPTER.normalize(note, FAKE_REF)


def test_status_accepted() -> None:
    paper = _normalize(make_note("p1", venueid=FAKE_REF.published_venueid or ""))
    assert paper.status == "accepted"


def test_status_under_review() -> None:
    paper = _normalize(
        make_note("p2", venueid=FAKE_REF.submission_venueid or "", venue="Test 2025")
    )
    assert paper.status == "under_review"


def test_status_withdrawn_and_desk_rejected() -> None:
    w = _normalize(make_note("p3", venueid=FAKE_REF.withdrawn_venueid or ""))
    d = _normalize(make_note("p4", venueid=FAKE_REF.desk_rejected_venueid or ""))
    assert w.status == "withdrawn"
    assert d.status == "desk_rejected"


def test_status_unknown_bucket() -> None:
    paper = _normalize(make_note("p5", venueid="Test.cc/2025/Conference/Some_Other_Bucket"))
    assert paper.status == "unknown"


def test_acceptance_type_from_venue_string() -> None:
    oral = _normalize(make_note("p6", venue="Test 2025 oral"))
    poster = _normalize(make_note("p7", venue="Test 2025 poster"))
    assert oral.acceptance_type == "oral"
    assert poster.acceptance_type == "poster"


def test_author_identity_variants() -> None:
    paper = _normalize(
        make_note(
            "pX",
            authors=["Alice Smith", "Bob Tan", "Carol No-Id"],
            authorids=["~Alice_Smith1", "bob@mit.edu"],  # Carol has no id
        )
    )
    alice, bob, carol = paper.authors
    assert alice.author_id == "~Alice_Smith1" and alice.data_quality == "resolved"
    assert alice.profile_url == "https://openreview.net/profile?id=~Alice_Smith1"
    assert bob.author_id == "email:bob@mit.edu" and bob.data_quality == "low"
    assert bob.affiliation == "MIT"  # seeded org from email domain
    assert carol.author_id.startswith("name:carol-no-id#pX-2")
    assert carol.data_quality == "unresolved"
    # positions preserved (S6)
    assert [a.position for a in paper.authors] == [0, 1, 2]


def test_topics_and_provenance_url() -> None:
    paper = _normalize(make_note("aBcD", keywords=["LLM Agents", "llm agents", "Memory"]))
    assert paper.topics == ["llm agents", "memory"]
    assert paper.url == "https://openreview.net/forum?id=aBcD"


def test_missing_fields_are_safe() -> None:
    note = make_note("p8", keywords=[])
    note["content"].pop("title")
    note["content"].pop("abstract")
    paper = _normalize(note)
    assert paper.title == ""
    assert paper.abstract == ""
    assert paper.topics == []


def test_scalar_keyword_and_author_fields_are_safe() -> None:
    # A bare string where a list is expected must NOT iterate char-by-char.
    note = make_note("pZ")
    note["content"]["keywords"] = {"value": "agents"}
    note["content"]["authors"] = {"value": "Alice Smith"}
    note["content"]["authorids"] = {"value": "~Alice_Smith1"}
    paper = _normalize(note)
    assert paper.keywords == []
    assert paper.topics == []
    assert paper.authors == []


def test_empty_id_raises() -> None:
    note = make_note("x")
    note["id"] = ""
    with pytest.raises(ValueError):
        _normalize(note)


def test_map_handle_alias_passthrough_and_error() -> None:
    assert ADAPTER._map_handle("neurips-2025") == ("NeurIPS.cc/2025/Conference", "neurips-2025")
    assert ADAPTER._map_handle("ICLR.cc/2025/Workshop/MLMP") == (
        "ICLR.cc/2025/Workshop/MLMP",
        "iclr-2025-workshop-mlmp",
    )
    with pytest.raises(UsageError):
        ADAPTER._map_handle("totally-unknown")


def test_slug_and_year_helpers() -> None:
    assert slugify_venue_id("NeurIPS.cc/2025/Conference") == "neurips-2025"
    assert extract_year("ICLR.cc/2026/Conference") == 2026
    assert extract_year("no-year-here") is None
