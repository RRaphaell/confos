# confos — Progress

**Status:** living · **Last updated:** 2026-06-01

The running state of the build. I update this every session: what's done, what's in
progress, what's next, and pointers to any research notes. Read this first when resuming.

---

## Current state

**Phase: 6 (Hardening & release polish) — COMPLETE. v0.1.0 tagged. All 7 phases done.**

- ✅ **Phase 6 built (v0.1.0):** every command's `--help` has 2-3 examples (test-pinned);
  `confos schema` documents every `--json`-envelope command (drift-guarded); full
  exit-code contract tests (network 4 / partial 5 / interrupt 130 / unexpected-error wrap);
  `doctor` checks openreview-py; CONTRIBUTING.md + opt-in `scripts/live-test.sh`;
  clean-checkout wheel install verified; CI actions bumped off Node 20. Two adversarial
  multi-agent sweeps (architecture-critic + code-reviewer sign-off, then a fix-verification
  pass) run and their findings fixed (CSV formula-injection hardening incl. BOM/Unicode-ws,
  `--json` purity on parse errors, envelope ok/warnings uniformity, doc/code alignment).
  Version 0.1.0; 192 tests; CI green.
- ✅ **Phase 5 built:** `export context` (self-contained, cited context pack — JSON +
  markdown, LLM-free, SCHEMAS §6), `export papers`/`authors` (CSV + JSONL),
  `confos schema <command>` (output-contract discovery), finalized AGENTS.md/SKILL.md.
  Verified live (MLMP); 167 tests; CI green.
- ✅ **Phase 4 built:** `trends topic`/`compare` (matched/total/share + first→last delta,
  SCHEMAS §5), `viz topics`/`orgs` (terminal bar charts), `viz network` (networkx
  co-authorship graph → terminal/mermaid/html, HTML-escaped). Verified live (MLMP); 132 tests.
- ✅ **Phase 3 built:** `authors find --topic` (ranked people + why-relevant + provenance,
  RANKING §2, pinned by the §3 acceptance test), `coauthors`, `stats overview/topics/orgs/
  countries` with honest `data_quality` + `--explain`, user-editable alias files
  (topics/orgs/countries). Verified live (MLMP); 119 tests; CI green.
- ✅ **Phase 2 built:** FTS5 search + explore + index rebuild.
- ✅ Decisions/assumptions captured in [DECISIONS.md](DECISIONS.md) (now through D20).
- ✅ **Phase 0:** package scaffold, typer CLI, `init`/`doctor`, full command tree, SQLite
  schema + migrate, JSON envelope, CI.
- ✅ **Phase 1 built:** OpenReview adapter (resolve/fetch/normalize), local status
  derivation (D4), author identity (D5), raw-JSONL-truth + derived SQLite/FTS, one-txn
  upsert, hybrid incremental (new + edited, D17), `--force`/`--dry-run`/partial(exit 5),
  `venues` (list/search/show/add/aliases) + alias map. Verified live (MLMP, 33 papers) +
  offline vcrpy replay. ruff + mypy(strict) + 72 pytest green; CI green.
- 🎉 **All phases complete — v0.1.0 released.**

## Phase checklist (see BUILD_PLAN.md §5 for detail)

| Phase | Name | Status |
|---|---|---|
| 0 | Foundation (scaffold, init/doctor, CI) | ✅ done (validated) |
| 1 | Ingest (OpenReview → raw JSONL + SQLite) | ✅ done (validated) |
| 2 | Search & explore | ✅ done (validated) |
| 3 | People discovery & stats | ✅ done (validated) |
| 4 | Trends & visualization | ✅ done (validated) |
| 5 | Export & agent surface | ✅ done (validated) |
| 6 | Hardening & release polish (v0.1.0) | ✅ done (validated, tagged) |

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

### Phase 1 deliverables
- [x] `models.py` — VenueRef / IngestOptions / NormalizedPaper / NormalizedAuthor / IngestResult
- [x] `adapters/` — SourceAdapter Protocol + OpenReviewAdapter (resolve/fetch/normalize/search)
- [x] `normalize/` — topics (full); orgs/countries best-effort from email domain (Phase-3 enriches)
- [x] `db/repositories/` — venues (+ ingest_runs watermarks), papers (+ authors/topics/fts), authors, orgs
- [x] `services/ingest.py` — hybrid incremental (D17), raw-JSONL current-state snapshot, one-txn upsert, partial(exit 5)
- [x] `services/venues.py` + `venues` command (list/search/show/add/aliases) + built-in alias map
- [x] `ingest` command wired; `schema.sql` + `venues.submission_venueid`
- [x] tests: unit (normalize, adapter) + integration (ingest service, venues CLI, vcrpy replay of a real venue)
- [x] **DoD:** ingest a fixture venue → SQLite + raw JSONL; incremental re-sync (incl. edits); provenance stamped; gate + CI green

