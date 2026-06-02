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


def test_status_rejected_from_explicit_venueid() -> None:
    paper = _normalize(make_note("p5r", venueid=FAKE_REF.rejected_venueid or ""))
    assert paper.status == "rejected"


def test_status_rejected_from_suffix_fallback() -> None:
    # A snapshot whose venue.json predates rejected_venueid (None on the ref) must still
    # reclassify via the conventional `/Rejected_Submission` suffix — the no-network
    # `index rebuild` upgrade path.
    ref = FAKE_REF.model_copy(update={"rejected_venueid": None})
    paper = ADAPTER.normalize(
        make_note("p5s", venueid="Test.cc/2025/Conference/Rejected_Submission"), ref
    )
    assert paper.status == "rejected"


def test_desk_rejected_not_confused_with_rejected_suffix() -> None:
    # `…/Desk_Rejected_Submission` must stay desk_rejected, not match the rejected suffix.
    ref = FAKE_REF.model_copy(update={"rejected_venueid": None})
    paper = ADAPTER.normalize(
        make_note("p5d", venueid="Test.cc/2025/Conference/Desk_Rejected_Submission"), ref
    )
    assert paper.status == "desk_rejected"


def test_captures_pdf_bibtex_supplementary() -> None:
    paper = _normalize(
        make_note(
            "p9",
            pdf="/pdf/9d1f.pdf",
            bibtex="@inproceedings{a2025,title={X}}",
            supplementary_material="/attachment/deadbeef.zip",
        )
    )
    assert paper.pdf_url == "https://openreview.net/pdf/9d1f.pdf"  # server path → absolute
    assert paper.bibtex == "@inproceedings{a2025,title={X}}"  # verbatim, not prefixed
    assert paper.supplementary_url == "https://openreview.net/attachment/deadbeef.zip"


def test_absolute_pdf_url_passed_through_and_missing_is_none() -> None:
    kept = _normalize(make_note("p10", pdf="https://example.org/x.pdf"))
    assert kept.pdf_url == "https://example.org/x.pdf"
    missing = _normalize(make_note("p11", pdf=None, bibtex=None, supplementary_material=None))
    assert missing.pdf_url is None
    assert missing.bibtex is None
    assert missing.supplementary_url is None


def test_abs_url_empty_and_bare_relative_edge_cases() -> None:
    # Empty string is treated as missing (None), not absolutized to the bare host.
    assert _normalize(make_note("p12", pdf="")).pdf_url is None
    # A bare relative value (no leading '/', not http) is returned verbatim — we only
    # prefix the web host onto server-absolute paths.
    assert _normalize(make_note("p13", pdf="abc.pdf")).pdf_url == "abc.pdf"


def test_supplementary_custom_field_fallback() -> None:
    # Some workshops store the link under a custom `Supplementary` field (absolute URL)
    # rather than the standard `supplementary_material`.
    note = make_note("p14", supplementary_material=None)
    note["content"]["Supplementary"] = {"value": "https://github.com/x/y"}
    assert _normalize(note).supplementary_url == "https://github.com/x/y"


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
