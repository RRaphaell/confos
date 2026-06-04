"""--venue validation (P1-3) + per-subcommand --limit guard (P1-6).

A typo'd venue must fail loudly rather than masquerade as a real-but-empty venue (ok:true,
zero rows, exit 0) — that silent ambiguity is exactly what corrupts an agent's conclusions.
A known builtin alias that simply isn't ingested yet is *not* a typo, so it passes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from confos.models import IngestOptions
from confos.paths import Paths
from confos.services.ingest import ingest_venue
from tests.conftest import RunCli
from tests.synthetic import FAKE_REF, FakeAdapter, make_note

PUB = FAKE_REF.published_venueid or ""


@pytest.fixture
def home(confos_home: Path) -> Path:
    ingest_venue(
        paths=Paths(home=confos_home),
        adapter=FakeAdapter(
            FAKE_REF, [make_note("p1", title="agents", keywords=["agents"], venueid=PUB)]
        ),
        handle="test-venue",
        opts=IngestOptions(),
    )
    return confos_home


def test_unknown_venue_errors_loudly(run_cli: RunCli, home: Path) -> None:
    result = run_cli("stats", "overview", "--venue", "nope-typo-2099", "--json")
    assert result.exit_code == 1
    err = result.json()["error"]
    assert err["type"] == "not_found"
    assert "nope-typo-2099" in err["message"]


def test_unknown_venue_errors_across_commands(run_cli: RunCli, home: Path) -> None:
    # The guard is shared, so every --venue-accepting read command behaves the same way.
    for args in (
        ("papers", "search", "agents", "--venue", "typo-venue"),
        ("authors", "find", "--topic", "agents", "--venue", "typo-venue"),
        ("brief", "--venue", "typo-venue"),
        ("viz", "topics", "--venue", "typo-venue"),
        ("export", "papers", "--venue", "typo-venue"),
    ):
        result = run_cli(*args, "--json")
        assert result.exit_code == 1, args
        assert result.json()["error"]["type"] == "not_found", args


def test_valid_venue_passes(run_cli: RunCli, home: Path) -> None:
    result = run_cli("stats", "overview", "--venue", "test-venue", "--json")
    assert result.exit_code == 0


def test_known_alias_not_ingested_is_not_an_error(run_cli: RunCli, home: Path) -> None:
    # neurips-2025 is a builtin alias but not ingested here: an empty result is legitimate.
    result = run_cli("papers", "search", "agents", "--venue", "neurips-2025", "--json")
    assert result.exit_code == 0
    assert result.json()["data"] == []


def test_negative_subcommand_limit_rejected(run_cli: RunCli, home: Path) -> None:
    result = run_cli(
        "papers", "search", "agents", "--venue", "test-venue", "--limit", "-1", "--json"
    )
    assert result.exit_code == 2
    assert result.json()["error"]["type"] == "usage"
