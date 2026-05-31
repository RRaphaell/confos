"""Phase-2 CLI contract: search/show/related, authors, orgs, index — envelopes + exits.

Ranking logic is covered in test_search_service; here we lock the JSON contract, exit
codes, and plain output for the commands an agent drives.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from confos.models import IngestOptions
from confos.paths import Paths
from confos.services.ingest import ingest_venue
from tests.conftest import RunCli
from tests.synthetic import FAKE_REF, FakeAdapter, make_note


@pytest.fixture
def ingested(confos_home: Path) -> Path:
    pub = FAKE_REF.published_venueid or ""
    notes = [
        make_note("aaa1", title="Agent memory", keywords=["agents", "memory"], venueid=pub),
        make_note(
            "bbb2",
            title="Tool use for language models",
            keywords=["tool use"],
            authors=["Bob Tan"],
            authorids=["bob@mit.edu"],
            venueid=pub,
        ),
    ]
    ingest_venue(
        paths=Paths(home=confos_home),
        adapter=FakeAdapter(FAKE_REF, notes),
        handle="test-venue",
        opts=IngestOptions(),
    )
    return confos_home


def test_papers_search_json_contract(run_cli: RunCli, ingested: Path) -> None:
    result = run_cli("papers", "search", "agents", "--json")
    assert result.exit_code == 0
    payload = result.json()
    assert payload["ok"] is True
    assert payload["command"] == "papers.search"
    paper = payload["data"][0]
    for field in ("paper_id", "title", "authors", "keywords", "status", "venue", "url", "bm25"):
        assert field in paper
    assert paper["url"].startswith("https://openreview.net/forum?id=")


def test_papers_show_includes_abstract_and_authors(run_cli: RunCli, ingested: Path) -> None:
    result = run_cli("papers", "show", "aaa1", "--json")
    assert result.exit_code == 0
    data = result.json()["data"]
    assert data["title"] == "Agent memory"
    assert "abstract" in data
    assert len(data["authors"]) >= 1


def test_papers_show_not_found(run_cli: RunCli, ingested: Path) -> None:
    result = run_cli("papers", "show", "nope", "--json")
    assert result.exit_code == 1
    assert result.json()["error"]["type"] == "not_found"


def test_papers_related_json(run_cli: RunCli, ingested: Path) -> None:
    result = run_cli("papers", "related", "aaa1", "--json")
    assert result.exit_code == 0
    assert "aaa1" not in [p["paper_id"] for p in result.json()["data"]]


def test_authors_show_and_papers(run_cli: RunCli, ingested: Path) -> None:
    show = run_cli("authors", "show", "email:bob@mit.edu", "--json")
    assert show.exit_code == 0
    assert show.json()["data"]["affiliation_current"] == "MIT"

    papers = run_cli("authors", "papers", "email:bob@mit.edu", "--json")
    assert [p["paper_id"] for p in papers.json()["data"]["papers"]] == ["bbb2"]


def test_authors_show_not_found(run_cli: RunCli, ingested: Path) -> None:
    result = run_cli("authors", "show", "~Nobody1", "--json")
    assert result.exit_code == 1
    assert result.json()["error"]["type"] == "not_found"


def test_orgs_top_json(run_cli: RunCli, ingested: Path) -> None:
    result = run_cli("orgs", "top", "--json")
    assert result.exit_code == 0
    assert any(o["name"] == "MIT" for o in result.json()["data"])


def test_index_status_and_rebuild(run_cli: RunCli, ingested: Path) -> None:
    status = run_cli("index", "status", "--json")
    assert status.exit_code == 0
    assert status.json()["data"]["counts"]["papers"] == 2

    rebuild = run_cli("index", "rebuild", "--json")
    assert rebuild.exit_code == 0
    assert rebuild.json()["data"]["papers"] == 2


def test_papers_search_plain_is_tab_separated(run_cli: RunCli, ingested: Path) -> None:
    result = run_cli("papers", "search", "agents", "--plain")
    assert result.exit_code == 0
    lines = [ln for ln in result.stdout.splitlines() if ln]
    assert lines
    assert all("\t" in ln for ln in lines)


def test_authors_find_returns_ranked_people(run_cli: RunCli, ingested: Path) -> None:
    result = run_cli("authors", "find", "--topic", "agents", "--json")
    assert result.exit_code == 0
    data = result.json()["data"]
    assert data  # at least one author works on "agents"
    top = data[0]
    for field in (
        "author_id",
        "display_name",
        "matched_paper_count",
        "score",
        "score_components",
        "why_relevant",
        "matched_papers",
    ):
        assert field in top
    assert top["matched_papers"][0]["url"].startswith("https://openreview.net/forum?id=")
