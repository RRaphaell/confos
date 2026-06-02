"""Domain models (pydantic v2) at the adapter ↔ service boundary.

These are the typed objects an adapter produces and the ingest service consumes. They
are deliberately *normalized* shapes — free of any source-specific quirks — so a future
adapter (AIE/PMLR/OpenAlex) can produce the same objects without changing the service or
repositories (ARCHITECTURE §9, D10). Read-side query models are added in later phases.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PaperStatus = Literal[
    "accepted", "under_review", "withdrawn", "desk_rejected", "rejected", "unknown"
]
DataQuality = Literal["resolved", "low", "unresolved"]
IngestStatus = Literal["ok", "partial", "error"]


class VenueRef(BaseModel):
    """A resolved venue: the user handle plus everything needed to fetch + classify it."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    source: str = "openreview"
    source_venue_id: str
    published_venueid: str | None = None  # raw venueid that marks 'accepted'
    submission_venueid: str | None = None  # under-review bucket → 'under_review'
    withdrawn_venueid: str | None = None
    desk_rejected_venueid: str | None = None
    rejected_venueid: str | None = None  # post-review reject bucket → 'rejected'
    submission_name: str | None = None  # e.g. 'Submission' (read from the group)
    display_name: str | None = None
    year: int | None = None
    url: str | None = None


class IngestOptions(BaseModel):
    """Knobs for a single ingest run (CLI flags map straight onto these)."""

    model_config = ConfigDict(extra="forbid")

    include_decisions: bool = False
    force: bool = False
    dry_run: bool = False


class NormalizedAuthor(BaseModel):
    """One author position on one paper, with a stable identity (D5)."""

    model_config = ConfigDict(extra="forbid")

    author_id: str  # profile id | email:<addr> | name:<slug>#<paper>-<pos>
    profile_id: str | None
    display_name: str
    position: int  # 0-based author order (S6)
    raw_name: str
    affiliation: str | None = None
    country: str | None = None
    data_quality: DataQuality = "resolved"
    profile_url: str | None = None


class NormalizedPaper(BaseModel):
    """A paper ready to upsert: derived status, normalized topics, ordered authors."""

    model_config = ConfigDict(extra="forbid")

    paper_id: str  # OpenReview note id == public id (D5)
    venue_slug: str
    number: int | None = None
    title: str = ""
    abstract: str = ""
    tldr: str | None = None
    keywords: list[str] = Field(default_factory=list)
    primary_area: str | None = None
    status: PaperStatus = "unknown"
    acceptance_type: str | None = None  # oral|spotlight|poster|null
    raw_venueid: str | None = None
    venue_string: str | None = None
    url: str = ""
    pdf_url: str | None = None  # absolute link to the PDF, or None
    bibtex: str | None = None  # the note's _bibtex citation block, verbatim
    supplementary_url: str | None = None  # absolute link to supplementary material, or None
    pdate: int | None = None
    tcdate: int | None = None
    tmdate: int | None = None
    authors: list[NormalizedAuthor] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)


class IngestResult(BaseModel):
    """Outcome of an ingest run (drives the command's output + ingest_runs row)."""

    model_config = ConfigDict(extra="forbid")

    venue: str
    status: IngestStatus = "ok"
    items_seen: int = 0
    items_added: int = 0
    items_updated: int = 0
    items_failed: int = 0
    max_tcdate: int | None = None
    max_tmdate: int | None = None
    dry_run: bool = False
    incremental: bool = False
    raw_path: str | None = None
    warnings: list[str] = Field(default_factory=list)
