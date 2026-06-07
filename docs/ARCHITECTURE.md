# confos — Architecture & System Design

**Status:** canonical · **Last updated:** 2026-06-07

How confos is built: high-level design, data flow, components, stack, data model.
For the user-facing command contract see [CLI_CONTRACT.md](CLI_CONTRACT.md); for the
build process see [BUILD_PLAN.md](BUILD_PLAN.md).

---

## 1. Design philosophy

Three ideas drive every decision:

1. **Local-first, index-as-cache.** Raw source snapshots are the source of truth;
   SQLite (+FTS5) is a derived, rebuildable index. The network is touched only by
   explicit network commands: `ingest`, `venues search`, and `enrich profiles`. The
   search/stats/trends/viz/export/read surface is offline and fast.
2. **Layered, one-way dependencies.** `commands → services → adapters / repositories`.
   Adapters fetch but never write the DB. Repositories own SQL but never touch the
   network. Commands parse args and format output but contain no business logic.
3. **Agent-native contract is a first-class product surface**, not an afterthought:
   stable `--json`, stdout/stderr discipline, exit codes, provenance on every row.

## 2. High-level system diagram

```
                                   confos CLI
┌─────────────────────────────────────────────────────────────────────────────┐
│  HUMAN (rich tables/charts)      SCRIPTS / CI (--json, --plain)     AGENT     │
│            │                              │                    (SKILL + --json)│
│            └──────────────┬───────────────┴───────────┬──────────────┘        │
│                           ▼                            ▼                       │
│                  ┌───────────────────────────────────────────┐                │
│                  │  commands/  (typer)                        │  parse args,   │
│                  │  init doctor venues ingest papers authors  │  format output │
│                  │  orgs stats trends viz export index schema │  (no logic)    │
│                  └───────────────────┬───────────────────────┘                │
│                                      ▼                                         │
│                  ┌───────────────────────────────────────────┐                │
│                  │  services/  (orchestration / business)     │  the "verbs"   │
│                  │  ingest search authors trends stats         │                │
│                  │  viz export normalize                       │                │
│                  └───────┬───────────────────────────┬────────┘                │
│              fetch only  │                            │  read/write only        │
│                          ▼                            ▼                         │
│        ┌─────────────────────────┐      ┌──────────────────────────────┐      │
│        │  adapters/              │      │  db/repositories/             │      │
│        │  SourceAdapter (proto)  │      │  papers authors venues orgs   │      │
│        │  openreview.py          │      │  (SQL + FTS5, typed)          │      │
│        │  [later: aie, pmlr,     │      └───────────────┬──────────────┘      │
│        │   openalex]             │                      ▼                       │
│        └────────────┬────────────┘      ┌──────────────────────────────┐      │
│                     │                    │  LOCAL STORE  (~/.confos)     │      │
│         network ────┼──────────────┐     │  confos.db   (SQLite + FTS5)  │      │
│                     ▼              │     │  raw/<venue>/*.jsonl (truth)  │      │
│        ┌──────────────────────┐   └────▶│  config.toml · aliases/ · logs│      │
│        │  OpenReview v2 API    │  ingest │  exports/                     │      │
│        │  api2.openreview.net  │  writes └──────────────────────────────┘      │
│        └──────────────────────┘                                                │
└─────────────────────────────────────────────────────────────────────────────┘

Rules enforced by the layering:
  • adapters never import repositories (they return normalized objects + raw payloads)
  • repositories never import adapters (no network in the query path)
  • commands never contain business logic (they call exactly one service)
  • only explicit network commands (`ingest`, `venues search`, `enrich profiles`) touch
    OpenReview; search/stats/trends/viz/export are offline
```

## 3. Data-flow diagram (ingest → query)

