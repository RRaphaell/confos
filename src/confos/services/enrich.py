"""Author profile enrichment: fetch profiles → snapshot ``profiles.jsonl`` → rebuild.

The fetch is the only network step (anonymous, per-profile, best-effort). Each result is
appended to ``raw/<source>/<venue>/profiles.jsonl`` as it arrives, so an interrupted run
**resumes** (already-seen handles — found *or* recorded ``not_found`` — are skipped). Once
the snapshot exists, ``index rebuild`` reproduces the enrichment with no network (D3), so
this command only needs to run once per venue.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any, Protocol

from ..adapters.base import RawProfile
from ..errors import NotFoundError
from ..paths import Paths
from . import index as index_service

ProgressFn = Callable[[str], None]


def _noop(_: str) -> None:
    pass


# OpenReview rate-limits anonymous /profiles to ~20 requests/minute (per IP, total).
_PROFILES_PER_MINUTE = 20


class ProfileFetcher(Protocol):
    """The slice of an adapter that profile enrichment needs (network).

    Yields ``(handle, snapshot|None, status)`` where status is ``"found"`` (snapshot is the
    profile), ``"not_found"`` (no public profile — safe to record), or ``"error"``
    (transient — must NOT be recorded so a resume retries the handle).
    """

    def fetch_profiles(
        self, handles: Iterable[str]
    ) -> Iterator[tuple[str, RawProfile | None, str]]: ...


def enrich_profiles(
    paths: Paths,
    venue_slug: str,
    *,
    fetcher: ProfileFetcher,
    source: str = "openreview",
    force: bool = False,
    limit: int | None = None,
    on_progress: ProgressFn = _noop,
) -> dict[str, Any]:
    """Fetch + snapshot author profiles for an ingested venue, then rebuild the index.

    ``force`` refetches every handle (rewriting the snapshot); otherwise only handles not
    already in ``profiles.jsonl`` are fetched. ``limit`` caps how many are fetched this run
    (resumable across runs). Returns a summary with honest coverage counts.
    """
    venue_dir = paths.raw_venue_dir(source, venue_slug)
    submissions = venue_dir / "submissions.jsonl"
    if not submissions.exists():
        raise NotFoundError(
            f"Venue '{venue_slug}' is not ingested (no raw snapshot to enrich).",
            hint="Run `confos ingest <venue>` first, then `confos enrich profiles --venue …`.",
        )

    profiles_path = venue_dir / "profiles.jsonl"
    handles = _profile_handles(submissions)
    already = set() if force else _recorded_handles(profiles_path)
    todo = [h for h in handles if h not in already]
    capped = limit is not None and limit < len(todo)
    if capped:
        todo = todo[:limit]

    eta_min = -(-len(todo) // _PROFILES_PER_MINUTE)  # ceil; OpenReview caps ~20 profiles/min
    eta = f" — ~{eta_min} min at OpenReview's ~20/min limit" if eta_min > 1 else ""
    on_progress(
        f"{len(handles)} unique author handle(s); {len(already)} already enriched; "
        f"fetching {len(todo)}" + (f" (capped at {limit})" if capped else "") + eta
    )

    fetched = not_found = errors = 0
    if todo:
        # Truncate on --force (full refetch), else append (resume) so prior results survive.
        # Transient errors are NOT written, so a later resume retries those handles.
        with profiles_path.open("w" if force else "a", encoding="utf-8") as out:
            for handle, profile, status in fetcher.fetch_profiles(todo):
                if status == "found" and profile is not None:
                    out.write(json.dumps(profile, ensure_ascii=False) + "\n")
                    fetched += 1
                elif status == "not_found":
                    out.write(json.dumps({"id": handle, "not_found": True}) + "\n")
                    not_found += 1
                else:  # transient error — leave unrecorded for the next run
                    errors += 1
                done = fetched + not_found + errors
                if done % 500 == 0:
                    out.flush()
                    on_progress(
                        f"… {done}/{len(todo)} "
                        f"({fetched} found, {not_found} none, {errors} errored)"
                    )

    on_progress("Rebuilding index from raw (applying enrichment, no network) …")
    rebuilt = index_service.rebuild(paths)

    return {
        "venue": venue_slug,
        "handles_total": len(handles),
        "already_enriched": len(already),
        "attempted": len(todo),
        "fetched": fetched,
        "not_found": not_found,
        "errors": errors,
        "capped": capped,
        "profiles_path": str(profiles_path),
        "papers_reindexed": rebuilt["papers"],
    }


def _profile_handles(submissions: Path) -> list[str]:
    """Unique tilde author handles across a venue's raw submissions, in first-seen order."""
    seen: dict[str, None] = {}
    for line in submissions.read_text("utf-8").splitlines():
        if not line.strip():
            continue
        try:
            note = json.loads(line)
        except json.JSONDecodeError:
            continue
        content = note.get("content") or {}
        ids = content.get("authorids")
        ids = ids.get("value") if isinstance(ids, dict) else ids
        if isinstance(ids, list):
            for handle in ids:
                if isinstance(handle, str) and handle.startswith("~"):
                    seen.setdefault(handle, None)
    return list(seen)


def _recorded_handles(profiles_path: Path) -> set[str]:
    """Handles already in ``profiles.jsonl`` (found OR recorded ``not_found``) — skip them."""
    if not profiles_path.exists():
        return set()
    out: set[str] = set()
    for line in profiles_path.read_text("utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        handle = record.get("id")
        if isinstance(handle, str):
            out.add(handle)
    return out
