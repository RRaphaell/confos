"""Phase 1b: the enrich service — fetch (faked) → snapshot profiles.jsonl → rebuild.

The network leg is faked here (a canned fetcher) so the service logic — resume, the
not_found record, --limit, and the trailing rebuild that applies enrichment — is tested
deterministically and offline. The real adapter fetch is covered by the cassette test.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path

from confos.adapters.base import RawProfile
from confos.models import IngestOptions
from confos.paths import Paths
from confos.services import authors as authors_service
from confos.services import enrich as enrich_service
from confos.services import stats as stats_service
from confos.services.ingest import ingest_venue
from tests.synthetic import FAKE_REF, FakeAdapter, make_note, make_profile


class _FakeFetcher:
    """Returns a canned profile per handle; ``errors`` handles fail transiently (retryable)."""

    def __init__(
        self, profiles: dict[str, dict[str, object]], *, errors: set[str] | None = None
    ) -> None:
        self._profiles = profiles
        self._errors = errors or set()
        self.calls: list[str] = []

    def fetch_profiles(
        self, handles: Iterable[str]
    ) -> Iterator[tuple[str, RawProfile | None, str]]:
        for handle in handles:
            self.calls.append(handle)
            if handle in self._errors:
                yield handle, None, "error"
            elif handle in self._profiles:
                yield handle, self._profiles[handle], "found"
            else:
                yield handle, None, "not_found"


def _ingest(home: Path, authorids: list[str]) -> Paths:
    paths = Paths(home=home)
    note = make_note("p1", authors=[h.strip("~") for h in authorids], authorids=authorids)
    ingest_venue(
        paths=paths,
        adapter=FakeAdapter(FAKE_REF, [note]),
        handle="test-venue",
        opts=IngestOptions(),
    )
    return paths


def test_enrich_snapshots_and_applies(tmp_path: Path) -> None:
    paths = _ingest(tmp_path / "store", ["~Alice1", "~Bob1"])
    fetcher = _FakeFetcher(
        {"~Alice1": make_profile("~Alice1", name="EleutherAI", domain="eleuther.ai", country="US")}
    )  # ~Bob1 has no profile → recorded as not_found

    result = enrich_service.enrich_profiles(paths, "test-venue", fetcher=fetcher)

    assert result["handles_total"] == 2
    assert result["fetched"] == 1
    assert result["not_found"] == 1

    # Snapshot written (one found + one not_found marker).
    snapshot = paths.raw_venue_dir("openreview", "test-venue") / "profiles.jsonl"
    records = [json.loads(line) for line in snapshot.read_text().splitlines()]
    assert {r["id"] for r in records} == {"~Alice1", "~Bob1"}
    assert any(r.get("not_found") for r in records if r["id"] == "~Bob1")

    # Enrichment is applied (rebuild ran): Alice resolved, orgs coverage now non-zero.
    assert authors_service.show_author(paths, "~Alice1")["affiliation_current"] == "EleutherAI"
    assert stats_service.orgs(paths, "test-venue")["data_quality"]["papers_with_signal"] == 1


def test_enrich_resumes_and_skips_already_fetched(tmp_path: Path) -> None:
    paths = _ingest(tmp_path / "store", ["~Alice1", "~Bob1"])
    profiles = {
        "~Alice1": make_profile("~Alice1", name="EleutherAI", domain="eleuther.ai"),
        "~Bob1": make_profile("~Bob1", name="MIT", domain="mit.edu"),
    }
    fetcher = _FakeFetcher(profiles)

    enrich_service.enrich_profiles(paths, "test-venue", fetcher=fetcher)
    assert sorted(fetcher.calls) == ["~Alice1", "~Bob1"]

    # Second run with a fresh fetcher: everything is already recorded → nothing refetched.
    fetcher2 = _FakeFetcher(profiles)
    result = enrich_service.enrich_profiles(paths, "test-venue", fetcher=fetcher2)
    assert result["attempted"] == 0
    assert fetcher2.calls == []
    assert result["already_enriched"] == 2


def test_enrich_transient_error_is_retried_on_resume(tmp_path: Path) -> None:
    paths = _ingest(tmp_path / "store", ["~Alice1", "~Bob1"])
    profiles = {h: make_profile(h, name="MIT", domain="mit.edu") for h in ("~Alice1", "~Bob1")}

    # First run: ~Bob1 errors transiently → it must NOT be recorded.
    first = enrich_service.enrich_profiles(
        paths, "test-venue", fetcher=_FakeFetcher(profiles, errors={"~Bob1"})
    )
    assert first["fetched"] == 1 and first["errors"] == 1
    snapshot = paths.raw_venue_dir("openreview", "test-venue") / "profiles.jsonl"
    recorded = {json.loads(line)["id"] for line in snapshot.read_text().splitlines()}
    assert recorded == {"~Alice1"}  # the errored handle is absent → retryable

    # Resume (no error this time): ~Bob1 is retried and now lands.
    second_fetcher = _FakeFetcher(profiles)
    second = enrich_service.enrich_profiles(paths, "test-venue", fetcher=second_fetcher)
    assert second_fetcher.calls == ["~Bob1"]
    assert second["fetched"] == 1
    assert authors_service.show_author(paths, "~Bob1")["affiliation_current"] == "MIT"


def test_enrich_limit_is_resumable(tmp_path: Path) -> None:
    paths = _ingest(tmp_path / "store", ["~Alice1", "~Bob1"])
    profiles = {
        "~Alice1": make_profile("~Alice1", name="EleutherAI", domain="eleuther.ai"),
        "~Bob1": make_profile("~Bob1", name="MIT", domain="mit.edu"),
    }
    first = enrich_service.enrich_profiles(
        paths, "test-venue", fetcher=_FakeFetcher(profiles), limit=1
    )
    assert first["attempted"] == 1 and first["capped"] is True

    second = enrich_service.enrich_profiles(paths, "test-venue", fetcher=_FakeFetcher(profiles))
    assert second["already_enriched"] == 1
    assert second["attempted"] == 1  # the remaining handle