```
  INGEST (network, explicit)                    QUERY (offline, fast)
  ─────────────────────────                     ──────────────────────
  confos ingest neurips-2025                     confos papers search "..."
        │                                              │
        ▼                                              ▼
  openreview adapter                            search service
   • resolve venue id                                 │
   • get_all_notes(invitation=…)                      ▼
   • paginate (limit=1000)                      papers repository
        │                                        • FTS5 MATCH + bm25()
        ▼                                        • filters (venue/year/org)
  raw JSONL snapshot ──────┐                          │
  raw/neurips-2025/*.jsonl │ (source of truth)        ▼
        │                  │                     output renderer
        ▼                  │                      • table (rich)  → human
  normalize service        │                      • json envelope → agent
   • papers/authors/orgs   │                      • plain (TSV)   → scripts
   • topics from keywords  │
   • provenance stamped    │      REBUILD (no network)
        │                  │      ───────────────────
        ▼                  └────▶ confos index rebuild
  SQLite upsert (by id)           re-normalize from raw JSONL
   • papers, authors, …           → fresh SQLite + FTS (truth unchanged)
   • FTS5 index built
        │
        ▼
  ingest_runs row (counts, watermark for incremental sync)
```

Why raw JSONL is kept as the source of truth: it lets us **re-normalize without
re-hitting the API** (e.g. when we improve org-alias mapping or country parsing), it
makes ingest auditable, and it makes the SQLite layer fully disposable/rebuildable.

## 4. Component responsibilities

| Layer | Owns | Must NOT |
|---|---|---|
| `commands/` | arg parsing (typer), output formatting, exit codes | contain business logic, call adapters/repos directly |
| `services/` | orchestration, ranking, the "verbs" | know about typer, know about SQL strings |
| `adapters/` | fetching from a source, returning normalized objects + raw payloads | write to the DB, know about other adapters |
| `db/repositories/` | typed SQL queries, FTS, upserts | make network calls, format output |
| `normalize/` | org/country/topic normalization (pure functions) | I/O |
| `output/` | JSON envelope, rich tables, plain TSV, mermaid/html | know where data came from |
| `models.py` | pydantic v2 domain models (Paper, Author, Venue, Org, Stat) | I/O |
| `config.py` / `paths.py` | config precedence, XDG-style dirs | business logic |

**Store-lifecycle exception:** `init` and `doctor` are store bootstrap/diagnostics, not
business logic — they may use `db.connection`/`db.migrate` directly (creating the store,
applying the schema, reading the schema version) rather than going through a service.
There's no meaningful "verb" to wrap a one-line `migrate()`. Every other command still
flows command → service → repository.

## 5. Stack (and why each piece)

| Concern | Choice | Why |
|---|---|---|
| Language | **Python 3.12** | `openreview-py` is the canonical client; analysis/viz ecosystem; matches Raphael's world. Pin 3.12 (3.14 too new for some deps). |
| Packaging / env | **uv** | Fast; `uv tool install confos` / `uvx confos`; lockfile reproducibility. |
| CLI framework | **typer** | Type-hint driven, subcommands, auto-help, completions; `create-cli` rubric maps cleanly. |
| Terminal UI / viz | **rich** | Tables, bar charts, progress on stderr, color with `NO_COLOR` respect. |
| Data source | **openreview-py (v2)** | Official client; anonymous public reads; handles pagination/auth. |
| Storage | **SQLite + FTS5** (stdlib `sqlite3`) + **raw JSONL** | Local-first; FTS5/BM25 built in; zero server; JSONL = re-normalizable truth. |
| Validation / models | **pydantic v2** | Validate adapter payloads + config; typed domain models. |
| HTTP (non-OpenReview later) | **httpx** | Only if/when needed for future adapters. |
| Graph viz | **networkx** (+ mermaid/HTML emit) | Co-authorship / topic graphs; export, not a GUI. |
| Tests | **pytest** + **vcrpy** (record/replay) | Fixture-first; no live API in CI. |
| Lint / format | **ruff** | One fast tool for lint+format. |
| Types | **mypy** (strict) | Catch contract drift; agent JSON is a public contract. |
| CI | **GitHub Actions** | typecheck + lint + test on push. |

## 6. Data model

