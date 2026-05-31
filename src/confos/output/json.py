"""The ``--json`` envelope — confos's public, versioned contract (SCHEMAS §1).

Agents hard-code field paths against this shape (e.g. ``.data.papers[].title``), so
the envelope is treated as an API: fields may be *added* in a minor version; renames
or removals bump ``schema_version``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from ..errors import ConfosError

SCHEMA_VERSION = "1"


def make_provenance(
    db_path: str,
    *,
    sources: list[str] | None = None,
    venue: str | None = None,
    stamp_time: bool = True,
) -> dict[str, Any]:
    """Build the ``provenance`` block. ``generated_at`` is stamped here, not by tests."""
    resolved_sources = sources if sources is not None else ["openreview"]
    prov: dict[str, Any] = {"db": db_path, "sources": resolved_sources}
    if venue is not None:
        prov["venue"] = venue
    if stamp_time:
        prov["generated_at"] = datetime.now(UTC).isoformat()
    return prov


def success_envelope(
    command: str,
    query: dict[str, Any],
    data: Any,
    *,
    provenance: dict[str, Any],
    warnings: list[str] | None = None,
    ok: bool = True,
) -> dict[str, Any]:
    """Assemble a data envelope. Key order is part of the readable contract.

    ``ok`` is True for the normal "command produced its data" case. A command may pass
    ``ok=False`` when the data itself reports an unhealthy/negative result that should
    agree with a non-zero exit code (e.g. ``doctor`` when a hard check fails) — the
    payload still rides in ``data``, not ``error``.
    """
    return {
        "ok": ok,
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "query": query,
        "data": data,
        "warnings": warnings or [],
        "provenance": provenance,
    }


def error_envelope(command: str, error: ConfosError) -> dict[str, Any]:
    """Assemble the error envelope (SCHEMAS §1 error form)."""
    err: dict[str, Any] = {
        "code": error.exit_code,
        "type": error.error_type,
        "message": error.message,
    }
    if error.hint:
        err["hint"] = error.hint
    return {
        "ok": False,
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "error": err,
    }


def dumps(envelope: dict[str, Any]) -> str:
    """Serialise an envelope deterministically (insertion order, UTF-8 preserved)."""
    return json.dumps(envelope, indent=2, ensure_ascii=False, sort_keys=False)
