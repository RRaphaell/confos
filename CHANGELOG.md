# Changelog

All notable changes to confos are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); versions follow SemVer.

## [Unreleased]

### Added
- **Enrichment Phase 5 — `confos brief`.** One command (`confos brief --venue <slug>
  [--topic t]`) produces a complete, cited conference landscape: overview, top papers (rated
  if reviews are ingested, else recent), hot topics, rising orgs, people-to-know, and
  (topic-mode) thin areas. Human Markdown by default; `--json` is an agent primitive (a
  superset of `export context`). LLM-free, and it degrades gracefully on an un-enriched store
  (telling you how to fill the gaps).
- **Enrichment Phase 2 — review scores & quality intelligence.** Ingesting with `confos
  ingest <venue> --with-reviews` now captures public Official_Review scores: papers carry
  `review_count`, `rating_mean`, `rating_std` (controversy), `confidence_mean`, and the
  `decision` verdict, with raw per-review rows for provenance. New `confos papers top`
  (highest mean rating) and `confos papers controversial` (highest rating variance) rank by
  quality, scoped to a topic/venue. The rating parser handles every venue format (`5`,
  `8: accept`). A later `index rebuild` reproduces it all offline.
- **Enrichment Phase 1 — author profile enrichment.** New `confos enrich profiles --venue
  <slug>` fetches each author's OpenReview profile (anonymous, best-effort, resumable) to fill
  the previously-empty people/orgs surfaces: `stats orgs`, `stats countries`, `orgs top`, and
  `viz orgs` now return real data, and authors gain `affiliation_country`, `homepage`,
  `gscholar`, `dblp`, and `expertise`. Profiles are cached in `raw/<venue>/profiles.jsonl`, so
  a later `confos index rebuild` reproduces all of it offline. Profile-derived affiliations are
  high-confidence; email-domain ones stay low (reported honestly via `--explain`).
- **Enrichment Phase 0 — capture dropped fields + the `rejected` status.** Papers now carry
  `pdf_url`, `bibtex`, and `supplementary_url` (all already downloaded, previously dropped) —
  surfaced in `confos papers show` and `confos export papers`. A new `rejected` status
  classifies post-review rejects (derived from the venue's `rejected_venue_id`, with a
  `…/Rejected_Submission` suffix fallback); these papers used to mislabel as `unknown`.
- **Incremental schema migrations.** `db/migrate.py` upgrades an existing store in place with
  additive, idempotent steps (fresh stores still apply the full schema in one shot). Upgrade
  an existing store with `confos index rebuild` — it backfills the new columns from the raw
  JSONL snapshot with **no re-download**.

### Changed
- `--json` Author objects gain `affiliation_country`/`homepage`/`gscholar`/`dblp`/`expertise`
  (additive; populated by `enrich profiles`). `export authors` CSV/JSONL gained the matching
  columns. `stats orgs`/`countries` `data_quality.method` now reflects the profile source and
  `low_confidence` counts only the email-domain affiliations.
- `--json` Paper objects gain `pdf_url`/`bibtex`/`supplementary_url` in `show` + `export
  papers` (additive; omitted from lean search/list views). `export papers` CSV/JSONL gained
  `pdf_url`, `supplementary_url`, and `bibtex` columns. SCHEMAS.md + `confos schema` updated.

## [0.1.0] - 2026-06-01

First public-grade release: the full v1 surface on OpenReview — ingest, search, people
discovery, orgs, honest stats, trends, visualization, export, context packs, and a bundled
agent skill — all offline after ingest, all with provenance.

### Added
- **Phase 6 — Hardening & release polish.** Every command's `--help` carries 2-3 examples
  (pinned by a test); `confos schema <command>` now documents every command that emits a
  `--json` envelope (drift-guarded); a full exit-code contract test (network 4, partial
  ingest 5, interrupt 130, unexpected-error wrap); `confos doctor` checks the openreview-py
  backend; CONTRIBUTING.md + an opt-in `scripts/live-test.sh`; clean-checkout wheel install
  verified. A multi-agent architecture-critic + code-reviewer sign-off pass was run and its
  findings fixed (CSV formula-injection hardening, `--json` purity on parse errors,
  envelope `ok`/`warnings` uniformity, doc/code alignment).
