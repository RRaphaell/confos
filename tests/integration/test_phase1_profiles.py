"""Phase 1: author profile enrichment reproduces offline from a profiles.jsonl snapshot.

The network fetch is exercised elsewhere (cassette). Here we prove the *rebuild* half: drop
a profiles.jsonl next to the raw submissions and `index rebuild` fills in orgs, countries,
affiliation confidence, and the per-author links — with no network (D3).
"""

from __future__ import annotations

import json
from pathlib import Path

from confos.models import IngestOptions
from confos.paths import Paths
from confos.services import authors as authors_service
from confos.services import index as index_service
from confos.services import orgs as orgs_service
from confos.services import stats as stats_service
from confos.services.ingest import ingest_venue
from tests.synthetic import FAKE_REF, FakeAdapter, make_note, make_profile


def _ingest_two_authors(home: Path) -> Paths:
    paths = Paths(home=home)
    note = make_note("p1", authors=["Alice Smith", "Bob Tan"], authorids=["~Alice1", "~Bob1"])
    ingest_venue(
        paths=paths,
        adapter=FakeAdapter(FAKE_REF, [note]),
        handle="test-venue",
        opts=IngestOptions(),
    )
    return paths


def _write_profiles(paths: Paths, profiles: list[dict[str, object]]) -> None:
    venue_dir = paths.raw_venue_dir("openreview", "test-venue")
    (venue_dir / "profiles.jsonl").write_text(
        "\n".join(json.dumps(p) for p in profiles), encoding="utf-8"
    )


def test_orgs_empty_before_enrichment(tmp_path: Path) -> None:
    paths = _ingest_two_authors(tmp_path / "store")
    dq = stats_service.orgs(paths, "test-venue")["data_quality"]
    assert dq["papers_with_signal"] == 0  # tilde authors, no profiles → the v0.1.0 gap


def test_rebuild_enriches_from_profiles_jsonl(tmp_path: Path) -> None:
    paths = _ingest_two_authors(tmp_path / "store")
    _write_profiles(
        paths,
        [
            make_profile(
                "~Alice1",
                name="EleutherAI",
                domain="eleuther.ai",
                country="US",
                homepage="https://alice.example",
                gscholar="https://scholar.google.com/citations?user=z",
                dblp="https://dblp.org/pid/9/9",
                expertise=["interpretability", "language models"],
            ),
            make_profile("~Bob1", name="MIT", domain="mit.edu", country="US"),
        ],
    )

    result = index_service.rebuild(paths)
    assert result["papers"] == 1

    # The four previously-empty surfaces now have real data.
    org_dq = stats_service.orgs(paths, "test-venue")["data_quality"]
    assert org_dq["papers_with_signal"] == 1
    assert org_dq["unknown"] == 0
    assert org_dq["low_confidence"] == 0  # profile-derived affiliations are high-confidence
    org_names = {r["key"] for r in stats_service.orgs(paths, "test-venue")["rows"]}
    assert {"EleutherAI", "MIT"} <= org_names
    assert stats_service.countries(paths, "test-venue")["data_quality"]["papers_with_signal"] == 1

    top = orgs_service.top_orgs(paths, venue="test-venue")["rows"]
    assert any(o["name"] == "EleutherAI" for o in top)

    alice = authors_service.show_author(paths, "~Alice1")
    assert alice["affiliation_current"] == "EleutherAI"
    assert alice["affiliation_country"] == "United States"
    assert alice["homepage"] == "https://alice.example"
    assert alice["gscholar"].endswith("user=z")
    assert alice["dblp"] == "https://dblp.org/pid/9/9"
    assert alice["expertise"] == ["interpretability", "language models"]


def test_rebuild_without_profiles_is_a_noop_for_enrichment(tmp_path: Path) -> None:
    # No profiles.jsonl → rebuild still succeeds and authors stay un-enriched (offline-safe).
    paths = _ingest_two_authors(tmp_path / "store")
    index_service.rebuild(paths)
    alice = authors_service.show_author(paths, "~Alice1")
    assert alice["affiliation_current"] == "Unknown"
    assert alice["homepage"] is None
    assert alice["expertise"] == []