### Local store layout (`~/.confos/`, override `$CONFOS_HOME`)
```
~/.confos/
  confos.db                 # SQLite source-of-record (derived, rebuildable)
  config.toml               # user config
  raw/
    openreview/
      neurips-2025/
        submissions.jsonl   # raw notes (TRUTH — re-normalizable)
        profiles.jsonl      # optional author-profile enrichment snapshot
        venue.json
        ingest_run.json
  aliases/
    orgs.yml                # user-editable org normalization
    countries.yml
  exports/                  # generated context packs / csv / html graphs
  logs/
```

### Core tables (SQLite)
```
venues(slug, source, source_venue_id, published_venueid, submission_venueid,
       submission_name, display_name, year, url, last_ingested_at, ...)
papers(id, venue_slug, title, abstract, keywords_json, status,
       acceptance_type, raw_venueid, url, pdf_url, bibtex, supplementary_url,
       review_count, rating_mean, rating_std, confidence_mean, decision,
       pdate, tcdate, tmdate, created_at, updated_at)
authors(id, profile_id, display_name, aliases_json,
        affiliation_current, affiliation_country, homepage, gscholar, dblp,
        expertise_json, data_quality, ...)
paper_authors(paper_id, author_id, position, raw_name)  -- positional; raw_name kept for unresolved
orgs(id, name, normalized_name, country, aliases_json)
author_affiliations(author_id, org_id, start_year, end_year, confidence)
paper_topics(paper_id, topic, source)                  -- topic = normalized keyword
reviews(paper_id, reviewer_key, rating, confidence, sub_scores_json, raw_rating)
ingest_runs(id, venue_slug, status, started_at, finished_at,
            items_seen, items_added, items_updated,
            max_tcdate, max_tmdate, error)             -- BOTH watermarks (S1)

-- FTS5 (derived, rebuildable from the above)
papers_fts(paper_id UNINDEXED, title, abstract, keywords, author_names, org_names)
authors_fts(author_id UNINDEXED, name, aliases, affiliations, topics)
orgs_fts(org_id UNINDEXED, name, aliases, country)
```

Identity rules (the hard part — see §8). **The public id IS the source id** so it is
stable across `index rebuild` and safe for agents to round-trip (C3):
- `papers.id` = the OpenReview **note id** (e.g. `aBcDeFgHiJ`). No surrogate autoincrement.
- `authors.id` = the OpenReview **profile id** (`~Alice_Smith1`) when present; else
  `email:<normalized-email>`; else `name:<slug>#<n>` flagged `data_quality='unresolved'`
  and **never merged across papers by name** (C3/S5). `paper_authors.raw_name` preserves
  display name + order even for unresolved authors so author order is never lost (S6).
- Orgs normalized via email-domain first, then a curated, **user-editable** alias table;
  everything else is "Unknown / Other," counted honestly.
- Because ids are deterministic functions of source ids, re-normalizing from raw JSONL
  (`index rebuild`) reproduces identical ids — rebuild is idempotent.

## 7. CLI contract (summary)

Full detail in [CLI_CONTRACT.md](CLI_CONTRACT.md); JSON shapes in [SCHEMAS.md](SCHEMAS.md);
ranking in [RANKING.md](RANKING.md). The essentials:
- `confos [global flags] <group> <command> [args]`
- **stdout** = requested data only (valid JSON under `--json`). **stderr** = progress,
  warnings, diagnostics. Nonzero exit on failure.
- Global: `--json`, `--plain`, `--quiet`, `--verbose`, `--no-input`, `--no-color`,
  `--home`, `--venue`, `--limit`. Respect `NO_COLOR`, TTY detection.
- Config precedence: **flags > env > user config > defaults** (no per-project layer).
- Exit codes: `0` ok · `1` generic · `2` usage/validation · `3` config/env ·
  `4` network/backend · `5` partial ingest · `130` interrupted (SIGINT, bounded cleanup).
- Safety classes: **local-read** (search/show/find/stats/trends/viz/export — no network),
  **network** (`ingest`, `venues search`, `enrich profiles`), **local-write** (`index rebuild`, `venues add`),
  **destructive** (future prune/reset — need `--force` non-interactive). There is **no
  `sync` command** — re-running `ingest` is the incremental update (C1).
