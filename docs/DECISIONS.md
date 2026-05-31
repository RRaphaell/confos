# confos — Decisions & Assumptions Log

**Status:** living · **Last updated:** 2026-05-31

A lightweight ADR (Architecture Decision Record). Every non-obvious choice, and every
assumption we're relying on, gets an entry — so neither future-me nor Raphael has to
re-derive it. New entries appended at the bottom with a date. Format: **what · why ·
alternatives considered**. Assumptions get a **how-to-verify** line.

---

## Decisions

### D1 — Product is a general-purpose conference CLI, not an event tool (2026-05-31)
**What:** confos is a standalone, agent-native CLI for conference intelligence (search,
people-find, trends, viz, export), usable by anyone. **Why:** an event-anchored framing
("help Raphael organize a NeurIPS dinner") is a use case, not a product, and made the doc
narrow. **Alternatives:** event-specific tool (rejected — too narrow); generic OpenReview
browser (rejected earlier — competes with the OpenReview site/PaperCopilot, no wedge).

### D2 — Language/stack: Python 3.12 · uv · typer · rich · pydantic v2 · SQLite/FTS5 (2026-05-31)
**What:** the stack in ARCHITECTURE §5. **Why:** `openreview-py` is the canonical data
client (Python); analysis/viz ecosystem is Python; matches Raphael's world. typer+rich
are best-in-class CLI/render. uv for fast, reproducible installs. **Alternatives:** Go
(like gogcli) / TS (like ft/birdclaw) — rejected because we'd hand-rebuild the OpenReview
data layer for no benefit. We take the *shape* of those repos, not their language.
Pin **3.12** (not 3.14, too new for some deps).

### D3 — Local-first: raw JSONL is truth, SQLite/FTS5 is a derived cache (2026-05-31)
**What:** `ingest` writes raw JSONL snapshots (source of truth) → normalize → SQLite
(+FTS5), which is fully rebuildable via `index rebuild`. **Why:** lets us re-normalize
(better org/country/topic mapping) without re-hitting the API; makes ingest auditable and
the DB disposable. **Alternatives:** SQLite-only (rejected — can't re-normalize offline);
query-OpenReview-live (rejected — slow, rate-limited, not offline). Same pattern as `ft`.

### D4 — Ingest pulls the FULL submission set; status derived locally (2026-05-31)
**What:** `confos ingest` fetches all submissions via the venue's `submission_name`
invitation, stores each note's raw `venueid`, and derives `status` locally (`accepted`
iff `raw_venueid == published_venueid`). `--accepted-only` is a read-time filter, never a
separate network query. **Why:** OpenReview only rewrites `venueid` *after* decisions, so
a `content={'venueid': ...}` query returns ~0 papers pre-decision. **Alternatives:** the
venueid-filter ingest (rejected — breaks mid-review). Source: research/openreview-api.md.

### D5 — Public ids ARE the OpenReview ids (no surrogate keys) (2026-05-31)
**What:** `papers.id` = note id; `authors.id` = profile id, else `email:<addr>`, else
`name:<slug>#<n>` (flagged unresolved, never name-merged). **Why:** stable across
`index rebuild`, aligns with provenance, safe for agents to round-trip ids between calls.
**Alternatives:** autoincrement surrogate (rejected — not rebuild-stable, breaks saved ids).

### D6 — No `sync` command; re-running `ingest` is the incremental update (2026-05-31)
**What:** there is no separate `sync` verb. `confos ingest` uses stored watermarks
(`max_tcdate` + `max_tmdate`) for incremental updates; `--force` does a full re-pull.
**Why:** one obvious command beats two overlapping ones. **Alternatives:** separate
`sync` (rejected — redundant surface; the earlier docs referenced it inconsistently).

### D7 — `--topic` is FTS over title+abstract+keywords, not exact keyword match (2026-05-31)
**What:** topic matching builds an FTS5 query (comma=OR, space=AND, alias-expanded) over
the text, ranked by bm25. **Why:** OpenReview keywords are free-text and ~30–60% coverage;
exact-keyword matching would miss most relevant papers. **Alternatives:** exact keyword
equality (rejected — silent misses); semantic/embeddings (deferred — adds heavy deps).
Full spec: RANKING.md §1.

