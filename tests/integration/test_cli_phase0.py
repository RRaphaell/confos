"""Phase 0 CLI surface: --version/--help, init, doctor, error paths + exit codes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from confos import __version__
from tests.conftest import RunCli


def test_version(run_cli: RunCli) -> None:
    result = run_cli("--version")
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_help_lists_command_tree(run_cli: RunCli) -> None:
    result = run_cli("--help")
    assert result.exit_code == 0
    for group in ("papers", "authors", "venues", "stats", "trends", "viz", "export"):
        assert group in result.stdout


def test_init_creates_store(run_cli: RunCli, confos_home: Path) -> None:
    result = run_cli("init")
    assert result.exit_code == 0
    assert (confos_home / "confos.db").exists()
    assert (confos_home / "raw").is_dir()
    assert (confos_home / "aliases").is_dir()


def test_init_json_reports_created(run_cli: RunCli) -> None:
    result = run_cli("init", "--json")
    assert result.exit_code == 0
    payload = result.json()
    assert payload["ok"] is True
    assert payload["command"] == "init"
    assert payload["data"]["created"] is True
    assert payload["data"]["schema_version"] == 1


def test_init_is_idempotent(run_cli: RunCli) -> None:
    first = run_cli("init", "--json")
    assert first.json()["data"]["created"] is True
    second = run_cli("init", "--json")
    assert second.exit_code == 0
    assert second.json()["data"]["created"] is False


def test_doctor_human(run_cli: RunCli, initialized_home: Path) -> None:
    result = run_cli("doctor")
    assert result.exit_code == 0
    assert "fts5" in result.stdout
    assert "python" in result.stdout


def test_doctor_json_reports_checks(run_cli: RunCli, initialized_home: Path) -> None:
    result = run_cli("doctor", "--json")
    assert result.exit_code == 0
    data = result.json()["data"]
    assert data["ok"] is True
    names = {c["name"] for c in data["checks"]}
    assert {"python", "sqlite", "fts5", "store", "database"}.issubset(names)
    fts = next(c for c in data["checks"] if c["name"] == "fts5")
    assert fts["status"] == "ok"


def test_doctor_before_init_warns_but_succeeds(run_cli: RunCli) -> None:
    # No init: store + database are warnings, not hard failures → exit 0.
    result = run_cli("doctor", "--json")
    assert result.exit_code == 0
    data = result.json()["data"]
    statuses = {c["name"]: c["status"] for c in data["checks"]}
    assert statuses["store"] == "warn"
    assert statuses["database"] == "warn"


def test_global_flag_before_and_after_command(run_cli: RunCli, initialized_home: Path) -> None:
    after = run_cli("doctor", "--json")
    before = run_cli("--json", "doctor")
    assert after.exit_code == before.exit_code == 0
    assert after.json()["command"] == before.json()["command"] == "doctor"


def test_json_plain_mutually_exclusive(run_cli: RunCli) -> None:
    result = run_cli("doctor", "--json", "--plain")
    assert result.exit_code == 2


def test_erroring_command_returns_json_error_envelope(run_cli: RunCli) -> None:
    # A command that raises a typed error emits the JSON error envelope (ok:false).
    result = run_cli("papers", "show", "no-such-id", "--json")
    assert result.exit_code == 1
    payload = result.json()
    assert payload["ok"] is False
    assert payload["command"] == "papers.show"
    assert payload["error"]["type"] == "not_found"


def test_missing_required_arg_is_usage_error(run_cli: RunCli) -> None:
    result = run_cli("papers", "search")
    assert result.exit_code == 2


def test_unknown_command_is_usage_error(run_cli: RunCli) -> None:
    result = run_cli("bogus-command")
    assert result.exit_code == 2


def test_bad_limit_is_usage_error(run_cli: RunCli) -> None:
    result = run_cli("--limit", "-5", "doctor")
    assert result.exit_code == 2


# --- regression tests for Phase-0 validation findings ------------------------


def test_init_plain_is_tab_separated_one_line_per_record(run_cli: RunCli) -> None:
    # --plain must emit real TABs, one record per line — no rich wrapping (even for a
    # long home path). Regression for the rich-Console.print wrapping/tab-stripping bug.
    result = run_cli("init", "--plain")
    assert result.exit_code == 0
    lines = [ln for ln in result.stdout.splitlines() if ln]
    assert len(lines) == 4  # home, db, schema_version, created
    for line in lines:
        assert "\t" in line


def test_doctor_plain_one_record_per_line(run_cli: RunCli, initialized_home: Path) -> None:
    result = run_cli("doctor", "--plain")
    assert result.exit_code == 0
    lines = [ln for ln in result.stdout.splitlines() if ln]
    assert len(lines) == 6  # python, sqlite, fts5, openreview-py, store, database
    for line in lines:
        assert line.count("\t") == 2  # name, status, detail


def test_doctor_reports_openreview_backend(run_cli: RunCli) -> None:
    # openreview-py is a declared dependency, so doctor must report it (and find it ok in
    # any real install). Documents that the contract check actually exists.
    result = run_cli("doctor", "--json")
    assert result.exit_code == 0
    checks = {c["name"]: c["status"] for c in result.json()["data"]["checks"]}
    assert checks.get("openreview-py") == "ok"


def test_doctor_unhealthy_json_is_honest(run_cli: RunCli, monkeypatch: pytest.MonkeyPatch) -> None:
    # When a hard check fails, top-level ok must agree with exit code 3.
    monkeypatch.setattr("confos.commands.doctor.fts5_available", lambda: False)
    result = run_cli("doctor", "--json")
    assert result.exit_code == 3
    payload = result.json()
    assert payload["ok"] is False
    assert payload["data"]["ok"] is False
    fts = next(c for c in payload["data"]["checks"] if c["name"] == "fts5")
    assert fts["status"] == "fail"


def test_bare_group_under_json_keeps_stdout_pure_json(run_cli: RunCli) -> None:
    # `confos --json papers` (no subcommand) must NOT leak a help banner to stdout.
    result = run_cli("--json", "papers")
    assert result.exit_code == 2
    payload = json.loads(result.stdout)  # must be parseable
    assert payload["ok"] is False
    assert payload["error"]["type"] == "usage"


def test_click_parse_error_under_json_is_envelope(run_cli: RunCli) -> None:
    # Unknown option under --json must produce a JSON usage envelope, not plain text.
    result = run_cli("--json", "papers", "search", "x", "--bogus-flag")
    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == 2
    assert payload["error"]["type"] == "usage"


def test_parse_error_with_json_AFTER_subcommand_is_envelope(run_cli: RunCli) -> None:
    # The documented agent form puts --json after the subcommand. On a parse error the
    # command body never runs (so the flag isn't merged into the context yet) — stdout
    # must STILL be a pure JSON usage envelope, not click's plain Usage/Error text.
    for args in (
        ("papers", "search", "--json"),  # missing required QUERY
        ("papers", "search", "x", "--bogus-flag", "--json"),  # unknown option
    ):
        result = run_cli(*args)
        assert result.exit_code == 2, args
        payload = json.loads(result.stdout)  # must parse — no leak
        assert payload["ok"] is False
        assert payload["error"]["type"] == "usage"


def test_error_envelope_with_json_before_subcommand(run_cli: RunCli) -> None:
    result = run_cli("--json", "papers", "show", "no-such-id")
    assert result.exit_code == 1
    payload = result.json()
    assert payload["ok"] is False
    assert payload["command"] == "papers.show"
    assert payload["error"]["type"] == "not_found"


def test_single_verbose_in_both_positions_is_not_vv(run_cli: RunCli) -> None:
    # -v before AND after a command must stay verbosity 1 (no leaked traceback at -vv) —
    # if it summed to 2, a typed error would dump a stack trace.
    result = run_cli("-v", "papers", "show", "no-such-id", "-v")
    assert result.exit_code == 1
    assert "Traceback" not in result.stderr


def test_completion_flags_absent(run_cli: RunCli) -> None:
    result = run_cli("--help")
    assert "--install-completion" not in result.stdout
    assert "--show-completion" not in result.stdout
