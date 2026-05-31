"""User-editable alias files under ``~/.confos/aliases/`` (loaded if present).

* ``topics.yml`` — ``term: [synonyms]`` — expands ``--topic`` matching at QUERY time.
* ``orgs.yml`` — ``email-domain: "Canonical Org Name"`` — applied at INGEST/rebuild time.
* ``countries.yml`` — ``email-domain (or org name): "Country"`` — applied at ingest time.

Because org/country aliases are applied during normalization, editing them and running
``confos index rebuild`` re-derives the index with the better mapping — no re-fetch (D3).
All files are optional; a missing or malformed file yields empty aliases (best-effort).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .paths import Paths


@dataclass
class NormalizeAliases:
    """Aliases applied during normalization (ingest/rebuild)."""

    orgs: dict[str, str] = field(default_factory=dict)  # email-domain -> canonical org name
    countries: dict[str, str] = field(default_factory=dict)  # domain or org name -> country


def _load_map(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def load_normalize_aliases(paths: Paths) -> NormalizeAliases:
    orgs = {
        str(k).strip().lower(): str(v) for k, v in _load_map(paths.alias_file("orgs.yml")).items()
    }
    countries = {
        str(k).strip().lower(): str(v)
        for k, v in _load_map(paths.alias_file("countries.yml")).items()
    }
    return NormalizeAliases(orgs=orgs, countries=countries)


def load_topic_aliases(paths: Paths) -> dict[str, list[str]]:
    """``term -> [synonyms]`` for ``--topic`` expansion (lowercased)."""
    out: dict[str, list[str]] = {}
    for key, value in _load_map(paths.alias_file("topics.yml")).items():
        term = str(key).strip().lower()
        if not term:
            continue
        if isinstance(value, list):
            syns = [str(s).strip().lower() for s in value if str(s).strip()]
        elif isinstance(value, str):
            syns = [s.strip().lower() for s in value.split(",") if s.strip()]
        else:
            continue
        if syns:
            out[term] = syns
    return out
