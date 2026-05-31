"""User configuration and precedence.

Precedence (CLI_CONTRACT §7): command-line flags > env vars > user
``~/.confos/config.toml`` > built-in defaults. This module owns only the *file +
defaults* layer; the CLI callback overlays env and flags on top of what we return.

Config is deliberately tiny — confos reads public data with anonymous requests, so
there are very few knobs. New keys get added here (and documented) only when a
command actually needs one; we do not ship speculative settings.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .errors import ConfigError

DEFAULT_OPENREVIEW_BASEURL = "https://api2.openreview.net"


class Config(BaseModel):
    """Validated contents of ``config.toml`` (all keys optional)."""

    model_config = ConfigDict(extra="forbid")

    default_venue: str | None = Field(
        default=None,
        description="Venue slug used when a command omits --venue.",
    )
    openreview_baseurl: str = Field(
        default=DEFAULT_OPENREVIEW_BASEURL,
        description="Base URL for the OpenReview v2 API.",
    )


def load_config(path: Path) -> Config:
    """Load and validate ``config.toml``; return defaults if the file is absent."""
    if not path.exists():
        return Config()
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(
            f"Could not read config file {path}: {exc}",
            hint="Fix the TOML syntax or delete the file to fall back to defaults.",
        ) from exc
    try:
        return Config.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(
            f"Invalid config in {path}: {exc.errors()[0].get('msg', exc)}",
            hint="Allowed keys: default_venue, openreview_baseurl.",
        ) from exc
