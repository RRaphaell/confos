"""OpenReview v2 adapter — the only adapter in v1.

Fetches the FULL submission set via the venue's submission invitation and derives
``status`` locally from each note's raw ``venueid`` (D4 / ARCHITECTURE §8) — never a
separate "accepted only" network query. Anonymous reads by default; optional
credentials come from env only (never flags, never logged).
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from typing import Any

from ..config import DEFAULT_OPENREVIEW_BASEURL
from ..errors import NetworkError, UsageError
from ..models import NormalizedAuthor, NormalizedPaper, PaperStatus, VenueRef
from ..normalize.orgs import org_from_email
from ..normalize.topics import normalize_keywords
from .base import RawNote, extract_year, slugify_venue_id

# Curated alias map for major venues. Workshops/arbitrary venues use a raw id or
# `venues add` — we never derive ids algorithmically (research §3).
BUILTIN_VENUE_ALIASES: dict[str, str] = {
    "neurips-2023": "NeurIPS.cc/2023/Conference",
    "neurips-2024": "NeurIPS.cc/2024/Conference",
    "neurips-2025": "NeurIPS.cc/2025/Conference",
    "iclr-2024": "ICLR.cc/2024/Conference",
    "iclr-2025": "ICLR.cc/2025/Conference",
    "iclr-2026": "ICLR.cc/2026/Conference",
    "icml-2024": "ICML.cc/2024/Conference",
    "icml-2025": "ICML.cc/2025/Conference",
    "colm-2024": "colmweb.org/COLM/2024/Conference",
    "colm-2025": "colmweb.org/COLM/2025/Conference",
}

_ACCEPTANCE_TYPES = ("oral", "spotlight", "poster")


def _unwrap(content: dict[str, Any], key: str) -> Any:
    """Read a v2 ``{"value": X}`` content field defensively (v1 is flat)."""
    field = content.get(key)
    if isinstance(field, dict):
        return field.get("value")
    return field


def _slug_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "anon"


class OpenReviewAdapter:
    """SourceAdapter for the OpenReview v2 API."""

    name = "openreview"

    def __init__(self, baseurl: str = DEFAULT_OPENREVIEW_BASEURL, client: Any = None) -> None:
        self._baseurl = baseurl
        self._client = client

    # --- client (lazy, injectable for tests) ---------------------------------
    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = self._build_client()
        return self._client

    def _build_client(self) -> Any:
        try:
            import openreview

            return openreview.api.OpenReviewClient(
                baseurl=self._baseurl,
                username=os.environ.get("OPENREVIEW_USERNAME"),
                password=os.environ.get("OPENREVIEW_PASSWORD"),
            )
        except Exception as exc:
            raise NetworkError(
                f"Could not initialise the OpenReview client: {exc}",
                hint="Check your network connection (ingest needs api2.openreview.net).",
            ) from exc

    # --- adapter protocol ----------------------------------------------------
    def resolve_venue(self, slug_or_id: str) -> VenueRef:
        venue_id, slug = self._map_handle(slug_or_id)
        try:
            group = self.client.get_group(venue_id)
        except Exception as exc:
            raise NetworkError(
                f"Could not resolve venue '{slug_or_id}' on OpenReview: {exc}",
                hint="Check the id/slug with `confos venues search`, or your connection.",
            ) from exc
        content = group.content or {}
        return VenueRef(
            slug=slug,
            source=self.name,
            source_venue_id=venue_id,
            published_venueid=venue_id,
            submission_venueid=_unwrap(content, "submission_venue_id"),
            withdrawn_venueid=_unwrap(content, "withdrawn_venue_id"),
            desk_rejected_venueid=_unwrap(content, "desk_rejected_venue_id"),
            submission_name=_unwrap(content, "submission_name") or "Submission",
            display_name=_unwrap(content, "title") or slug,
            year=extract_year(venue_id),
            url=f"https://openreview.net/group?id={venue_id}",
        )

    def fetch_notes(
        self, ref: VenueRef, opts: Any, *, since_tcdate: int | None = None
    ) -> Iterator[RawNote]:
        invitation = f"{ref.source_venue_id}/-/{ref.submission_name or 'Submission'}"
        kwargs: dict[str, Any] = {"invitation": invitation, "sort": "tcdate:asc"}
        if since_tcdate is not None and not opts.force:
            kwargs["mintcdate"] = since_tcdate + 1
        if opts.include_decisions:
            kwargs["details"] = "replies"
        try:
            notes = self.client.get_all_notes(**kwargs)
        except Exception as exc:
            raise NetworkError(
                f"Failed to fetch submissions for '{ref.slug}': {exc}",
                hint="Retry; if it persists, OpenReview may be unreachable.",
            ) from exc
        for note in notes:
            yield _note_to_raw(note)

    def normalize(self, raw: RawNote, ref: VenueRef) -> NormalizedPaper:
        content = raw.get("content") or {}
        paper_id = str(raw.get("id") or "")
        raw_venueid = _unwrap(content, "venueid")
        venue_string = _unwrap(content, "venue")
        status = _derive_status(raw_venueid, ref)
        keywords_raw = _unwrap(content, "keywords") or []
        keywords = [k for k in keywords_raw if isinstance(k, str)]
        return NormalizedPaper(
            paper_id=paper_id,
            venue_slug=ref.slug,
            number=raw.get("number"),
            title=_unwrap(content, "title") or "",
            abstract=_unwrap(content, "abstract") or "",
            tldr=_unwrap(content, "TLDR"),
            keywords=keywords,
            primary_area=_unwrap(content, "primary_area"),
            status=status,
            acceptance_type=(
                _derive_acceptance_type(venue_string, raw.get("details"))
                if status == "accepted"
                else None
            ),
            raw_venueid=raw_venueid,
            venue_string=venue_string,
            url=f"https://openreview.net/forum?id={paper_id}",
            pdate=raw.get("pdate"),
            tcdate=raw.get("tcdate"),
            tmdate=raw.get("tmdate"),
            authors=_normalize_authors(content, paper_id),
            topics=normalize_keywords(keywords),
        )

    def search_venues(self, query: str, *, limit: int = 25) -> list[dict[str, str]]:
        """Find venues matching a free-text query (network, best-effort).

        Combines reliable matches from the built-in alias map with an OpenReview group
        prefix search. Host casing is irregular (``NeurIPS.cc`` vs ``colmweb.org``), so
        the network leg tries a few case variants of the first name token and filters to
        conference/workshop groups; venues it can't construct a prefix for are still
        reachable via the alias map or a raw id.
        """
        tokens = query.lower().split()
        year = next((tok for tok in tokens if tok.isdigit() and len(tok) == 4), None)
        name_tokens = [tok for tok in tokens if not (tok.isdigit() and len(tok) == 4)]

        results: list[dict[str, str]] = []
        seen: set[str] = set()
        for slug, venue_id in BUILTIN_VENUE_ALIASES.items():
            haystack = f"{slug} {venue_id}".lower()
            if all(tok in haystack for tok in tokens):
                results.append({"slug": slug, "source_venue_id": venue_id, "via": "alias"})
                seen.add(venue_id)

        if name_tokens:
            for group_id in self._prefix_search(name_tokens[0], year, limit=limit * 4):
                low = group_id.lower()
                if group_id in seen:
                    continue
                if year and year not in low:
                    continue
                if not (low.endswith("/conference") or "/workshop/" in low):
                    continue
                results.append(
                    {
                        "slug": slugify_venue_id(group_id),
                        "source_venue_id": group_id,
                        "via": "openreview",
                    }
                )
                seen.add(group_id)
                if len(results) >= limit:
                    break
        return results[:limit]

    def _prefix_search(self, name_token: str, year: str | None, *, limit: int) -> list[str]:
        """Collect group ids by prefix. A year narrows to ``<Name>.cc/<year>`` (the
        convention for most major ML venues), which returns that year's conference +
        workshops directly; a bare-name prefix is the broad fallback."""
        variants = list(dict.fromkeys([name_token, name_token.upper(), name_token.title()]))
        prefixes: list[str] = []
        for variant in variants:
            if year:
                prefixes.append(f"{variant}.cc/{year}")
        prefixes.extend(variants)  # broad fallbacks last
        prefixes = list(dict.fromkeys(prefixes))

        ids: list[str] = []
        seen: set[str] = set()
        for prefix in prefixes:
            try:
                groups = self.client.get_groups(prefix=prefix, limit=limit)
            except Exception:
                continue
            for group in groups:
                gid = getattr(group, "id", None) or (group if isinstance(group, str) else None)
                if gid and gid not in seen:
                    seen.add(gid)
                    ids.append(gid)
            if len(ids) >= limit:
                break
        return ids

    # --- internals -----------------------------------------------------------
    def _map_handle(self, handle: str) -> tuple[str, str]:
        """Map a handle to ``(venue_id, slug)`` via alias map or raw-id passthrough."""
        alias = BUILTIN_VENUE_ALIASES.get(handle.lower())
        if alias is not None:
            return alias, handle.lower()
        if "/" in handle:
            return handle, slugify_venue_id(handle)
        raise UsageError(
            f"Unknown venue '{handle}'.",
            hint="Use `confos venues search` to find it, pass an OpenReview id "
            "(e.g. NeurIPS.cc/2025/Conference), or register it with `confos venues add`.",
        )


def _note_to_raw(note: Any) -> RawNote:
    """Snapshot a note as a plain dict (the truth, D3), capturing tcdate/tmdate."""
    raw: RawNote = note.to_json()
    raw["number"] = getattr(note, "number", None)
    raw["tcdate"] = getattr(note, "tcdate", None)
    raw["tmdate"] = getattr(note, "tmdate", None)
    details = getattr(note, "details", None)
    if details:
        raw["details"] = details
    return raw


def _derive_status(raw_venueid: str | None, ref: VenueRef) -> PaperStatus:
    """Derive status locally from the note's raw venueid (D4)."""
    if raw_venueid is None:
        return "unknown"
    if raw_venueid == ref.published_venueid:
        return "accepted"
    if ref.submission_venueid and raw_venueid == ref.submission_venueid:
        return "under_review"
    if ref.withdrawn_venueid and raw_venueid == ref.withdrawn_venueid:
        return "withdrawn"
    if ref.desk_rejected_venueid and raw_venueid == ref.desk_rejected_venueid:
        return "desk_rejected"
    return "unknown"