### D8 — `authors find` ranking is explicit and deterministic (2026-05-31)
**What:** score = paper_count + 0.5·normalized_bm25 + recency_bonus (0 for single-venue);
tie-break score→count→author_id; output includes `why_relevant` + `matched_papers`. **Why:**
this is the product's differentiator; it must be testable, not vibes. **Alternatives:**
LLM ranking (rejected for v1 — must work without an LLM). Full spec: RANKING.md §2.

### D9 — Context pack is LLM-free in v1; "open questions" → "thin_areas" (2026-05-31)
**What:** `export context` returns only data we can derive + cite; the LLM-implying
"open_questions" field is replaced by `thin_areas` (under-represented keyword combos,
labelled heuristic). **Why:** principle "useful without an LLM"; LLM synthesis is a later
`--llm` phase. **Alternatives:** ship open_questions via LLM in v1 (rejected — scope).

### D10 — Adapter seam now, one adapter (openreview) in v1 (2026-05-31)
**What:** a `SourceAdapter` Protocol exists; only `openreview` is implemented. AIE/PMLR/
OpenAlex are designed-for-later. **Why:** design the seam so future sources don't force a
rewrite, but don't build speculative adapters. **Alternatives:** hard-code OpenReview
(rejected — future rewrite); build multiple adapters now (rejected — over-engineering).

### D11 — Deliberately CUT as over-engineering (2026-05-31)
**What:** no SECURITY.md, no CONTRIBUTING.md (premature), no SBOM/pip-audit/Dependabot,
no `--wrap-untrusted`, no `--rate-delay`, no per-project config layer, no plugin system,
no coverage-percentage gate. **Why:** Raphael's explicit guardrail — public anonymous
data, focused CLI; these add complexity without value. The only output-safety rule is
`html.escape` on free-text in HTML graphs. **Re-add only if a concrete need appears.**

### D12 — Git: no AI-attribution trailer; conventional commits; push per phase (2026-05-31)
**What:** commit messages are plain conventional-commits with **no** `Co-Authored-By:
Claude` line (the harness default must be omitted). Push to private `RRaphaell/confos`
after each phase. **Why:** Raphael's hard rule. **Note:** the 3 blueprint commits were
history-rewritten to strip a trailer that slipped in.

### D13 — Full v1 schema applied once via `PRAGMA user_version` (2026-05-31, Phase 0)
**What:** the complete v1 schema (core tables + FTS5) lives in `db/schema.sql` and is
applied exactly once at `init`, gated by `PRAGMA user_version` (`db/migrate.py`).
`index rebuild` drops + recreates only the derived FTS tables (`drop_derived` /
`create_derived`) and re-normalises from raw JSONL. **Why:** simplest correct model;
no Alembic, no per-phase migration ladder. Tables sit empty until their phase populates
them. **Alternatives:** grow the schema per phase with versioned migrations (rejected —
migration framework overhead for a single-process local store). *Resolves the Phase-0
"migration model" open item.*

### D14 — Global output flags work before AND after the subcommand (2026-05-31, Phase 0)
**What:** `--json/--plain/--quiet/--verbose/--no-input/--no-color` are accepted both as
root options (`confos --json doctor`) and after the command (`confos doctor --json`) via
a `global_output_options` decorator that injects them onto every command and OR-merges
them into the base `AppContext`. `--home`/`--version` are root-only; `--venue`/`--limit`
are command-level where the command tree lists them, with a root-level global as the
fallback default. **Why:** CLI_CONTRACT §1 says "global flags first," but every worked
example in AGENTS.md/PRODUCT/README puts `--json --no-input` *after* the command — agents
will type it that way. Supporting both removes a sharp edge. **Alternatives:** root-only
globals (rejected — breaks the documented agent usage); duplicate every flag on every
command (rejected — unmaintainable).

### D15 — Internal schema naming refined from the ARCHITECTURE §6 sketch (2026-05-31, Phase 0)
**What:** the FK column is `papers.venue_slug` (not `venue_id`) referencing
`venues.slug` (the PK); added explicit `withdrawn_venueid` / `desk_rejected_venueid`
columns on `venues`, and `number` / `tldr` / `primary_area` / `tcdate` / `tmdate` /
`venue_string` on `papers`. **Why:** ARCHITECTURE §6 is a sketch (with `...`); these make
local status derivation (D4) and incremental sync (S1) implementable without ambiguity.
The public JSON field stays `venue` (the slug) per SCHEMAS §2. **Alternatives:** literal
`venue_id` name (rejected — it stores a slug, so the name would mislead).

