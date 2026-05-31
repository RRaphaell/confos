"""The JSON envelope is the public contract (SCHEMAS §1)."""

from __future__ import annotations

import json

from confos.errors import NetworkError
from confos.output.json import (
    SCHEMA_VERSION,
    dumps,
    error_envelope,
    make_provenance,
    success_envelope,
)


def test_success_envelope_shape() -> None:
    env = success_envelope(
        "papers.search",
        {"q": "agents"},
        [{"paper_id": "x"}],
        provenance=make_provenance("~/.confos/confos.db", venue="neurips-2025", stamp_time=False),
    )
    assert env["ok"] is True
    assert env["schema_version"] == SCHEMA_VERSION
    assert env["command"] == "papers.search"
    assert env["query"] == {"q": "agents"}
    assert env["data"] == [{"paper_id": "x"}]
    assert env["warnings"] == []
    assert env["provenance"]["db"] == "~/.confos/confos.db"
    assert env["provenance"]["sources"] == ["openreview"]
    assert env["provenance"]["venue"] == "neurips-2025"
    # generated_at omitted when stamp_time=False (keeps tests deterministic).
    assert "generated_at" not in env["provenance"]


def test_success_envelope_ok_override() -> None:
    # A command (e.g. doctor) may report an unhealthy result with ok=False but keep
    # the payload in data (not error).
    env = success_envelope(
        "doctor", {}, {"ok": False}, provenance=make_provenance("db", stamp_time=False), ok=False
    )
    assert env["ok"] is False
    assert "data" in env
    assert "error" not in env


def test_make_provenance_explicit_empty_sources() -> None:
    prov = make_provenance("db", sources=[], stamp_time=False)
    assert prov["sources"] == []  # explicit [] is honoured, not coerced to default


def test_error_envelope_shape() -> None:
    err = NetworkError("OpenReview unreachable", hint="retry later")
    env = error_envelope("ingest", err)
    assert env["ok"] is False
    assert env["schema_version"] == SCHEMA_VERSION
    assert env["command"] == "ingest"
    assert env["error"]["code"] == 4
    assert env["error"]["type"] == "network"
    assert env["error"]["message"] == "OpenReview unreachable"
    assert env["error"]["hint"] == "retry later"


def test_dumps_is_valid_json_utf8() -> None:
    env = success_envelope(
        "x", {}, {"name": "Müller café"}, provenance=make_provenance("db", stamp_time=False)
    )
    text = dumps(env)
    assert json.loads(text)["data"]["name"] == "Müller café"
    assert "Müller" in text  # not ascii-escaped
