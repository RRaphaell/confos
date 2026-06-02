"""Phase 5: `confos brief` — composition over stats/orgs/papers/people, human + agent.

Builds a small reviewed corpus and asserts the brief wires every section together and the
ranking falls back sensibly (top-rated when reviews exist; topic mode adds ranked people +
thin areas). The composition is offline + deterministic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from confos.adapters.base import RawNote
from confos.models import IngestOptions
from confos.paths import Paths
from confos.services import brief as brief_service
from confos.services.ingest import ingest_venue
from tests.conftest import RunCli
from tests.synthetic import FAKE_REF, FakeAdapter, make_note

PUB = FAKE_REF.published_venueid or ""


def _corpus_notes() -> list[RawNote]:
    return [
        make_note("p1", title="agents one", keywords=["agents", "memory"], venueid=PUB,
                  authors=["Alice", "Bob"], authorids=["~A1", "~B1"],
                  reviews=[{"rating": 8}, {"rating": 7}]),
        make_note("p2", title="agents two", keywords=["agents"], venueid=PUB,
                  authors=["Alice"], authorids=["~A1"], reviews=[{"rating": 5}, {"rating": 5}]),
        make_note("p3", title="vision work", keywords=["vision"], venueid=PUB,
                  authors=["Carol"], authorids=["~C1"]),
    ]


def _ingest(home: Path) -> Paths:
    paths = Paths(home=home)
    ingest_venue(
        paths=paths,
        adapter=FakeAdapter(FAKE_REF, _corpus_notes()),
        handle="test-venue",
        opts=IngestOptions(include_decisions=True),
    )
    return paths


def test_brief_venue_landscape(tmp_path: Path) -> None:
    brief = brief_service.build_brief(_ingest(tmp_path / "store"), venue="test-venue")
    assert brief["type"] == "confos.brief"
    assert brief["overview"]["papers"] == 3
    # reviews present → top papers ranked by rating, highest first.
    assert brief["top_papers"]["ranked_by"] == "rating"
    assert brief["top_papers"]["papers"][0]["paper_id"] == "p1"  # mean 7.5
    # hot topics + people (most prolific = Alice, 2 papers).
    assert any(t["key"] == "agents" for t in brief["hot_topics"])
    assert brief["people_to_know"][0]["display_name"] == "Alice"
    assert brief["thin_areas"] == []  # only with a topic


def test_brief_topic_focus(tmp_path: Path) -> None:
    paths = _ingest(tmp_path / "store")
    brief = brief_service.build_brief(paths, venue="test-venue", topic="agents")
    assert brief["topic"] == "agents"
    assert brief["top_papers"]["ranked_by"] == "relevance"
    ids = {p["paper_id"] for p in brief["top_papers"]["papers"]}
    assert ids == {"p1", "p2"}  # the vision paper doesn't match
    # ranked people carry why-relevant (find_authors), not just a bare count.
    assert brief["people_to_know"]
    assert "why_relevant" in brief["people_to_know"][0]


def test_brief_recent_fallback_without_reviews(tmp_path: Path) -> None:
    # No reviews ingested → top papers fall back to "recent" rather than empty.
    paths = Paths(home=tmp_path / "store")
    note = make_note("only", title="solo", keywords=["agents"], venueid=PUB)
    ingest_venue(
        paths=paths, adapter=FakeAdapter(FAKE_REF, [note]), handle="test-venue",
        opts=IngestOptions(),
    )
    brief = brief_service.build_brief(paths, venue="test-venue")
    assert brief["top_papers"]["ranked_by"] == "recent"
    assert brief["top_papers"]["papers"][0]["paper_id"] == "only"


def test_brief_markdown(tmp_path: Path) -> None:
    brief = brief_service.build_brief(_ingest(tmp_path / "store"), venue="test-venue")
    md = brief_service.brief_markdown(brief)
    assert md.startswith("# confos brief: test-venue")
    assert "## Top papers" in md and "## People to know" in md


def test_brief_markdown_with_orgs_renders(tmp_path: Path) -> None:
    # Regression: top_orgs rows are {name, country, papers} (NOT {key,...}); the Markdown
    # render must not KeyError. The synthetic reviewed corpus has no affiliations, so this
    # uses an email author (→ MIT org) to make rising_orgs non-empty.
    paths = Paths(home=tmp_path / "store")
    note = make_note("p1", title="agents", keywords=["agents"], venueid=PUB,
                     authors=["Bob"], authorids=["bob@mit.edu"])
    ingest_venue(
        paths=paths, adapter=FakeAdapter(FAKE_REF, [note]), handle="test-venue",
        opts=IngestOptions(),
    )
    brief = brief_service.build_brief(paths, venue="test-venue")
    assert brief["rising_orgs"] and brief["rising_orgs"][0]["name"] == "MIT"
    md = brief_service.brief_markdown(brief)  # must NOT raise KeyError('key')
    assert "## Organisations" in md and "MIT" in md


# --- CLI ---------------------------------------------------------------------


@pytest.fixture
def brief_home(confos_home: Path) -> Path:
    _ingest(confos_home)
    return confos_home


def test_cli_brief_json(run_cli: RunCli, brief_home: Path) -> None:
    result = run_cli("brief", "--venue", "test-venue", "--json")
    assert result.exit_code == 0
    data = result.json()["data"]
    assert data["type"] == "confos.brief"
    assert data["top_papers"]["papers"][0]["paper_id"] == "p1"


def test_cli_brief_human_markdown(run_cli: RunCli, brief_home: Path) -> None:
    result = run_cli("brief", "--venue", "test-venue")
    assert result.exit_code == 0
    assert result.stdout.startswith("# confos brief: test-venue")