- `confos schema <command>` prints the JSON schema of that command's output (the JSON
  contract is versioned — see [SCHEMAS.md](SCHEMAS.md)).

## 8. Hard problems (named up front, not discovered late)

| Problem | Reality | confos approach |
|---|---|---|
| **Accepted vs rejected** | OpenReview rewrites a note's `venueid` only *after* decisions; pre-decision every note's `venueid` is the under-review bucket, so a `content={'venueid': venue_id}` query returns ~0 papers mid-review (C2) | **Ingest always pulls the FULL submission set** via `invitation=f'{venue_id}/-/{submission_name}'`, stores each note's raw `venueid`, and derives `status` **locally**: `accepted` iff `raw_venueid == venue.published_venueid`; withdrawn/desk-rejected from the buckets named in the venue group. `--accepted-only` is a local `WHERE status='accepted'`, **never a different network query**. Mark unknown explicitly. |
| **Incremental sync** | `/notes` endpoint exposes `mintcdate` but **no `mintmdate`** | `mintcdate` watermark for new notes + periodic full re-fetch with `sort='tmdate:desc'` short-circuit to catch edits; store **both** `max_tcdate` and `max_tmdate` in `ingest_runs`. Re-running `confos ingest` performs this incremental update; `--force` ignores watermarks for a full re-pull (there is no separate `sync` command — C1). |
| **Author identity** | Names collide; one human can have multiple merged tilde ids | Key on profile id when present; never auto-merge by name |
| **Affiliations / countries** | Free-text, missing ~10–15%, inconsistent | Email-domain + curated alias table; report known/unknown/low-confidence in every stat; `--explain` shows method |
| **Venue id conventions** | `NeurIPS.cc/2025/Conference` vs `colmweb.org/COLM/2024/Conference` | Curated alias map + `venues add` for arbitrary ids; never derive algorithmically |
| **Rate/politeness** | Notes ingest is fine sequentially; `/profiles` has a practical anonymous cap of about 20 profiles/min | Keep ingest sequential and cached; make profile enrichment opt-in, sequential, and resumable via `profiles.jsonl`. No `--workers` knob because concurrency only creates 429 churn. |

(Full OpenReview API mechanics: [research/openreview-api.md](research/openreview-api.md).)

## 9. Adapter model (extensibility)

```python
class SourceAdapter(Protocol):
    name: str
    def resolve_venue(self, slug_or_id: str) -> VenueRef: ...
    def fetch_papers(self, ref: VenueRef, opts: IngestOptions) -> Iterable[RawPaper]: ...
    def normalize(self, raw: RawPaper) -> NormalizedPaper: ...
```
v1 ships `openreview`. The seam (VenueRef / RawPaper / NormalizedPaper) is designed so
`aie` (talks/speakers), `pmlr` (proceedings fallback), and `openalex` (citations) become
additive adapters — **no rewrite**. We design the seam now; we do not build them now.

## 10. Repository structure

```
confos/
  pyproject.toml            .python-version   .gitignore   LICENSE   README.md
  AGENTS.md
  docs/                     PRODUCT · ARCHITECTURE · CLI_CONTRACT · BUILD_PLAN ·
                            REFERENCES · research/
  src/confos/
    __init__.py  cli.py  config.py  paths.py  console.py  errors.py  models.py
    output/      json.py  table.py  plain.py  graph.py
    db/          connection.py  migrate.py  schema.sql  repositories/{papers,authors,venues,orgs}.py
    adapters/    base.py  openreview.py
    services/    ingest.py  search.py  authors.py  orgs.py  stats.py  trends.py  viz.py  export.py  ranking.py
    normalize/   orgs.py  countries.py  topics.py
    commands/    init.py  doctor.py  venues.py  ingest.py  papers.py  authors.py  orgs.py  stats.py  trends.py  viz.py  export.py  index.py  schema.py
  tests/         unit/  integration/  fixtures/
  .agents/skills/confos/SKILL.md
  .github/workflows/ci.yml
```