- **Phase 5 — Export & agent surface.** `confos export context --topic t [--venue v]
  [--format json|markdown]` produces one self-contained, fully-cited context pack (top
  papers with abstracts + ranked people with why-relevant + orgs + topic-scoped stats +
  heuristic thin areas), LLM-free. `confos export papers|authors --format csv|jsonl` dumps
  bulk data (spreadsheet-formula-injection-safe). `confos schema <command>` prints the
  versioned output contract for any command. AGENTS.md + the bundled skill finalized.
- **Phase 4 — Trends & visualization.** `confos trends topic <t> --venues a,b,c` and
  `confos trends compare a b --topic t` show a topic's matched/total/share across
  venues with a first→last delta and the top authors/orgs per venue. `confos viz topics`
  / `viz orgs` render terminal bar charts; `confos viz network --topic t
  --format terminal|mermaid|html` builds a co-authorship graph (networkx) and exports a
  mermaid diagram or a self-contained HTML page (free text HTML-escaped).
- **Phase 3 — People discovery & stats.** `confos authors find --topic` ranks the people
  actually publishing on a topic (count + relevance + recency), each with a why-relevant
  explanation, score breakdown, and cited matched papers — the differentiator, pinned by a
  fixed-ranking acceptance test. `confos authors coauthors` ranks collaborators by shared
  papers. `confos stats overview/topics/orgs/countries` reports aggregates with a
  `data_quality` block (known/unknown/low-confidence + method) and `--explain` — never
  faking clean numbers. User-editable alias files (`topics.yml` for `--topic` expansion;
  `orgs.yml`/`countries.yml` applied during normalization, re-derived via `index rebuild`).
- **Phase 2 — Search & explore.** `confos papers search` (FTS5/bm25, ranked + cited,
  filters: `--venue`/`--year`/`--org`/`--accepted-only`/`--limit`), `papers show`
  (+authors, `--with related`), `papers related`. `confos authors search/show/papers`
  and `confos orgs top/papers`. `confos index rebuild` re-derives the whole index from
  the raw JSONL snapshots offline (sync watermarks preserved) and `index status` reports
  row counts. All offline, deterministic, with the stable JSON envelope.
- **Phase 1 — Ingest (OpenReview).** `confos ingest <venue>` pulls a venue's full
  submission set, snapshots raw JSONL (the source of truth), normalizes, and upserts into
  SQLite + FTS in one transaction; status (accepted/under_review/withdrawn/desk_rejected)
  is derived locally from each note's raw venueid. Incremental re-runs use a hybrid
  watermark (new submissions by creation date + edited notes by modify date, so
  post-decision status flips are caught); `--force` re-pulls, `--dry-run` reports counts,
  partial failures exit 5. New `confos venues` group: list / search (network) / show / add
  / aliases, with a built-in alias map for major venues. Author identity follows OpenReview
  profile ids (else email / unresolved name), never merged across papers by name.
- **Phase 0 — Foundation.** Python/uv package scaffold; typer CLI with the full command
  tree (`init`, `doctor`, and stubbed groups for later phases); global flag handling that
  works before *and* after the subcommand; strict stdout/stderr split with a stable
  versioned JSON envelope; SQLite schema + apply-once migration with FTS5; `init` creates
  the `~/.confos` store; `doctor` checks env/DB/FTS5; GitHub Actions CI (ruff + mypy +
  pytest); unit + integration tests.

### Project setup
- Blueprint complete: product spec, architecture, CLI contract, ranking/topic spec, JSON
  schemas, build plan, references, agent docs.

[Unreleased]: https://github.com/RRaphaell/confos/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/RRaphaell/confos/releases/tag/v0.1.0
