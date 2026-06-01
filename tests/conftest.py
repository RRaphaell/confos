"""Shared test fixtures.

The ``run_cli`` fixture drives the real :func:`confos.cli.main` in-process so tests
exercise the actual exit-code mapping and stdout/stderr split — not a parallel test
harness. Each invocation is isolated to a temp ``$CONFOS_HOME``.
"""

from __future__ import annotations

import json as jsonlib
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from confos.cli import main


def leaf_command_paths() -> list[tuple[str, ...]]:
    """Every leaf command path the CLI exposes (canonical click names).

    Walks the click command tree typer builds (duck-typed via ``.commands`` since typer
    vendors its own click), so callers stay in sync with whatever the CLI exposes — used
    by the help-text and schema-registry contract tests.
    """
    import typer

    root = typer.main.get_command(__import__("confos.cli", fromlist=["app"]).app)

    def walk(command: object, prefix: tuple[str, ...]) -> list[tuple[str, ...]]:
        children = getattr(command, "commands", None)
        if isinstance(children, dict) and children:
            leaves: list[tuple[str, ...]] = []
            for name, sub in children.items():
                leaves.extend(walk(sub, (*prefix, name)))
            return leaves
        return [prefix]

    return sorted(walk(root, ()))


@dataclass
class CliResult:
    exit_code: int
    stdout: str
    stderr: str

    def json(self) -> Any:
        return jsonlib.loads(self.stdout)


RunCli = Callable[..., CliResult]


@pytest.fixture
def confos_home(tmp_path: Path) -> Path:
    return tmp_path / "confos"


@pytest.fixture
def run_cli(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    confos_home: Path,
) -> RunCli:
    def _run(*args: str, set_home: bool = True, env: dict[str, str] | None = None) -> CliResult:
        monkeypatch.setattr(sys, "argv", ["confos", *args])
        # Neutralise ambient env so tests are deterministic.
        for var in ("NO_COLOR", "CONFOS_CONFIG", "OPENREVIEW_USERNAME", "OPENREVIEW_PASSWORD"):
            monkeypatch.delenv(var, raising=False)
        if set_home:
            monkeypatch.setenv("CONFOS_HOME", str(confos_home))
        else:
            monkeypatch.delenv("CONFOS_HOME", raising=False)
        for key, value in (env or {}).items():
            monkeypatch.setenv(key, value)
        try:
            main()
            code = 0
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 0
        captured = capsys.readouterr()
        return CliResult(exit_code=code, stdout=captured.out, stderr=captured.err)

    return _run


@pytest.fixture
def initialized_home(run_cli: RunCli, confos_home: Path) -> Path:
    """A confos store that has already been ``init``-ed."""
    result = run_cli("init")
    assert result.exit_code == 0
    return confos_home
