"""``confos doctor`` — check environment, store, FTS5, and the ingest backend.

Runs offline: python/sqlite/FTS5, the openreview-py dependency, and the local store/DB.
There is deliberately no network probe (it would surprise ``--no-input`` callers and
confos is offline after ingest). Exit code is 3 (config) if any *hard* check fails
(today: FTS5), otherwise 0 — soft findings (no store yet, no openreview-py) only warn.
"""

import platform
import sys
from importlib.metadata import version as pkg_version

import typer

from ..console import AppContext, bind_command
from ..db.connection import connect, fts5_available, sqlite_version
from ..db.migrate import SCHEMA_VERSION, current_version
from ..errors import EXIT_CONFIG
from ..output.plain import tsv_rows
from ..output.table import data_table

_STATUS_STYLE = {"ok": "green", "warn": "yellow", "fail": "red"}


def _check(name: str, status: str, detail: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def _collect_checks(app_ctx: AppContext) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []

    py = ".".join(str(v) for v in sys.version_info[:3])
    py_ok = sys.version_info[:2] >= (3, 12)
    checks.append(
        _check("python", "ok" if py_ok else "warn", f"{py} ({platform.python_implementation()})")
    )

    checks.append(_check("sqlite", "ok", sqlite_version()))

    if fts5_available():
        checks.append(_check("fts5", "ok", "available"))
    else:
        checks.append(
            _check("fts5", "fail", "missing — confos search needs SQLite built with FTS5")
        )

    # openreview-py is the ingest/venue-search backend (a declared dependency). Offline
    # queries don't need it, so a missing one only warns rather than failing hard.
    try:
        checks.append(_check("openreview-py", "ok", f"v{pkg_version('openreview-py')}"))
    except Exception as exc:  # any import/metadata failure here is a soft finding
        checks.append(
            _check("openreview-py", "warn", f"unavailable ({exc}); ingest/venue search disabled")
        )

    paths = app_ctx.paths
    if paths.home.is_dir():
        checks.append(_check("store", "ok", f"{paths.home}"))
    else:
        checks.append(_check("store", "warn", f"not created — run `confos init` ({paths.home})"))

    if paths.db.exists():
        try:
            conn = connect(paths.db, create_parents=False)
            try:
                version = current_version(conn)
            finally:
                conn.close()
        except Exception as exc:
            checks.append(_check("database", "fail", f"could not open: {exc}"))
        else:
            if version == SCHEMA_VERSION:
                checks.append(_check("database", "ok", f"schema v{version}"))
            elif version == 0:
                checks.append(
                    _check("database", "warn", "present but not migrated — run `confos init`")
                )
            else:
                checks.append(
                    _check(
                        "database",
                        "fail",
                        f"schema v{version} unsupported (expected v{SCHEMA_VERSION})",
                    )
                )
    else:
        checks.append(_check("database", "warn", "not created — run `confos init`"))

    return checks


def run(ctx: typer.Context) -> None:
    """Check the environment, local store, FTS5, and the openreview-py backend.

    Runs offline. Reports each check and its status. Exits 3 if a hard requirement (FTS5)
    is missing; soft findings (no store yet, openreview-py absent) only warn and exit 0.

    Examples:
      confos doctor
      confos doctor --json
    """
    app_ctx = bind_command(ctx, "doctor")
    checks = _collect_checks(app_ctx)
    overall_ok = not any(c["status"] == "fail" for c in checks)

    if app_ctx.is_json:
        # Top-level `ok` mirrors health so it agrees with the exit code (SCHEMAS note).
        app_ctx.render_json(
            {"ok": overall_ok, "checks": checks}, query={}, sources=[], ok=overall_ok
        )
    elif app_ctx.is_plain:
        tsv_rows(app_ctx.out, [(c["name"], c["status"], c["detail"]) for c in checks])
    else:
        rows = []
        for c in checks:
            status = c["status"]
            mark = {"ok": "✓", "warn": "!", "fail": "✗"}[status]
            if app_ctx.use_color:
                rendered = f"[{_STATUS_STYLE[status]}]{mark} {status}[/{_STATUS_STYLE[status]}]"
            else:
                rendered = f"{mark} {status}"
            rows.append((c["name"], rendered, c["detail"]))
        data_table(app_ctx.out, ["check", "status", "detail"], rows, title="confos doctor")

    if not overall_ok:
        raise typer.Exit(EXIT_CONFIG)
