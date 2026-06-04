"""Export: context pack (SCHEMAS §6), markdown, bulk CSV/JSONL — service + CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from confos.adapters.base import RawNote
from confos.models import IngestOptions
from confos.paths import Paths
from confos.services import export as export_service
from confos.services.ingest import ingest_venue
from tests.conftest import RunCli
from tests.synthetic import FAKE_REF, FakeAdapter, make_note

PUB = FAKE_REF.published_venueid or ""


def _corpus_notes() -> list[RawNote]:
    return [
        make_note(
            "p1",
            title="qq one",
            keywords=["qq", "alpha"],
            authors=["Alice", "Bob"],
            authorids=["~A1", "bob@mit.edu"],
            venueid=PUB,
        ),
        make_note(
            "p2",
            title="qq two",
            keywords=["qq", "beta"],
            authors=["Alice"],
            authorids=["~A1"],
            venueid=PUB,
        ),
        make_note(
            "p3",
            title="unrelated",
            keywords=["other"],
            authors=["Carol"],
            authorids=["~C1"],
            venueid=PUB,
        ),
    ]


@pytest.fixture
def corpus(tmp_path: Path) -> Paths:
    paths = Paths(home=tmp_path / "store")
    ingest_venue(
        paths=paths,
        adapter=FakeAdapter(FAKE_REF, _corpus_notes()),
        handle="test-venue",
        opts=IngestOptions(),
    )
    return paths


def test_context_pack_structure(corpus: Paths) -> None:
    pack = export_service.build_context_pack(corpus, "qq", venue="test-venue")
    assert pack["type"] == "confos.context_pack"
    assert pack["topic"] == "qq"
    assert len(pack["papers"]) == 2  # p1, p2 match; p3 doesn't
    assert pack["papers"][0]["url"].startswith("https://openreview.net/forum?id=")
    assert "abstract" in pack["papers"][0]  # self-contained
    # ranked authors with provenance
    assert pack["authors"][0]["author_id"] == "~A1"  # 2 matched papers → top
    assert pack["authors"][0]["matched_papers"]
    # orgs (MIT via bob@mit.edu)
    assert {"name": "MIT", "papers": 1} in pack["orgs"]
    # topic-scoped stats
    assert pack["stats"]["matched"] == 2
    assert pack["stats"]["total"] == 3
    # thin areas: alpha/beta appear once among matched; qq appears on both (not thin)
    assert set(pack["thin_areas"]) >= {"alpha", "beta"}
    assert "qq" not in pack["thin_areas"]
    assert pack["notes"]


def test_context_pack_markdown(corpus: Paths) -> None:
    pack = export_service.build_context_pack(corpus, "qq", venue="test-venue")
    md = export_service.context_pack_markdown(pack)
    assert md.startswith("# Context pack: qq")
    assert "## Papers (2)" in md
    assert "https://openreview.net/forum?id=" in md  # cited
    assert "thin areas" in md.lower()


def test_export_papers_csv_and_jsonl(corpus: Paths) -> None:
    csv_out = export_service.export_papers(corpus, venue="test-venue", fmt="csv")
    lines = csv_out.splitlines()
    assert lines[0] == (
        "paper_id,title,status,acceptance_type,venue,url,"
        "pdf_url,supplementary_url,authors,keywords,bibtex"
    )
    assert len(lines) == 1 + 3  # header + 3 papers

    jsonl_out = export_service.export_papers(corpus, venue="test-venue", fmt="jsonl")
    records = [json.loads(line) for line in jsonl_out.splitlines()]
    assert len(records) == 3
    assert "authors" in records[0] and "url" in records[0]
    # Phase 0: pdf link + bibtex now ride along (server path → absolute).
    assert records[0]["pdf_url"].startswith("https://openreview.net/pdf/")
    assert records[0]["bibtex"].startswith("@inproceedings{")


def test_export_csv_escapes_formula_and_round_trips(tmp_path: Path) -> None:
    import csv as _csv
    import io as _io

    paths = Paths(home=tmp_path / "store")
    note = make_note(
        "x1",
        title='=cmd(), "quoted, comma" title',
        keywords=["a"],
        authors=["Al"],
        authorids=["~Al1"],
        venueid=PUB,
    )
    ingest_venue(
        paths=paths,
        adapter=FakeAdapter(FAKE_REF, [note]),
        handle="test-venue",
        opts=IngestOptions(),
    )
    csv_out = export_service.export_papers(paths, venue="test-venue", fmt="csv")
    records = list(_csv.DictReader(_io.StringIO(csv_out)))
    assert len(records) == 1
    title = records[0]["title"]
    assert title.startswith("'=")  # formula injection neutralised
    assert "quoted, comma" in title  # comma + quotes round-trip via the csv module


def test_csv_safe_neutralises_leading_whitespace_formulas() -> None:
    # Spreadsheets strip leading whitespace/tab/CR before evaluating, so the guard must
    # look past it. The original (untrimmed) value is preserved after the quote.
    for danger in (
        "=cmd()",
        "\t=cmd()",
        " =cmd()",
        "\r\n=cmd()",
        " +1",
        "\t-2",
        "@x",
        "\ufeff=cmd()",  # leading BOM (consumers often strip it, re-exposing the '=')
        "\xa0=cmd()",  # NBSP (Unicode whitespace, not plain ASCII)
    ):
        assert export_service._csv_safe(danger) == "'" + danger
    # Benign values (incl. leading text, numbers) are untouched.
    for ok in ("hello", "a=b", "  spaced text", "2024"):
        assert export_service._csv_safe(ok) == ok
    assert export_service._csv_safe(None) == ""


def test_export_authors_jsonl(corpus: Paths) -> None:
    out = export_service.export_authors(corpus, venue="test-venue", fmt="jsonl")
    records = [json.loads(line) for line in out.splitlines()]
    ids = {r["author_id"] for r in records}
    assert {"~A1", "email:bob@mit.edu", "~C1"} <= ids


# --- CLI ---------------------------------------------------------------------


@pytest.fixture
def export_home(confos_home: Path) -> Path:
    ingest_venue(
        paths=Paths(home=confos_home),
        adapter=FakeAdapter(FAKE_REF, _corpus_notes()),
        handle="test-venue",
        opts=IngestOptions(),
    )
    return confos_home


def test_cli_export_context_json(run_cli: RunCli, export_home: Path) -> None:
    result = run_cli("export", "context", "--topic", "qq", "--json")
    assert result.exit_code == 0
    data = result.json()["data"]
    assert data["type"] == "confos.context_pack"
    assert data["papers"] and data["authors"]


def test_cli_export_context_markdown(run_cli: RunCli, export_home: Path) -> None:
    result = run_cli("export", "context", "--topic", "qq", "--format", "markdown")
    assert result.exit_code == 0
    assert result.stdout.startswith("# Context pack: qq")


def test_cli_export_papers_csv(run_cli: RunCli, export_home: Path) -> None:
    result = run_cli("export", "papers", "--format", "csv")
    assert result.exit_code == 0
    assert result.stdout.splitlines()[0].startswith("paper_id,title")


def test_cli_export_bad_format(run_cli: RunCli, export_home: Path) -> None:
    result = run_cli("export", "papers", "--format", "xml", "--json")
    assert result.exit_code == 2
    assert result.json()["error"]["type"] == "usage"


def test_cli_export_papers_json_emits_envelope(run_cli: RunCli, export_home: Path) -> None:
    # The #1 contract: --json must speak JSON, not silently fall back to CSV.
    result = run_cli("export", "papers", "--json")
    assert result.exit_code == 0
    payload = result.json()
    assert payload["ok"] is True
    assert payload["command"] == "export.papers"
    assert isinstance(payload["data"], list) and len(payload["data"]) == 3
    assert {"paper_id", "title", "authors"} <= payload["data"][0].keys()


def test_cli_export_authors_json_emits_envelope(run_cli: RunCli, export_home: Path) -> None:
    result = run_cli("export", "authors", "--json")
    assert result.exit_code == 0
    payload = result.json()
    assert payload["ok"] is True
    assert payload["command"] == "export.authors"
    assert isinstance(payload["data"], list) and payload["data"]
    assert "author_id" in payload["data"][0]


def test_cli_export_json_conflicts_with_explicit_csv(run_cli: RunCli, export_home: Path) -> None:
    # Asking for --json AND --format csv is contradictory: a loud usage error beats
    # silently honouring one and dropping the other.
    result = run_cli("export", "papers", "--json", "--format", "csv")
    assert result.exit_code == 2
    assert result.json()["error"]["type"] == "usage"