### Phase 2 deliverables
- [x] `fts.py` (safe MATCH builder) + `serialize.py` (SCHEMAS §2/§3 dict mappers)
- [x] `services/search.py` — papers search (bm25, filters, deterministic order), show, related
- [x] `services/authors.py` — search/show/papers; `services/orgs.py` — top/papers
- [x] `services/index.py` — rebuild (re-derive from raw JSONL, validate-before-destroy) + status
- [x] repositories: FTS search + lookups (papers/authors/orgs); `_render.py` human tables + resolve_limit
- [x] commands papers/authors/orgs/index wired (json/plain/human); authors find/coauthors → Phase 3
- [x] tests: fts, search service (ranking/filters/determinism/rebuild), search CLI contract
- [x] **DoD:** ranked + cited results offline; `--json` matches SCHEMAS; fresh-user + agent-consumer + code-reviewer subagents pass

### Phase 3 deliverables
- [x] `fts.topic_query` (RANKING §1) + `aliases.py` (topics/orgs/countries) + pyyaml dep
- [x] `services/ranking.py` — `authors find` (RANKING §2 score + tie-break + why-relevant +
  provenance) + `coauthors`; pinned by the RANKING §3 fixed-ranking acceptance test
- [x] `services/stats.py` + `db/repositories/stats.py` — overview/topics/orgs/countries with
  honest `data_quality` (known/unknown/low-confidence + method)
- [x] org/country aliases threaded through normalize (re-applied via `index rebuild`, D3)
- [x] `authors find/coauthors` + `stats` commands wired; `orgs top` carries coverage too
- [x] tests: RANKING §3 acceptance, fts topic_query, aliases, stats data_quality
- [x] **DoD:** explainable + provenance-backed ranking; honest stats; architecture-critic
  confirmed it is NOT a worse OpenReview site

### Phase 5 deliverables
- [x] `services/export.py` — `build_context_pack` (papers+authors+orgs+stats+thin_areas+notes,
  LLM-free, SCHEMAS §6) + markdown render + CSV/JSONL bulk (formula-injection-safe)
- [x] `schemas.py` + `confos schema <command>` — versioned output-contract discovery
- [x] `export` (context json/markdown, papers/authors csv/jsonl) + `schema` commands
- [x] repo helpers `papers.list_all` / `authors.list_for_export` (no SQL in the service)
- [x] removed dead `NotImplementedYetError`; finalized AGENTS.md + SKILL.md
- [x] tests: context-pack structure/markdown, CSV escaping + round-trip, JSONL, schema registry
- [x] **DoD:** context pack self-contained + fully cited; agent-consumer completed a real
  task ("top papers + people on topic X, cited") using only confos

### Phase 6 deliverables (v0.1.0)
- [x] `--help` for every command carries 2-3 examples (CLI_CONTRACT §10), test-pinned
- [x] `confos schema` documents every `--json`-envelope command; drift-guard test
- [x] error-path tests: exit 4 (network), 5 (partial), 130 (interrupt), unexpected-error wrap
- [x] `doctor` checks openreview-py (offline); docs aligned (no phantom network probe)
- [x] CONTRIBUTING.md; opt-in `scripts/live-test.sh`; clean-checkout wheel install verified
- [x] CI bumped off Node 20 (checkout@v5, setup-uv@v6)
- [x] two adversarial multi-agent sweeps (sign-off + fix-verification); all findings fixed
- [x] version 0.1.0; CHANGELOG `[0.1.0]`; **tagged v0.1.0**
- [x] **DoD:** clean install + quickstart works; subagent passes clean; v1 surface complete

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
- 2026-05-31 · Phase 1 · architecture-critic + code-reviewer + agent-consumer (all
  **pass_with_findings**, no criticals) → fixed: implemented the incremental HYBRID
  (mintcdate new + `tmdate:desc` edit-catch) so post-decision status flips/edits are
  caught (D17); snapshot is now current-state merge (no stale truth / dup lines);
  defensive parsing guards scalar keyword/author fields (no char-by-char); `venues
  search` excludes role sub-groups; `venues add` refuses to remap an ingested slug;
  `items_seen` consistent with the persisted run row; `NotFoundError` (`type:not_found`)
  for missing venues; empty-id note skipped; `extract_year` handles glued years.
  Deferred (logged): adapter registry + neutral timestamps before source #2 (D19).
  +6 regression tests; verified live (MLMP) + offline replay.
