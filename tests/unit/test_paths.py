"""Paths resolution + store skeleton (precedence A1: --home > $CONFOS_HOME > ~/.confos)."""

from __future__ import annotations

from pathlib import Path

import pytest

from confos.errors import ConfigError
from confos.paths import Paths, resolve_home


def test_resolve_home_explicit_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CONFOS_HOME", str(tmp_path / "from_env"))
    explicit = tmp_path / "from_flag"
    assert resolve_home(explicit) == explicit.resolve()


def test_resolve_home_env_when_no_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_home = tmp_path / "from_env"
    monkeypatch.setenv("CONFOS_HOME", str(env_home))
    assert resolve_home(None) == env_home.resolve()


def test_resolve_home_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CONFOS_HOME", raising=False)
    assert resolve_home(None) == Path("~/.confos").expanduser().resolve()


def test_subpaths(tmp_path: Path) -> None:
    paths = Paths(home=tmp_path)
    assert paths.db == tmp_path / "confos.db"
    assert paths.config == tmp_path / "config.toml"
    assert paths.raw_venue_dir("openreview", "neurips-2025") == (
        tmp_path / "raw" / "openreview" / "neurips-2025"
    )
    assert paths.alias_file("orgs.yml") == tmp_path / "aliases" / "orgs.yml"


def test_ensure_creates_skeleton(tmp_path: Path) -> None:
    paths = Paths(home=tmp_path / "store")
    assert not paths.exists()
    paths.ensure()
    for directory in (paths.home, paths.raw, paths.aliases, paths.exports, paths.logs):
        assert directory.is_dir()


def test_ensure_raises_configerror_on_unwritable(tmp_path: Path) -> None:
    # A file where a directory should be → mkdir fails → ConfigError.
    blocker = tmp_path / "blocker"
    blocker.write_text("not a dir")
    paths = Paths(home=blocker / "store")
    with pytest.raises(ConfigError):
        paths.ensure()