def _derive_acceptance_type(venue_string: str | None, details: Any) -> str | None:
    """oral/spotlight/poster from the venue string, falling back to Decision replies."""
    text = (venue_string or "").lower()
    for kind in _ACCEPTANCE_TYPES:
        if kind in text:
            return kind
    if isinstance(details, dict):
        for reply in details.get("replies", []):
            invitations = reply.get("invitations") or []
            if any(str(inv).endswith("Decision") for inv in invitations):
                decision = (_unwrap(reply.get("content") or {}, "decision") or "").lower()
                for kind in _ACCEPTANCE_TYPES:
                    if kind in decision:
                        return kind
    return None


def _normalize_authors(content: dict[str, Any], paper_id: str) -> list[NormalizedAuthor]:
    names = _unwrap(content, "authors") or []
    ids = _unwrap(content, "authorids") or []
    authors: list[NormalizedAuthor] = []
    for position, name in enumerate(names):
        if not isinstance(name, str):
            continue
        raw_id = ids[position] if position < len(ids) and isinstance(ids[position], str) else None
        authors.append(_normalize_author(name, raw_id, paper_id, position))
    return authors


def _normalize_author(
    name: str, raw_id: str | None, paper_id: str, position: int
) -> NormalizedAuthor:
    if raw_id and raw_id.startswith("~"):
        return NormalizedAuthor(
            author_id=raw_id,
            profile_id=raw_id,
            display_name=name,
            position=position,
            raw_name=name,
            data_quality="resolved",
            profile_url=f"https://openreview.net/profile?id={raw_id}",
        )
    if raw_id and "@" in raw_id:
        email = raw_id.strip().lower()
        org = org_from_email(email)
        affiliation, country = (org[0], org[1]) if org else (None, None)
        return NormalizedAuthor(
            author_id=f"email:{email}",
            profile_id=None,
            display_name=name,
            position=position,
            raw_name=name,
            affiliation=affiliation,
            country=country,
            data_quality="low",
        )
    # No usable id → unresolved, scoped to this paper so it never merges across papers (D5).
    return NormalizedAuthor(
        author_id=f"name:{_slug_name(name)}#{paper_id}-{position}",
        profile_id=None,
        display_name=name,
        position=position,
        raw_name=name,
        data_quality="unresolved",
    )