- 2026-05-31 · Phase 2 · code-reviewer + agent-consumer (PASS) + fresh-user
  (pass_with_findings) → fixed: dup-authorid no longer crashes ingest/rebuild (OR
  IGNORE); `index rebuild` validates venue.json + normalizes BEFORE any destructive
  write so a bad snapshot fails clean with the store untouched (no half-wiped FTS, D20);
  `--limit 0` honoured; readable human search table (ellipsis titles, collapsed venue,
  rounded score); `authors search` shows ids; keywords in `papers show`; friendlier
  empty-venue message; org fallback name = domain (honest); SQL pulled out of services
  (exists/reset_entities/count_table). Not bugs (verified): bm25 ties broken by id-asc;
  Phase-3 org polish + venues-search acronym noted. +5 regression tests; verified live.
- 2026-05-31 · Phase 3 · code-reviewer (pass_with_findings) + architecture-critic
  (pass_with_findings, **"not a worse OpenReview site — the wedge is real"**) +
  agent-consumer (PASS) → fixed: `orgs top` now carries the data_quality coverage footer
  (honesty parity with `stats orgs`); candidate-cap truncation emits a warning; SCHEMAS §4
  clarified (Unknown lives in data_quality, not a row); ranking-test docstring corrected
  (count is dominant, not absolute). Verified: topic_query FTS-injection-safe, ranking
  deterministic + tie-break pinned, D3 alias re-derivation works end-to-end, layering clean.

- 2026-05-31 · Phase 4 · code-reviewer (pass_with_findings) + agent-consumer (PASS) →
  fixed: mermaid node ids are now positional/injective (distinct author_ids that differ
  only in punctuation no longer collide into one node); mermaid labels strip newlines;
  trends emits a warning when a requested venue isn't ingested (zeros are self-explaining,
  not a phantom decline) or the match cap is hit. Verified: HTML escaping robust, stdout
  pure across mermaid/html/json, deltas correct. +2 regression tests.

- 2026-06-01 · Phase 5 · code-reviewer (pass_with_findings) + agent-consumer (PASS,
  **"an agent CAN produce a credible, fully-cited brief from confos alone"**) → fixed:
  moved export's bulk SQL into repo helpers (layering); CSV formula-injection escaping
  (=/+/-/@); SCHEMAS §6 aligned (pack includes abstracts + leaner stats shape). Verified:
  context pack self-contained + cited + LLM-free, schema shapes match real output, CSV/JSONL
  round-trip. Deferred (logged): a "venue not ingested" warning on empty --venue results
  across search/stats (AGENTS.md already tells agents to check `venues list` first).

- 2026-06-01 · Phase 6 · v1 sign-off sweep (4 lenses: architecture / correctness / contract
  / release, 21 agents, every finding adversarially verified → 17 confirmed, 0 dropped) then
  a fix-verification pass (per-fix skeptics + completeness critic) → fixed: **[HIGH]** CSV
  formula-injection bypass via leading whitespace (later widened to BOM + all Unicode ws);
  **[HIGH]** `--json` after the subcommand leaked non-JSON on parse errors (`_wants_json`
  argv sniff, scoped to pre-`--` tokens); **[MED]** partial-ingest `ok` now agrees with
  exit 5; **[MED]** `schema` registry completed for all 9 missing envelope commands +
  drift-guard test; **[MED]** `doctor` openreview-py check + doc alignment; **[LOW]**
  trends+ingest warnings de-duplicated to the envelope level, mermaid label hardening
  (`;`/`#`/backtick), `venues search --limit 0`, several doc/code alignments. Left as
  logged D19 decisions: the adapter-registry / search_venues-on-Protocol seam (intentional
  one-adapter-v1 simplification). +regression tests for each. 192 tests; CI green; tagged.

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
