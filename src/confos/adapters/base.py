"""The source-adapter seam plus venue-id helpers shared across adapters."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any, Protocol, runtime_checkable

from ..models import IngestOptions, NormalizedPaper, VenueRef

# A raw note is the source's payload, snapshotted verbatim to JSONL (the truth, D3).
RawNote = dict[str, Any]


@runtime_checkable
class SourceAdapter(Protocol):
    """Fetch + classify one source. Implementations live in this package."""

    name: str

    def resolve_venue(self, slug_or_id: str) -> VenueRef:
        """Resolve a user handle or raw source id into a full :class:`VenueRef`."""
        ...

    def fetch_notes(
        self, ref: VenueRef, opts: IngestOptions, *, since_tcdate: int | None = None
    ) -> Iterator[RawNote]:
        """Yield raw notes for the venue (paginated). ``since_tcdate`` enables incremental."""
        ...

    def normalize(self, raw: RawNote, ref: VenueRef) -> NormalizedPaper:
        """Turn one raw note into a normalized paper (pure; safe to replay from JSONL)."""
        ...


_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
# Domain/track labels dropped when deriving a slug from a raw venue id.
_SLUG_DROP = {"cc", "org", "com", "net", "www", "conference"}


def extract_year(venue_id: str) -> int | None:
    """Pull the 4-digit year out of a venue id, if present."""
    match = _YEAR_RE.search(venue_id)
    return int(match.group(0)) if match else None


def slugify_venue_id(venue_id: str) -> str:
    """Derive a readable slug from a raw venue id (passthrough case).

    ``NeurIPS.cc/2025/Conference`` → ``neurips-2025``;
    ``ICLR.cc/2025/Workshop/MLMP`` → ``iclr-2025-workshop-mlmp``.
    """
    tokens = re.split(r"[/.]", venue_id.lower())
    kept = [tok for tok in tokens if tok and tok not in _SLUG_DROP]
    slug = "-".join(kept)
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug or venue_id.lower()
