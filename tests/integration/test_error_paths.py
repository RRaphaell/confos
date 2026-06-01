"""Exit-code contract (CLI_CONTRACT §5) end-to-end through ``main()``.

Each typed failure must map to its stable exit code AND, under ``--json``, to an error
envelope with the right ``error.type`` — that pairing is what agents/scripts branch on.
Codes 0/1(not_found)/2(usage)/3(config) are exercised elsewhere (phase-0 + service
tests); this module pins the ones that were otherwise only unit-level: 4 (network),
5 (partial ingest), 130 (interrupt), and the catch-all "unexpected error" wrap (1),
including the promise that a raw traceback is shown only at ``-vv``.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from confos.adapters.base import RawNote
from confos.errors import NetworkError
from confos.models import IngestOptions, VenueRef
from tests.conftest import RunCli
from tests.synthetic import FAKE_REF, FakeAdapter, make_note


class _NetworkDownAdapter(FakeAdapter):
    """Resolves a venue, then the upstream is unreachable when fetching notes."""

    def __init__(self) -> None:
        super().__init__(FAKE_REF, [])

    def fetch_notes(
        self, ref: VenueRef, opts: IngestOptions, **kwargs: object
    ) -> Iterator[RawNote]:
        raise NetworkError("OpenReview is unreachable.", hint="Check your connection and retry.")


def test_network_failure_exits_4(run_cli: RunCli, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "confos.commands.ingest.OpenReviewAdapter", lambda **_: _NetworkDownAdapter()
    )
    result = run_cli("ingest", "neurips-2025", "--json")
    assert result.exit_code == 4
    payload = result.json()
    assert payload["ok"] is False
    assert payload["error"]["type"] == "network"


def test_partial_ingest_exits_5(run_cli: RunCli, monkeypatch: pytest.MonkeyPatch) -> None:
    notes = [make_note("p1"), make_note("BAD-NOTE"), make_note("p2", tcdate=50)]
    monkeypatch.setattr(
        "confos.commands.ingest.OpenReviewAdapter", lambda **_: FakeAdapter(FAKE_REF, notes)
    )
    result = run_cli("ingest", "test-venue", "--json")
    assert result.exit_code == 5
    payload = result.json()
    # Partial means usable-but-incomplete: the good rows persisted, with a warning.
    assert payload["ok"] is False  # ok must agree with the non-zero exit code
    assert payload["data"]["status"] == "partial"
    assert payload["data"]["items_added"] == 2
    assert payload["warnings"]


def test_keyboard_interrupt_exits_130(run_cli: RunCli, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_command: str) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("confos.commands.schema.schema_for", boom)
    result = run_cli("schema", "papers.search")
    assert result.exit_code == 130
    assert "interrupted" in result.stderr


def test_unexpected_error_is_wrapped_exit_1_no_traceback(
    run_cli: RunCli, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(_command: str) -> None:
        raise RuntimeError("kaboom")

    monkeypatch.setattr("confos.commands.schema.schema_for", boom)
    result = run_cli("schema", "papers.search")
    assert result.exit_code == 1
    # Clean one-liner, never a raw Python traceback by default.
    assert "unexpected error" in result.stderr
    assert "Traceback (most recent call last)" not in result.stderr


def test_unexpected_error_traceback_only_at_double_verbose(
    run_cli: RunCli, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(_command: str) -> None:
        raise RuntimeError("kaboom")

    monkeypatch.setattr("confos.commands.schema.schema_for", boom)
    result = run_cli("schema", "papers.search", "-vv")
    assert result.exit_code == 1
    assert "Traceback (most recent call last)" in result.stderr
    assert "RuntimeError: kaboom" in result.stderr


def test_unexpected_error_under_json_is_envelope(
    run_cli: RunCli, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(_command: str) -> None:
        raise RuntimeError("kaboom")

    monkeypatch.setattr("confos.commands.schema.schema_for", boom)
    result = run_cli("schema", "papers.search", "--json")
    assert result.exit_code == 1
    payload = result.json()  # stdout stays pure JSON even on an unexpected crash
    assert payload["ok"] is False
    assert payload["error"]["type"] == "error"


def test_malformed_config_exits_3(run_cli: RunCli, confos_home: Path) -> None:
    confos_home.mkdir(parents=True, exist_ok=True)
    (confos_home / "config.toml").write_text("this is = = not valid toml\n")
    result = run_cli("venues", "aliases", "--json")
    assert result.exit_code == 3
    payload = result.json()
    assert payload["ok"] is False
    assert payload["error"]["type"] == "config"
