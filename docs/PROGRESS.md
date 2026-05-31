# confos — Progress

**Status:** living · **Last updated:** 2026-05-31

The running state of the build. I update this every session: what's done, what's in
progress, what's next, and pointers to any research notes. Read this first when resuming.

---

## Current state

**Phase: 0 (Foundation) — COMPLETE (gate green, 4-subagent validation passed, findings fixed). Next: Phase 1.**

- ✅ Docs/blueprint complete & cross-validated (3 subagent passes; 6 criticals fixed).
- ✅ Repo initialized, pushed to private GitHub: `RRaphaell/confos`.
- ✅ Decisions/assumptions captured in [DECISIONS.md](DECISIONS.md) (now through D16).
- ✅ **Phase 0 built:** package scaffold, typer CLI, `init`/`doctor`, full command tree
  (stubs for later phases), SQLite schema + migrate, JSON envelope, CI. ruff + mypy(strict)
  + 31 pytest all green locally.
- ⏳ **Next:** Phase 1 — Ingest (OpenReview → raw JSONL + SQLite).

## Phase checklist (see BUILD_PLAN.md §5 for detail)

| Phase | Name | Status |
|---|---|---|
| 0 | Foundation (scaffold, init/doctor, CI) | ✅ done (validated) |
| 1 | Ingest (OpenReview → raw JSONL + SQLite) | not started |
| 2 | Search & explore | not started |
| 3 | People discovery & stats | not started |
| 4 | Trends & visualization | not started |
| 5 | Export & agent surface | not started |
| 6 | Hardening & release polish (v0.1.0) | not started |

### Phase 0 deliverables
- [x] `pyproject.toml` (uv, hatchling), `.python-version` (3.12), ruff/mypy/pytest config
- [x] `src/confos/` package: `cli.py`, `config.py`, `paths.py`, `console.py`, `errors.py`
- [x] `output/` — json envelope, table, plain (graph deferred to Phase 4)
- [x] `db/` — `connection.py`, `schema.sql` (full v1 schema), `migrate.py`
- [x] `commands/` — `init` + `doctor` working; full tree stubbed for later phases
- [x] `_clickcompat.py` shim (typer-vendored click)
- [x] CI workflow (ruff + format + mypy + pytest)
- [x] tests: unit (config/paths/json/migrate) + integration (CLI phase-0 surface)
- [x] **DoD:** `--help` / `--version` / `init` / `doctor` work; doctor checks env/DB/FTS5; gate green

> **Per-phase mechanics (so the build survives context loss mid-phase):**
> When a phase starts, expand its deliverables into a checkbox list right here, and add a
> one-line **validation log** entry when its subagents run (subagent → verdict → findings
> fixed/deferred). That way a fresh session can tell exactly where the phase stands and
> whether validation happened.

## Validation log
_(one line per subagent pass, per phase — added as the build proceeds)_
- 2026-05-31 · blueprint · architecture-critic + fresh-user + re-validation + readiness →
  6 criticals fixed, over-engineering trimmed, verdict **ready to implement**.
- 2026-05-31 · Phase 0 · code-reviewer + architecture-critic + fresh-user + agent-consumer
  (all **pass_with_findings**, no criticals) → fixed: `--plain` now raw TSV (no rich
  wrapping/tab-stripping); bare-group + click-parse errors under `--json` now emit a JSON
  usage envelope (stdout stays pure JSON); `doctor --json` top-level `ok` mirrors health;
  `--verbose` merge uses max (no accidental `-vv`); `add_completion=False`; schema uses
  `IF NOT EXISTS` (idempotent recovery) + dropped the dead `PRAGMA`; reworded idempotent
  init. Deferred (logged): `-vv` tracebacks for typed errors (BUILD_PLAN §3 wants them),
  doctor/init logic in command (services layer deferred by design). +9 regression tests.

## Research notes gathered
_(none yet — added under `docs/research/` as I look things up during the build)_
- `docs/research/openreview-api.md` — OpenReview v2 API mechanics (pre-existing)
- `docs/research/name-conflict.md` — name availability (pre-existing)

## Open questions / to confirm with Raphael
- Reserve the `confos` name on PyPI before any public mention (cheap, do at Phase 6 prep).
- (none blocking Phase 0)

## Session log
- **2026-05-31** — Reframed confos to general-purpose; wrote full doc set; studied
  create-cli/gogcli/ft/birdclaw; ran architecture-critic + fresh-user + re-validation
  subagents; fixed 6 criticals; cut over-engineering per Raphael; added DECISIONS.md +
  PROGRESS.md + research/decision discipline to BUILD_PLAN; git init + pushed to private
  GitHub (commits stripped of AI-attribution trailer).
