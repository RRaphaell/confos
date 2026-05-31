"""Local-store layout and home-directory resolution.

confos keeps everything under one directory (``~/.confos`` by default). The raw
JSONL snapshots are the source of truth; ``confos.db`` is a rebuildable index
(ARCHITECTURE §6). This module is pure path math — it never creates files except
through :meth:`Paths.ensure`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .errors import ConfigError

DEFAULT_HOME = Path("~/.confos")
ENV_HOME = "CONFOS_HOME"


def resolve_home(explicit: str | os.PathLike[str] | None = None) -> Path:
    """Resolve the confos home dir: ``--home`` flag > ``$CONFOS_HOME`` > ``~/.confos``."""
    if explicit is not None:
        chosen: str | os.PathLike[str] = explicit
    elif os.environ.get(ENV_HOME):
        chosen = os.environ[ENV_HOME]
    else:
        chosen = DEFAULT_HOME
    return Path(chosen).expanduser().resolve()


@dataclass(frozen=True)
class Paths:
    """All filesystem locations derived from the confos home directory."""

    home: Path

    @classmethod
    def resolve(cls, explicit: str | os.PathLike[str] | None = None) -> Paths:
        return cls(home=resolve_home(explicit))

    # --- files ---------------------------------------------------------------
    @property
    def db(self) -> Path:
        return self.home / "confos.db"

    @property
    def config(self) -> Path:
        return self.home / "config.toml"

    # --- directories ---------------------------------------------------------
    @property
    def raw(self) -> Path:
        return self.home / "raw"

    @property
    def aliases(self) -> Path:
        return self.home / "aliases"

    @property
    def exports(self) -> Path:
        return self.home / "exports"

    @property
    def logs(self) -> Path:
        return self.home / "logs"

    # --- per-source / per-venue raw snapshot paths ---------------------------
    def raw_venue_dir(self, source: str, venue_slug: str) -> Path:
        """Directory holding the raw snapshot for one venue from one source."""
        return self.raw / source / venue_slug

    def alias_file(self, name: str) -> Path:
        """User-editable alias file, e.g. ``orgs.yml`` / ``countries.yml`` / ``topics.yml``."""
        return self.aliases / name

    # --- creation ------------------------------------------------------------
    def exists(self) -> bool:
        """Whether the store has been initialised (home + db present)."""
        return self.home.is_dir() and self.db.exists()

    def ensure(self) -> None:
        """Create the directory skeleton (idempotent). Does not touch the DB."""
        for directory in (self.home, self.raw, self.aliases, self.exports, self.logs):
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise ConfigError(
                    f"Could not create confos store directory {directory}: {exc.strerror or exc}.",
                    hint="Check permissions, or point --home / $CONFOS_HOME somewhere writable.",
                ) from exc
