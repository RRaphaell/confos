# confos — Decisions & Assumptions Log

**Status:** living · **Last updated:** 2026-06-02

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
**Update (D21, v0.1.0):** `CONTRIBUTING.md` was added at release (the "premature" window
closed when the repo went public); everything else here stays cut.

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

### D17 — Incremental ingest is a true hybrid; the snapshot is current-state (2026-05-31, Phase 1)
**What:** re-running `ingest` (D6) now fetches BOTH new submissions (`mintcdate` >
stored `max_tcdate`) AND edited notes (a `sort='tmdate:desc'` scan that short-circuits
at the stored `max_tmdate`) — so abstract edits, late co-authors, and decision-time
`venueid` rewrites (under_review→accepted) are caught without `--force`. The raw JSONL
snapshot is written **current-state, keyed by id**: a full run rewrites it; an incremental
run merges fetched notes into it (one line per id). **Why:** ARCHITECTURE §8 + research §6
promise this hybrid; the first cut implemented only the `mintcdate` half, so the default
re-ingest silently missed status flips and the snapshot went stale (Phase-1 architecture-
critic, both majors). The merge is idempotent, so a failed DB transaction simply re-merges
next run (no duplicate lines), and `index rebuild` re-normalizes truth with no dedup
ambiguity (last/only line per id wins). **Alternatives:** mintcdate-only + document the
gap (rejected — the product's core claim is trustworthy acceptance status); append-only log
(rejected — stale truth + dedup burden on rebuild).

### D18 — Schema evolves freely during 0.x; frozen at v0.1.0 (2026-05-31, Phase 1)
**What:** before the v0.1.0 release the SQLite schema may change in place (e.g. Phase 1
added `venues.submission_venueid`) while keeping `user_version = 1`; pre-release stores are
disposable (re-`init`/re-ingest). At v0.1.0 the schema is frozen and any later change bumps
`user_version` with a real migration. **Why:** the only stores that exist during 0.x are
ephemeral test stores; a migration ladder for an unreleased tool is the exact over-build D13
avoids. **Alternatives:** bump `user_version` per dev tweak (rejected — premature migration
machinery); never change the schema (rejected — Phase 1 genuinely needed the column).

### D19 — Adapter seam carries OpenReview vocabulary in v1; neutralize before source #2 (2026-05-31, Phase 1)
**What:** `NormalizedPaper`/`VenueRef` carry OpenReview-shaped fields (`tcdate`/`tmdate`,
`*_venueid`) and commands construct `OpenReviewAdapter` directly (no registry). **Why:**
acceptable for a one-adapter v1 (BUILD_PLAN §3 simplicity); building a registry + fully
source-neutral watermark model now would be speculative. **Before a second adapter (AIE/
PMLR/OpenAlex) lands:** add a `source name → adapter factory` registry so commands resolve
the adapter from `VenueRef.source` and derive provenance `sources` from it, and treat
`tcdate/tmdate` as the OpenReview adapter's watermark detail (other sources may leave them
null and use a different strategy). Logged so it isn't rediscovered late (Phase-1 critic).

