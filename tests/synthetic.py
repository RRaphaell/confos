"""Hand-crafted OpenReview-shaped notes + a FakeAdapter for deterministic tests.

These let us exercise the full ingest pipeline (normalize → upsert → watermark) without
the network and with precise control over edge cases (status buckets, author-identity
variants, missing fields).
"""

from __future__ import annotations

from collections.abc import Iterator

from confos.adapters.base import RawNote
from confos.adapters.openreview import OpenReviewAdapter
from confos.aliases import NormalizeAliases
from confos.models import IngestOptions, NormalizedPaper, VenueRef

FAKE_REF = VenueRef(
    slug="test-venue",
    source="openreview",
    source_venue_id="Test.cc/2025/Conference",
    published_venueid="Test.cc/2025/Conference",
    submission_venueid="Test.cc/2025/Conference/Submission",
    withdrawn_venueid="Test.cc/2025/Conference/Withdrawn_Submission",
    desk_rejected_venueid="Test.cc/2025/Conference/Desk_Rejected_Submission",
    rejected_venueid="Test.cc/2025/Conference/Rejected_Submission",
    submission_name="Submission",
    display_name="Test 2025",
    year=2025,
)


def make_note(
    note_id: str,
    *,
    venueid: str = FAKE_REF.published_venueid or "",
    authors: list[str] | None = None,
    authorids: list[str] | None = None,
    keywords: list[str] | None = None,
    title: str = "A Paper",
    abstract: str = "An abstract.",
    venue: str = "Test 2025 poster",
    pdf: str | None = "/pdf/abc123.pdf",
    bibtex: str | None = "@inproceedings{x2025, title={A Paper}}",
    supplementary_material: str | None = None,
    tcdate: int = 1000,
    tmdate: int = 2000,
    number: int = 1,
) -> RawNote:
    content: dict[str, object] = {
        "title": {"value": title},
        "abstract": {"value": abstract},
        "authors": {"value": authors if authors is not None else ["Alice Smith"]},
        "authorids": {"value": authorids if authorids is not None else ["~Alice_Smith1"]},
        "keywords": {"value": keywords if keywords is not None else ["agents"]},
        "venueid": {"value": venueid},
        "venue": {"value": venue},
    }
    if pdf is not None:
        content["pdf"] = {"value": pdf}
    if bibtex is not None:
        content["_bibtex"] = {"value": bibtex}
    if supplementary_material is not None:
        content["supplementary_material"] = {"value": supplementary_material}
    return {
        "id": note_id,
        "number": number,
        "tcdate": tcdate,
        "tmdate": tmdate,
        "pdate": None,
        "content": content,
    }


class FakeAdapter:
    """A SourceAdapter that yields canned notes; normalize uses the real OpenReview logic.

    A note whose id is ``"BAD-NOTE"`` raises during normalize, to exercise the
    partial-failure path.
    """

    name = "openreview"

    def __init__(self, ref: VenueRef, notes: list[RawNote]) -> None:
        self._ref = ref
        self._notes = notes
        self._real = OpenReviewAdapter()

    def resolve_venue(self, slug_or_id: str) -> VenueRef:
        return self._ref

    def fetch_notes(
        self,
        ref: VenueRef,
        opts: IngestOptions,
        *,
        since_tcdate: int | None = None,
        since_tmdate: int | None = None,
    ) -> Iterator[RawNote]:
        incremental = since_tcdate is not None and not opts.force
        if not incremental:
            yield from self._notes
            return
        # Hybrid: new (tcdate past watermark) + edited (tmdate past watermark), deduped.
        collected: dict[str, RawNote] = {}
        for note in self._notes:
            tcdate = int(note.get("tcdate") or 0)
            tmdate = int(note.get("tmdate") or 0)
            is_new = since_tcdate is not None and tcdate > since_tcdate
            is_edited = since_tmdate is not None and tmdate > since_tmdate
            if is_new or is_edited:
                collected[str(note["id"])] = note
        yield from collected.values()

    def normalize(
        self, raw: RawNote, ref: VenueRef, *, aliases: NormalizeAliases | None = None
    ) -> NormalizedPaper:
        if raw.get("id") == "BAD-NOTE":
            raise ValueError("synthetic normalize failure")
        return self._real.normalize(raw, ref, aliases=aliases)
