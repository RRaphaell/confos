"""Config loading + validation (CLI_CONTRACT §7)."""

from __future__ import annotations

from pathlib import Path

import pytest

from confos.config import DEFAULT_OPENREVIEW_BASEURL, Config, load_config
from confos.errors import ConfigError


def test_missing_file_returns_defaults(tmp_path: Path) -> None:
    cfg = load_config(tmp_path / "nope.toml")
    assert cfg == Config()
    assert cfg.default_venue is None
    assert cfg.openreview_baseurl == DEFAULT_OPENREVIEW_BASEURL


def test_valid_config(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('default_venue = "neurips-2025"\nopenreview_baseurl = "https://example.test"\n')
    cfg = load_config(path)
    assert cfg.default_venue == "neurips-2025"
    assert cfg.openreview_baseurl == "https://example.test"


def test_unknown_key_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('bogus_key = "x"\n')
    with pytest.raises(ConfigError):
        load_config(path)


def test_bad_toml_syntax(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("this = = invalid")
    with pytest.raises(ConfigError):
        load_config(path)