### D20 — `index rebuild` validates before it destroys (2026-05-31, Phase 2)
**What:** rebuild loads every `venue.json` + normalizes every raw note FIRST (read-only,
fail-soft on bad note lines); only then, in one transaction, does it drop/recreate the
FTS tables, reset the derived entities, and repopulate. A malformed `venue.json` (or
unknown source) raises a clean `ConfigError` (exit 3) BEFORE any destructive write, so
the existing index is untouched. **Why:** the first cut dropped the FTS tables (which
self-committed) then re-derived, so a mid-rebuild failure left search silently empty
against a populated store (Phase-2 critic). Validate-before-destroy makes rebuild safe
without fighting SQLite's DDL-transaction quirks. **Alternatives:** skip bad venues and
continue (rejected — silently drops a venue's papers from the index); per-venue partial
rebuild (rejected — more complexity than a one-shot re-derive needs).

### D21 — Phase 6 release decisions (2026-06-01, v0.1.0)
**What:** for v0.1.0 we (a) ADD `CONTRIBUTING.md` (the D11 Phase-6 trigger fired — going
public) and an opt-in `scripts/live-test.sh`; (b) keep `doctor` fully offline — the
"network" check sketched in early docs is CUT (it would surprise `--no-input` callers and
confos is offline after ingest), so `doctor` checks env/DB/FTS5/openreview-py only and the
contract docs were trimmed to match; (c) the `schema` command must document *every*
command that emits a `--json` envelope (export papers/authors are the raw-bulk exception),
enforced by a drift-guard test; (d) `warnings` live at the envelope level only across all
commands; `ok` always agrees with the exit code. **Why:** uniform, discoverable, honest
JSON contract for agents + a clean public release. **Still CUT (per D11):** SECURITY.md,
SBOM/pip-audit/Dependabot. **Still deferred (per D19):** the source→adapter registry and
putting `search_venues` on the `SourceAdapter` Protocol — both land before adapter #2.

### D22 — Incremental migrations after the v0.1.0 freeze (2026-06-02, Enrichment M0)
**What:** `db/migrate.py` now converges two paths against `PRAGMA user_version`: a **fresh**
store (`version 0`) applies the complete current `schema.sql` in one shot and jumps to
`SCHEMA_VERSION`; an **existing** store (`1 ≤ version < SCHEMA_VERSION`) applies the ordered
`_MIGRATIONS` steps newer than it. Steps are additive (`ALTER TABLE … ADD COLUMN` via an
`_add_columns` helper that diffs `table_info`, so a step is idempotent + crash-safe; new
tables use `CREATE TABLE IF NOT EXISTS`) and `schema.sql` always mirrors the latest shape.
Each schema-changing enrichment phase appends a step + bumps `SCHEMA_VERSION`. The upgrade
path per phase is **`migrate` (adds empty columns) → `index rebuild` (backfills from raw)**.
**Why:** D18 froze the schema at v0.1.0 and said the next change ships a real migration; the
enrichment phases (0/1/2/4) each add columns/tables to *existing* stores, so apply-once (D13)
no longer suffices. **Alternatives:** Alembic (rejected — framework overhead for a
single-process local store); blow-away-and-re-init (rejected — discards a user's ingested
venues for an additive change; raw survives either way but a forced re-ingest is a worse UX).
*Supersedes D13's "apply-once" for ≥ v2; the fresh-store fast path is unchanged.*

### D23 — Phase 0: `rejected` status + capture pdf/bibtex/supplementary (2026-06-02, Enrichment)
**What:** (a) added the `rejected` `PaperStatus`, derived from the venue group's
`rejected_venue_id` (read into `VenueRef.rejected_venueid`) with a fallback to the
conventional `…/Rejected_Submission` venueid suffix — so a snapshot whose venue.json predates
the field still reclassifies on a no-network `index rebuild`. (b) Persist `pdf_url`/`bibtex`/
`supplementary_url`, all already present in the raw note content (pdf/supplementary server
paths are prefixed with the `https://openreview.net` web host; bibtex is verbatim). The three
artifact fields are surfaced in `papers show` + `export papers` and gated behind a
`paper_dict(include_artifacts=…)` flag so lean list/search/context views (and the context
pack) stay small — same precedent as `abstract`. **Why:** these are free wins — the data is
already on disk, so a `migrate` + `index rebuild` (no re-download) reclassifies 254 NeurIPS-2025
papers and backfills links for all 5,540. **Alternatives:** suffix-only reject detection
(rejected — fragile if a venue renames the bucket; the group field is authoritative when
present); putting bibtex in every view (rejected — bloats search/context output).
**Verified:** real-store rebuild → `accepted 5286 / rejected 254`, pdf+bibtex 5540/5540,
supplementary 2784/5540, offline in ~17s.

### D24 — Phase 1: author profile enrichment via anonymous per-profile fetch (2026-06-02)
**What:** a new `confos enrich profiles --venue <slug>` fetches each tilde-handle author's
OpenReview profile and fills `authors.affiliation_current/affiliation_country/homepage/
gscholar/dblp/expertise` + the `orgs`/`author_affiliations` rows — fixing the four
previously-empty surfaces (`orgs top`, `stats orgs`, `stats countries`, `viz orgs`). Current
institution = the `history` entry that is still open (`end is None`), else the most recent;
country comes from the profile's explicit ISO alpha-2 code (authoritative) mapped to a
display name. Profiles snapshot to `raw/<venue>/profiles.jsonl` (one record per handle,
including `not_found` markers); `index rebuild` replays them offline (D3). Profile-derived
affiliations are **high**-confidence, email-domain ones **low** — stats report the split.
**Key findings (verified live):** (a) the batched `search_profiles`/`tools.get_profiles`
endpoint is **403 for anonymous** users, but **per-profile `get_profile(handle)` works
anonymously**; (b) OpenReview **rate-limits `/profiles` to ~20 requests/min per IP** (HTTP
429) — a *total* cap, so concurrency doesn't help (measured: 8 workers @ 0.33/s was slightly
*slower* than sequential @ 0.39/s, just 429 churn). So the fetcher is per-profile and
**sequential** (the client's built-in 429-retry self-paces on the window reset), best-effort
(genuine "Profile Not Found" → record; transient error → don't record, retried on resume),
and **resumable** (skip handles already in the snapshot). For neurips-2025 that's ~23k
one-time fetches at ~20/min (≈ several hours, run incrementally), cached forever. A
`--workers` knob was considered and **cut** (D11 — it never helps against a total cap). **Why:** the product's "find people working on X, ranked" wedge was
affiliation-blind; this is the single biggest credibility fix (`stats orgs --explain` went
from `0/5540`). **Alternatives:** batched fetch (rejected — auth-only); fetch during base
`ingest` (rejected — keeps base ingest fast + offline-after; opt-in `enrich` matches "raw is
truth"). **Resolves open decisions 2 (dedicated `enrich` command) + 3 (opt-in, not
ingest-default).** **Framing:** we surface where people work + their public links, **not**
emails (the API redacts email local-parts for anonymous reads, and we drop them anyway).

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
  ✅ **Done (D21, v0.1.0):** CONTRIBUTING.md added; SECURITY.md stays cut.