### D16 — typer vendors click → `_clickcompat` shim (2026-05-31, Phase 0)
**What:** typer ≥ 0.16 vendors click as `typer._click`; `standalone_mode=False` re-raises
*that* click's exceptions, so `cli.main` catches classes resolved through a small
`_clickcompat` shim (vendored first, external click fallback). **Why:** matching the exact
exception classes typer raises is required for the exit-code mapping to fire. **Alternatives:**
depend on external `click` (rejected — would not be the same class typer raises → missed
`isinstance`).

---

## Assumptions (verify before/while building)

### A1 — OpenReview v2 anonymous reads cover what we need
**Assumption:** public submissions, authors, keywords, decisions are readable without auth.
**Verify:** Phase 1 `doctor`/ingest against a real small venue; confirm fields present.
Source: research/openreview-api.md (says yes).

### A2 — `submission_name` must be read per-venue from the group (not hard-coded)
**Assumption:** venues vary (`Submission` / `Blind_Submission` / …). **Verify:** read
`venue_group.content['submission_name']` during ingest; fixture-test ≥1 venue.

### A3 — FTS5 is available in the user's Python sqlite build
**Assumption:** most CPython builds include FTS5. **Verify:** `doctor` checks it and emits
a precise remediation if missing. (Don't build a fallback unless it actually bites.)

### A4 — A venue ingests in "a few minutes / tens of MB" (the cost we advertise)
**Assumption:** NeurIPS-scale (~4–5k papers) is minutes, not hours. **Verify:** measure on
first real ingest; correct README/AGENTS numbers if off.

### A5 — Keyword coverage is partial (~30–60%)
**Assumption:** many papers lack keywords, so topic/stats lean on FTS over title+abstract
and report coverage. **Verify:** compute `papers_with_keywords/total` during Phase 3 stats.

---

## Open spec items — decide when the owning phase starts (don't guess earlier)

A readiness review (2026-05-31) confirmed the blueprint is build-ready but flagged these
small holes. They don't block Phase 0; pin each (as a new D-entry) when its phase begins,
so two implementers can't diverge. Recommended defaults in parentheses — confirm, don't
auto-accept.

- **Phase 0 — migration model:** how `schema.sql` is applied. (Rec: `PRAGMA user_version`,
  apply-once; `index rebuild` = drop derived tables + re-normalize from raw JSONL. No
  Alembic.) Also: enumerate `config.toml` keys as they're added.
- **Phase 2 — `papers related <id>` algorithm:** currently unspecified (biggest hole).
  (Rec: FTS `MATCH` built from the source paper's title+keywords — same machinery as
  `--topic`, deterministic, no new deps.)
- **Phase 2 — exposed `bm25` field sign/scale:** SQLite `bm25()` returns negative (lower =
  better). (Rec: expose `-bm25()` so bigger = more relevant; the 0–1 normalization stays
  *inside* the ranker per RANKING §2. Pin so the public JSON number is stable.)
- **Phase 2 — `--plain` contract:** (Rec: downgrade to "best-effort; **JSON is the
  contract**" rather than spec'ing TSV columns per command — simpler and honest.)
- **Phase 2 — default scope when `--venue` omitted:** (Rec: all ingested venues, applied
  consistently across search/find/stats — RANKING §2 already says this for `authors find`.)
- **Phase 3 — `top_authors`/`top_orgs` in stats/trends:** (Rec: simple `COUNT(*)`
  aggregation, NOT the bm25-weighted `authors find` score — that ranker is find-only.)
- **Phase 3 — `orgs top` ordering + `data_quality.method`:** pin the org-normalization as
  an ordered algorithm (email-domain → alias table → Unknown) and the method string.
- **Phase 3 — move exit-code/error-path unit tests here** (as each code becomes reachable),
  not deferred wholesale to Phase 6 (agents branch on exit codes — it's a contract).
- **Phase 5 — `thin_areas` heuristic:** define threshold + population (within the topic's
  matched set vs across venue). Keep it simple and clearly labelled as a heuristic.
- **Phase 6 — add a minimal `CONTRIBUTING.md`** before going public (table-stakes for a
  "serious OSS repo"; correctly cut until then). SECURITY.md stays cut (public anon data).
