"""Trends deltas + co-authorship graph, over synthetic corpora (offline)."""

from __future__ import annotations

from pathlib import Path

import pytest

from confos.models import IngestOptions
from confos.paths import Paths
from confos.services import trends as trends_service
from confos.services import viz as viz_service
from confos.services.ingest import ingest_venue
from tests.conftest import RunCli
from tests.synthetic import FAKE_REF, FakeAdapter, make_note

V1 = FAKE_REF.model_copy(
    update={
        "slug": "v1",
        "source_venue_id": "Test.cc/2024/Conference",
        "published_venueid": "Test.cc/2024/Conference",
        "year": 2024,
    }
)
V2 = FAKE_REF.model_copy(
    update={
        "slug": "v2",
        "source_venue_id": "Test.cc/2025/Conference",
        "published_venueid": "Test.cc/2025/Conference",
        "year": 2025,
    }
)


@pytest.fixture
def two_venues(tmp_path: Path) -> Paths:
    paths = Paths(home=tmp_path / "store")
    # v1 (2024): 3 papers, 1 matches "qq"
    v1_notes = [
        make_note(
            "a1",
            keywords=["qq"],
            authors=["A"],
            authorids=["~A1"],
            venueid=V1.published_venueid or "",
        ),
        make_note(
            "a2",
            keywords=["other"],
            authors=["B"],
            authorids=["~B1"],
            venueid=V1.published_venueid or "",
        ),
        make_note(
            "a3",
            keywords=["other"],
            authors=["C"],
            authorids=["~C1"],
            venueid=V1.published_venueid or "",
        ),
    ]
    # v2 (2025): 4 papers, 2 match "qq"
    v2_notes = [
        make_note(
            "b1",
            keywords=["qq"],
            authors=["A", "B"],
            authorids=["~A1", "~B1"],
            venueid=V2.published_venueid or "",
        ),
        make_note(
            "b2",
            keywords=["qq"],
            authors=["A", "C"],
            authorids=["~A1", "~C1"],
            venueid=V2.published_venueid or "",
        ),
        make_note(
            "b3",
            keywords=["x"],
            authors=["D"],
            authorids=["~D1"],
            venueid=V2.published_venueid or "",
        ),
        make_note(
            "b4",
            keywords=["y"],
            authors=["E"],
            authorids=["~E1"],
            venueid=V2.published_venueid or "",
        ),
    ]
    ingest_venue(paths=paths, adapter=FakeAdapter(V1, v1_notes), handle="v1", opts=IngestOptions())
    ingest_venue(paths=paths, adapter=FakeAdapter(V2, v2_notes), handle="v2", opts=IngestOptions())
    return paths


def test_trends_topic_series_and_delta(two_venues: Paths) -> None:
    result = trends_service.trends_topic(two_venues, "qq", ["v1", "v2"])
    series = result["series"]
    assert [s["venue"] for s in series] == ["v1", "v2"]
    assert [s["matched"] for s in series] == [1, 2]
    assert [s["total"] for s in series] == [3, 4]
    assert series[0]["year"] == 2024 and series[1]["year"] == 2025
    assert series[1]["share"] == 0.5
    delta = result["delta"]
    assert delta["matched_abs"] == 1
    assert abs(delta["share_pp"] - 16.67) < 0.01  # (0.5 - 0.3333) * 100


def test_trends_compare_is_two_venue_trend(two_venues: Paths) -> None:
    result = trends_service.trends_compare(two_venues, "v1", "v2", "qq")
    assert [s["venue"] for s in result["series"]] == ["v1", "v2"]
    assert result["delta"]["matched_abs"] == 1


def test_trends_warns_on_not_ingested_venue(two_venues: Paths) -> None:
    # A venue that isn't local should report zeros AND a warning (not a phantom decline).
    result = trends_service.trends_topic(two_venues, "qq", ["v1", "nope-2099"])
    series = {s["venue"]: s for s in result["series"]}
    assert series["nope-2099"]["matched"] == 0
    assert series["nope-2099"]["total"] == 0
    assert any("nope-2099" in w for w in result["warnings"])


def test_coauthor_graph_edges(two_venues: Paths) -> None:
    # In v2, "qq" papers are A+B (b1) and A+C (b2) → edges A-B, A-C; A has degree 2.
    graph = viz_service.build_coauthor_graph(two_venues, "qq", venue="v2")
    assert graph["node_count"] == 3
    assert graph["edge_count"] == 2
    top = graph["nodes"][0]
    assert top["id"] == "~A1" and top["degree"] == 2
    assert sorted(graph["edges"]) == [["~A1", "~B1"], ["~A1", "~C1"]]


# --- CLI contract ------------------------------------------------------------


@pytest.fixture
def viz_home(confos_home: Path) -> Path:
    """Ingest a small co-authored corpus into the run_cli home."""
    pub = FAKE_REF.published_venueid or ""
    notes = [
        make_note("m1", keywords=["qq"], authors=["A", "B"], authorids=["~A1", "~B1"], venueid=pub),
        make_note("m2", keywords=["qq"], authors=["A", "C"], authorids=["~A1", "~C1"], venueid=pub),
    ]
    ingest_venue(
        paths=Paths(home=confos_home),
        adapter=FakeAdapter(FAKE_REF, notes),
        handle="test-venue",
        opts=IngestOptions(),
    )
    return confos_home


def test_trends_topic_json(run_cli: RunCli, viz_home: Path) -> None:
    result = run_cli("trends", "topic", "qq", "--venues", "test-venue", "--json")
    assert result.exit_code == 0
    data = result.json()["data"]
    assert data["topic"] == "qq"
    assert data["series"][0]["matched"] == 2
    assert "delta" in data


def test_viz_topics_json(run_cli: RunCli, viz_home: Path) -> None:
    result = run_cli("viz", "topics", "--json")
    assert result.exit_code == 0
    assert "rows" in result.json()["data"]


def test_viz_network_mermaid_is_plain_text(run_cli: RunCli, viz_home: Path) -> None:
    result = run_cli("viz", "network", "--topic", "qq", "--format", "mermaid")
    assert result.exit_code == 0
    assert result.stdout.startswith("graph LR")
    assert "---" in result.stdout  # has at least one edge


def test_viz_network_html_is_valid_doc(run_cli: RunCli, viz_home: Path) -> None:
    result = run_cli("viz", "network", "--topic", "qq", "--format", "html")
    assert result.exit_code == 0
    assert result.stdout.startswith("<!doctype html>")
    assert 'class="mermaid"' in result.stdout


def test_viz_network_bad_format_is_usage_error(run_cli: RunCli, viz_home: Path) -> None:
    result = run_cli("viz", "network", "--topic", "qq", "--format", "svg", "--json")
    assert result.exit_code == 2
    assert result.json()["error"]["type"] == "usage"


def test_viz_network_plain_is_tsv(run_cli: RunCli, viz_home: Path) -> None:
    # P1-7: --plain must be line/TSV, not a Rich box table.
    result = run_cli("viz", "network", "--topic", "qq", "--plain")
    assert result.exit_code == 0
    assert "\t" in result.stdout
    assert "┏" not in result.stdout and "│" not in result.stdout


def test_viz_topics_limit_is_accepted(run_cli: RunCli, viz_home: Path) -> None:
    # P1-9: the documented `--limit` example must be a real option (was exit 2 "No such option").
    result = run_cli("viz", "topics", "--venue", "test-venue", "--limit", "1", "--json")
    assert result.exit_code == 0
    assert len(result.json()["data"]["rows"]) <= 1
