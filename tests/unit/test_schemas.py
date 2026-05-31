"""The `confos schema` registry: lookups + alignment with real commands."""

from __future__ import annotations

import pytest

from confos.schemas import SCHEMAS, available_commands, schema_for
from tests.conftest import RunCli


def test_schema_for_known_and_unknown() -> None:
    found = schema_for("papers.search")
    assert found is not None
    assert "envelope" in found and "data" in found
    assert schema_for("nope.cmd") is None


def test_available_commands_sorted_and_nonempty() -> None:
    commands = available_commands()
    assert commands == sorted(commands)
    assert "export.context" in commands
    assert "authors.find" in commands


@pytest.mark.parametrize("command", sorted(SCHEMAS))
def test_every_schema_command_is_real(run_cli: RunCli, command: str) -> None:
    # Every documented command must resolve in the CLI (no schema for a phantom command).
    # We invoke its --help, which exits 0 for a real command.
    group, _, sub = command.partition(".")
    args = [group, sub, "--help"] if sub else [group, "--help"]
    result = run_cli(*args)
    assert result.exit_code == 0, f"schema lists {command!r} but `{' '.join(args)}` failed"


def test_schema_cli_envelope(run_cli: RunCli) -> None:
    result = run_cli("schema", "export.context", "--json")
    assert result.exit_code == 0
    payload = result.json()
    assert payload["ok"] is True
    assert payload["data"]["command"] == "export.context"
    assert "envelope" in payload["data"] and "data" in payload["data"]


def test_schema_cli_unknown_is_usage_error(run_cli: RunCli) -> None:
    result = run_cli("schema", "bogus.command", "--json")
    assert result.exit_code == 2
    assert result.json()["error"]["type"] == "usage"
