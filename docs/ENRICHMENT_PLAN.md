# confos — Enrichment & Quality Intelligence Plan

**Created:** 2026-06-02
**Status:** In progress. **M0 + Phase 0 shipped (2026-06-02)** — see D22/D23 + PROGRESS.md. Phase 1 is next.
**Owner:** Raphael
**Scope:** Phases 0, 1, 2, 4, 5. **Phase 3 (semantic/clusters/map) is intentionally deferred** (big infra lift; see §Phase 3).

> **Read this first when resuming.** This document is the working memory for the next
> build chapter of confos. It captures *what* we're building, *why*, and *how* — with
> exact files, functions, schema diffs, and acceptance criteria — so we can start
> implementing from a cleared conversation without re-deriving anything.

---

## 0. TL;DR

confos v0.1.0 works end-to-end (ingest → index → search/stats/viz/export against live
OpenReview). But a hands-on test of `neurips-2025` (5,540 papers) surfaced a gap: every
command that needs **author affiliation** (`orgs top`, `stats orgs`, `stats countries`,
`viz orgs`) returns "no data," we **drop useful fields we already downloaded** (pdf link,
bibtex), we **throw away review scores** that ride along for free, and rejected papers are
**mislabeled** `unknown`. None of this is a bug — it's unfinished data capture.

This plan closes that gap and then adds the features the data unlocks, cheapest-first:

| Phase | Name | Net effect | Cost |
|---|---|---|---|
| **0** | Capture dropped fields + fix `rejected` status | pdf/bibtex/supplementary stored; 254 papers correctly labeled `rejected` | **free** — data already in raw; `index rebuild`, no re-download |
| **1** | Author profile enrichment | fixes orgs/countries/contacts; adds homepage/Scholar/DBLP/expertise | cheap — ~20k profile fetches, once, cached |
| **2** | Review scores & quality intelligence | per-paper rating/confidence/decision; `papers top`, `papers controversial`; quality-weighted ranking | cheap* — reviews ride on the `details=replies` sweep confos already does |
| ~~3~~ | ~~Semantic search + clusters + map~~ | **deferred** | big |
| **4** | OpenAlex citation enrichment | realized impact; `papers top --by citations` | medium — free API, title-match |
| **5** | `confos brief` | one-command landscape; the launch demo + agent primitive | cheap once 1–2 exist |

`*` Phase 2 is cheap because of a key finding (see §2): the reviews already come down in the
same `get_all_notes(details="replies")` call confos makes under `--include-decisions`. We
parse only the Decision today and discard the `Official_Review` notes in the same payload.

---

## 1. Why we're doing this

confos's stated differentiator (README, PRODUCT.md) is **not** "search papers" — it's that
an agent can drive a *local, composable, quality-aware* index that the website can't give
you: "who works on X, ranked," "the *good* papers on Y," "how a field moved." Today the
index is keyword-only and affiliation-blind, so it's closer to "grep over abstracts" than
"conference intelligence." Phases 0–2 turn the most-caveated, emptiest parts of the product
into real data; Phases 4–5 turn that data into the headline features and the demo.

This also fixes the single biggest credibility issue: `stats orgs --explain` currently
reports `0/5540 papers have signal` — the flagship "people & orgs" surface is empty.

---

## 2. What we found (evidence — don't re-derive)

All verified against the live OpenReview API and the on-disk raw snapshot
(`~/.confos/raw/openreview/neurips-2025/submissions.jsonl`) on 2026-06-02.

**Paper records (already downloaded) contain, per note:**
`title, authors, authorids, keywords, abstract, primary_area, venue, venueid, pdf,
_bibtex, paperhash, TLDR, supplementary_material, flagged_for_ethics_review`.
- confos **stores**: title, abstract, tldr, keywords, primary_area, venue→`acceptance_type`,
  venueid→`status`. ✅
- confos **drops** (but the data is right there in raw): **`pdf`** (link), **`_bibtex`**,
  **`supplementary_material`**. ← Phase 0.

**Author identity:** all 30,428 author IDs are profile handles like `~Nora_Belrose1`.
**Zero emails, zero affiliation fields** anywhere in the paper records. confos derives
orgs/countries from **email domains** (`normalize/orgs.py`, method
`author_affiliation_domain_v1`), so it has nothing to work with → `orgs 0`. ← Phase 1.

**Author profiles (one fetch deeper) DO carry the missing data.** `get_profile("~Nora_Belrose1")` returns:
`history[].institution {name, domain, country}` (e.g. EleutherAI / eleuther.ai / **US** —
country is explicit, no domain-guessing needed), plus `homepage, gscholar, dblp, expertise,
names, relations`. ← Phase 1 source.

**Reviews & decisions are public and already in the fetch path.** The adapter calls
`get_all_notes(invitation=…, details="replies")` **when `--include-decisions` is set**
(`adapters/openreview.py:122`). That payload embeds every reply. For an accepted paper the
replies include **4× `Official_Review`** with fields
`rating, confidence, quality, clarity, originality, significance, soundness,
strengths_and_weaknesses, summary, questions, limitations, …` plus **1× `Decision`**
(`decision`, `comment`). confos uses the replies **only** to read acceptance type from the
Decision (`_derive_acceptance_type`) and **discards the reviews**. ← Phase 2.

**Status is derived locally from `venueid` (D4).** For neurips-2025:
- `5286` → `NeurIPS.cc/2025/Conference` → `accepted` ✅
- `254` → `NeurIPS.cc/2025/Conference/Rejected_Submission` → falls through to **`unknown`**
  because there is no `rejected` bucket. ← Phase 0 fix.

**Acceptance type already works** (parsed from the human `venue` string): 4522 poster /
687 spotlight / 77 oral (= 5286 accepted). ✅ No work needed.

**Workshops are separate venues** (`NeurIPS.cc/2025/Workshop/<X>`), not in the Conference
ingest. Out of scope; ingest them as their own slugs if wanted.

**Data numbers (neurips-2025):** 5,540 papers · 23,013 authors · 30,428 paper-author links
· 20,003 paper-topics · 9,826 distinct topics · orgs 0.

---

## 3. Architecture & invariants to respect

Do **not** violate these — they're the spine of the codebase (see ARCHITECTURE.md,
DECISIONS.md, CONTRIBUTING.md):

1. **Layering.** `commands/ → services/ → {db/repositories, adapters}`. Commands do I/O and
   rendering only; business logic lives in `services/`; SQL lives in `db/repositories/`;
   network/source quirks live in `adapters/`. New code goes in the right layer.
2. **Raw JSONL is the source of truth (D3).** SQLite is a *derived, disposable* index.
   Anything we want to survive `index rebuild` must be **persisted to raw** at ingest time.
3. **`index rebuild` re-derives ALL core tables from raw, no network** (`services/index.py`:
   drops derived + `reset_entities` + re-runs `upsert_normalized_paper` over raw). This is
   our upgrade mechanism: add columns → migrate → ensure the data is in raw → `index rebuild`.
4. **Status derived from `venueid` + group metadata (D4)** — never a separate "accepted-only"
   query.
5. **Stable `--json` contract (SCHEMAS.md).** Changes must be **additive** (new fields ok;
   never rename/remove/retype existing ones). Update SCHEMAS.md + `confos schema` for each.
6. **Honest about uncertainty / provenance.** Every number traceable; `--explain` reports
   coverage + method + confidence. New data carries its own data-quality reporting.
7. **The gate (CONTRIBUTING.md):** `ruff` + `mypy --strict` + `pytest` must pass. Network is
   mocked with `vcrpy` cassettes; real-API tests are `@pytest.mark.live` (opt-in) and added
   to `scripts/live-test.sh`.
8. **Identity rules (D5):** `papers.id` = OpenReview note id; `authors.id` = profile id else
   `email:<addr>` else `name:<slug>#<n>`. Don't add surrogate keys to round-trippable entities.

---

## 4. The data-flow model & what each phase needs in raw

```
INGEST (network)                         index rebuild (no network)
 OpenReview ──► raw/<venue>/                  raw/<venue>/*.jsonl
   submissions.jsonl  (+details.replies          │  re-normalize
                       when --include-decisions)  ▼
   profiles.jsonl     (NEW, Phase 1)         SQLite core tables
   venue.json                                papers / authors / orgs /
        │ normalize                          author_affiliations /
        ▼                                     paper_authors / paper_topics / reviews
   SQLite + FTS                                  │
                                                 ▼  every query = local SQL, offline
```

What each phase needs present in **raw** before `index rebuild` can backfill it:
- **Phase 0** — already in existing `submissions.jsonl` (pdf/_bibtex/supplementary/venueid).
  **→ ships with zero re-download.**
- **Phase 1** — needs **`profiles.jsonl`** (new artifact). The existing store doesn't have it,
  so a one-time profile fetch is required (via re-ingest or a dedicated `enrich` command).
- **Phase 2** — needs `details.replies` inside `submissions.jsonl`. The existing store was
  ingested **without** `--include-decisions`, so it has no replies → a one-time re-ingest with
  reviews is required. `_note_to_raw` already snapshots `details` when present
  (`adapters/openreview.py:322`), so once re-ingested, reviews are rebuildable offline.
- **Phase 4** — needs a citations artifact (e.g. `citations.jsonl`) from OpenAlex.

---

## 5. Cross-cutting infra — M0: incremental migrations (do first) ✅ DONE (2026-06-02, D22)

> **Shipped.** `db/migrate.py` now carries an ordered `_MIGRATIONS` registry + an
> idempotent `_add_columns` helper; fresh stores apply `schema.sql` and jump to
> `SCHEMA_VERSION`, existing stores apply only the newer additive steps. `SCHEMA_VERSION = 2`.
> Crash-safe (re-applies cleanly). Tests in `tests/unit/test_migrate.py`.


**Problem:** `db/migrate.py` is apply-once (`SCHEMA_VERSION = 1`, only handles 0→1). Phases
0/2/4 **add columns**, so we need stepwise migrations.

**Plan:**
- Introduce an ordered migration registry in `db/migrate.py`, e.g.
  `_MIGRATIONS: list[tuple[int, str]]` of `(target_version, sql)` using
  `ALTER TABLE … ADD COLUMN` (cheap, safe, non-destructive in SQLite).
- `migrate()` applies every step with `target_version > current_version` in order, then sets
  `user_version`. Keep the existing 0→1 full-schema apply as step 1.
- Bump `SCHEMA_VERSION` as each phase lands (Phase 0 → v2, Phase 1 → v3, …).
- **Upgrade path for an existing store per phase:** `migrate` adds the (empty) columns →
  `confos index rebuild` backfills them from raw. Document this in each phase.
- New tables (e.g. `reviews`) are added in `schema.sql` *and* as an `ALTER`/`CREATE` migration
  step so both fresh and existing stores converge.

**Decision:** prefer additive migrations over "blow away and re-init" (raw survives either
way, but migrations keep the user's ingested venues without a full rebuild surprise).

---

## Phase 0 — Capture dropped fields + fix `rejected` status ✅ DONE (2026-06-02, D23)

> **Shipped + verified on the real store.** `index rebuild` (no network) → `accepted 5286 /
> rejected 254` (was 254 `unknown`), pdf+bibtex 5540/5540, supplementary 2784/5540, ~17s.
> Open decision #4 **decided:** the group exposes `rejected_venue_id` (verified live); we read
> it into `VenueRef.rejected_venueid` and fall back to the `/Rejected_Submission` suffix so
> pre-existing snapshots reclassify offline.

**Why:** Cheapest value on the board. The data is already on disk; we're just storing more of
it and correcting a label. Ships against the existing `neurips-2025` store with **no network**.

**Deliverables**
- `papers.pdf_url`, `papers.bibtex`, `papers.supplementary_url` populated.
- New status value **`rejected`**; the 254 neurips-2025 papers reclassify from `unknown`.
- `papers show` + `export papers` surface pdf/bibtex; `stats overview` shows a `rejected` row.

**How (files)**
- `models.py`: add `"rejected"` to `PaperStatus` literal; add `pdf_url`, `bibtex`,
  `supplementary_url` to `NormalizedPaper`.
- `adapters/openreview.py`:
  - `normalize()` / `_note_to_normalized`: read `content.pdf` (prefix path with
    `https://openreview.net`), `content._bibtex`, `content.supplementary_material`.
  - `_derive_status`: add a `rejected` branch. **Preferred:** add `rejected_venueid` to
    `VenueRef` and read `rejected_venue_id` from group content in `resolve_venue`
    (**verify the exact group field name** — see Open Decisions). **Fallback:** recognize the
    conventional `…/Rejected_Submission` venueid suffix.
- `db/schema.sql`: add the three `papers` columns; update the `status` comment to include
  `rejected`. `db/repositories/papers.py`: include new columns in `upsert_paper` + reads.
- `db/migrate.py`: migration → v2 (ALTER TABLE add 3 columns).
- `commands/papers.py` (`show`) + `commands/export.py` (`papers`): include new fields.
- `commands/stats.py`: ensure the status breakdown renders `rejected`.
- Docs: SCHEMAS.md (papers shape), `confos schema papers.show`/`export.papers`.

**Upgrade path:** `migrate` (adds columns) → `confos index rebuild` (backfills from existing
raw). No re-ingest.

**Caveats:** `pdf`/`supplementary_material` are server paths, not absolute URLs — prefix them.
A handful of papers may lack `pdf`. Keep `paperhash`, `flagged_for_ethics_review`,
`readers/writers/signatures` **out** (no value).

**Acceptance**
- `stats overview --venue neurips-2025` → `accepted 5286`, **`rejected 254`**, no `unknown`.
- `papers show <id> --json` includes non-null `pdf_url` + `bibtex`.
- Gate green; SCHEMAS.md updated.

**Tests:** unit for `_derive_status` (rejected), normalize populates new fields; a fixture note
with `Rejected_Submission`.

---

## Phase 1 — Author profile enrichment (fixes orgs / countries / contacts)

**Why:** Fixes all four "no data" commands **and** supercharges the "find people working on X"
differentiator (homepage, Scholar, DBLP, expertise). The write-path already exists —
`upsert_normalized_paper` (`services/ingest.py:132`) already creates `orgs` +
`author_affiliations` rows **whenever `author.affiliation` is set** — it's just always `None`
today. We're feeding a built-but-starved pipe.

**Deliverables**
- `orgs`, `author_affiliations`, `authors.affiliation_current/affiliation_country/profile_url`
  populated. `orgs top`, `stats orgs`, `stats countries`, `viz orgs` return real data.
- New author fields: `homepage`, `gscholar`, `dblp`, `expertise`. Surfaced in `authors show`
  (+ `--json`) and `export authors`.
- A new `profiles.jsonl` raw artifact so enrichment is rebuildable offline.

**How (files)**
- New raw artifact: `raw/openreview/<venue>/profiles.jsonl` (one JSON per unique handle).
- `adapters/openreview.py`:
  - New `fetch_profiles(handles: list[str]) -> dict[str, RawProfile]` using
    `openreview.tools.get_profiles` (batched). Best-effort: skip 404s.
  - `normalize(raw, ref, *, aliases, profiles=None)` — add an optional `profiles` map; when
    present, set each `NormalizedAuthor.affiliation/country/profile_url/homepage/gscholar/
    dblp/expertise` from the handle's profile (current institution = most-recent `history`
    entry; prefer profile's explicit `country`; canonicalize org name/domain through
    `normalize/orgs.py`). Set `data_quality = resolved|low|unresolved` accordingly.
- `services/ingest.py`: two-pass — after `fetch_notes`, collect unique `~handles`, call
  `fetch_profiles`, **snapshot to `profiles.jsonl`**, then `normalize(..., profiles=map)`.
  Change `link_affiliation(..., confidence="low")` (line 136) to use real confidence
  (profile-derived = `high`).
- `services/index.py` `rebuild()`: load `profiles.jsonl` if present and pass the map into
  `normalize` (so rebuild reproduces affiliations with no network). Update `_snapshots` to
  tolerate the optional file.
- `models.py`: `NormalizedAuthor` already has `affiliation/country/profile_url`; add
  `homepage/gscholar/dblp/expertise`.
- `db/schema.sql` + migration → v3: add author columns; ensure `authors_fts.affiliations` +
  `authors_fts.topics` get populated (so author search by org/expertise works).
- `db/repositories/{authors,orgs,stats}.py`: write/read new fields. The `stats` org/country
  queries should already work once `orgs`/`author_affiliations` are populated — verify.
- New command (recommended): **`confos enrich profiles --venue <slug>`** so existing stores
  upgrade *without* a full re-ingest (fetch profiles → snapshot → rebuild). See Open Decisions.

**Network cost:** ~20k unique profiles for neurips-2025, batched, **first time only**, cached
in `profiles.jsonl`. Rough order: tens of minutes. Resumable/idempotent.

**Caveats:** coverage is best-effort — some handles return "Profile Not Found" (seen in
testing); some profiles lack institution history. Report it honestly via `--explain`
(`data_quality`). **Framing (README):** "find where they work now + their links," **not**
email-harvesting (emails are usually redacted for other users; there's no LinkedIn field).

**Acceptance**
- `stats orgs --explain` → non-trivial coverage (not `0/5540`); `orgs top` + `viz orgs` render.
- `stats countries` returns a distribution.
- `authors show <id> --json` includes affiliation + homepage/gscholar/dblp.
- `index rebuild` reproduces all of the above from raw with **no network**.

**Tests:** vcr cassette for `fetch_profiles`; unit for profile→NormalizedAuthor mapping
(incl. missing-history + 404 handling); rebuild-from-`profiles.jsonl` test.

---

## Phase 2 — Review scores & quality intelligence (the flagship)

**Why:** This is the line between "keyword search over abstracts" and "quality intelligence
the website doesn't give you." And it's cheap: the reviews already arrive in the
`details="replies"` payload confos fetches under `--include-decisions`.

**Deliverables**
- Per-paper review signals: `review_count`, `rating_mean`, `rating_std` (= controversy),
  `confidence_mean`, `decision`, and (optionally) per-sub-score means
  (soundness/presentation/contribution).
- A `reviews` table (raw per-review rows) for provenance + aggregate columns on `papers` for
  fast ranking.
- New commands: **`papers top`** (highest-rated on a topic/venue) and **`papers controversial`**
  (high rating variance).
- **Quality-weighting** wired into `papers search`, `authors find`, `trends`, `stats`,
  `export` (opt-in flag, e.g. `--by rating`).

**How (files)**
- Fetch: ensure ingest pulls replies (today gated by `--include-decisions`). **Decide** whether
  to reuse that flag or add `--with-reviews` (Open Decisions). `_note_to_raw` already persists
  `details` → reviews land in `submissions.jsonl`.
- `adapters/openreview.py`: new `_parse_reviews(details) -> list[NormalizedReview]` reading
  `details.replies` where invitation endswith `Official_Review`. **Per-venue rating parser**
  (the only real work): ratings come as `8`, `"8: accept"`, or `"8: Weak Accept"` depending on
  venue/year → a small registry keyed by venue family that extracts the leading int.
- `models.py`: new `NormalizedReview` (rating, confidence, sub-scores, raw); add
  `reviews: list[NormalizedReview]` + aggregate fields to `NormalizedPaper`.
- `db/schema.sql` + migration → v4: `reviews` table (`paper_id`, `reviewer_key`, `rating`,
  `confidence`, sub-scores, `raw_json`) + aggregate columns on `papers`. Add an FTS or index as
  needed for `papers top`.
- `services/`: new `services/reviews.py` (aggregation); extend `services/ranking.py` for
  quality-weighting; `upsert_normalized_paper` writes reviews + aggregates.
- `commands/papers.py`: `top`, `controversial`; add `--by rating|citations|relevance` where it
  makes sense.
- Docs: SCHEMAS.md (new shapes), CLI_CONTRACT.md (new commands), RANKING.md (quality weighting).

**Upgrade path:** one-time re-ingest with reviews (`confos ingest neurips-2025 --force
--with-reviews`) to put replies in raw → thereafter `index rebuild` is offline.

**Caveats:** rating scales differ per venue/year → parser registry is essential; default to
"unknown/skip" rather than mis-scaling. Some rejected papers have no public reviews → reviews
are best-effort; report coverage. Reviewer identities are anonymized (keep `reviewer_key`
opaque).

**Acceptance**
- `papers top --topic "agent memory" --venue neurips-2025` returns rating-sorted papers with
  `rating_mean`/`review_count`.
- `papers controversial` returns high-variance papers.
- `stats overview` (or a new `stats reviews`) shows the score distribution.
- Provenance: every score traceable to the reviews in raw.

**Tests:** rating-parser unit tests across formats (`8`, `"8: accept"`); aggregation math;
vcr cassette with a reviewed paper; `papers top` ordering.

---

## Phase 3 — Semantic search + topic clusters + landscape map  *(DEFERRED)*

Not in this cycle (per decision 2026-06-02 — biggest infra lift). Captured so we don't lose it:
embed abstracts once with a small **local** model (keep offline/free) to unlock semantic
search, better "related papers," HDBSCAN topic clusters with cheap TF-IDF labels, and a
shareable static-HTML landscape map for `viz`. Highest payoff-per-investment **after** the data
foundation (0–2) exists. Revisit once Phases 0–2 land. (Note: it would also subsume the
"LLM/LLMs/large language model" topic-fragmentation issue seen in `stats topics`.)

---

## Phase 4 — OpenAlex citation enrichment (realized impact)

**Why:** Adds "did it matter," not just "was it rated well." Combined with Phase 2:
"highly-rated **and** highly-cited" — and the misses. The adapter Protocol already names
`openalex` as a future seam.

**Deliverables**
- `papers.citation_count` (+ `citations_source`, `citations_asof`).
- Impact ranking: `papers top --by citations`; citation-weighted options where sensible.

**How (files)**
- New `adapters/openalex.py`: query `https://api.openalex.org/works` (free, **no key**, no hard
  rate limit) — match by normalized title (+ year guard) → `cited_by_count`. Optional DOI match
  if present in `_bibtex`.
- New raw artifact `citations.jsonl` + `services/citations.py` (or fold into an `enrich`
  command: **`confos enrich citations --venue <slug>`**).
- `models.py` + `db/schema.sql` + migration → v5: citation columns; `ranking.py` option.
- Docs: PRODUCT.md (impact), SCHEMAS.md, CLI_CONTRACT.md.

**Caveats:** title-match has false positives → require close title match + year proximity;
log unmatched count (no silent caps). **Recent papers have ~0 citations** → this serves
"survey a field," not "prep for the upcoming conference." Lower priority than 0–2 for the
attendee persona.

**Acceptance:** matched papers carry `citation_count` with provenance + an honest match-rate;
`papers top --by citations` ranks correctly; unmatched papers reported.

**Tests:** vcr cassette for OpenAlex; title-normalization + match-threshold units; no-key path.

---

## Phase 5 — `confos brief` (the one-command landscape + launch demo)

**Why:** Composes everything into the entry point for the three personas PRODUCT.md names
(casual reader, attendee, agent). The `--json` form is a superset of today's `export context`
— the ideal agent primitive; the human form is the open-source launch demo. Cheap once 1–2
exist.

**Deliverables**
- **`confos brief --venue <slug>`** (and `--topic <t>`): top-rated papers (P2), hot + emerging
  topics (stats + trends), rising orgs (P1), people-to-know with links (authors find + P1),
  thin/underexplored areas. Human render (rich) + `--json`.

**How (files)**
- New `services/brief.py` composing existing services (search/stats/trends/authors/ranking +
  reviews). New `commands/brief.py`. `--json` schema = superset of `export context`
  (`output/json.py`, SCHEMAS.md). Human layout modeled on a viz/stats dashboard.

**Depends on:** Phase 1 (people/orgs) + Phase 2 (top-rated). Phase 4 optional (impact).

**Acceptance:** one command yields a complete, cited landscape; `--json` validates against its
schema and round-trips for an agent; no fabricated numbers.

**Tests:** composition unit test on a small fixture store; JSON schema validation.

---

## 6. Sequencing & dependencies

```
M0 migrations ─┬─► Phase 0 (free, no network)        ── ship first, instant win
               ├─► Phase 1 (profiles) ──┐
               ├─► Phase 2 (reviews) ────┤
               │                         ├─► Phase 5 (brief)   [needs 1 + 2]
               └─► Phase 4 (citations) ──┘ (optional into 5)
```
- **M0 + Phase 0** first — unblocks everything and ships value with no re-download.
- **Phase 1** and **Phase 2** are independent of each other; do 1 first (fixes the empty
  commands and is the bigger credibility win), then 2 (the flagship feature).
- **Phase 4** any time after M0; lower priority.
- **Phase 5** last — it's glue over 1/2(/4).

---

## 7. Open decisions (resolve while implementing; defaults chosen so we can proceed)

1. **Reviews flag.** Reuse `--include-decisions` (which already fetches replies) vs. add
   `--with-reviews`. *Default:* add `--with-reviews` as the clear name; keep
   `--include-decisions` as an alias that implies it.
2. **Profile/citation upgrade UX.** Force a re-ingest vs. a dedicated **`confos enrich
   {profiles,citations} --venue`** command. *Default:* add `enrich` — existing stores upgrade
   without re-downloading papers. (Cleaner, and matches "raw is truth.")
3. **Profile fetch default.** On-by-default during `ingest` vs. opt-in. *Default:* opt-in via
   `enrich`/a flag for now (keeps base ingest fast + offline-after); revisit making it default.
4. **`rejected` detection.** Group-content field (`rejected_venue_id`?) vs. `…/Rejected_Submission`
   suffix heuristic. *Default:* try the group field in `resolve_venue`; fall back to the suffix.
   **Verify the exact OpenReview group field name during Phase 0.**
5. **Review storage.** Raw rows + aggregates vs. aggregates only. *Default:* both (raw
   `reviews` table for provenance + aggregate columns for fast ranking).
6. **Rating parser scope.** *Default:* start with NeurIPS/ICLR/ICML 2024–2025 scales; registry
   keyed by venue family; unknown scales → skip with a logged count.

---

## 8. Definition of done (every phase)

- New/changed `--json` output is **additive** and documented in SCHEMAS.md + `confos schema`.
- `--explain` / data-quality reporting present for any newly-derived data.
- `index rebuild` reproduces the phase's data from raw with **no network** (once the raw
  artifact exists).
- Gate green: `ruff`, `mypy --strict`, `pytest`. New unit tests + a vcr cassette; a `live`
  test added to `scripts/live-test.sh`.
- PROGRESS.md updated (session log) and DECISIONS.md gets an ADR line for any non-obvious call.

---

## 9. First concrete steps for the implementation session

1. **M0:** add incremental-migration support to `db/migrate.py` (registry + ordered apply).
2. **Phase 0:** `PaperStatus += "rejected"`; populate `pdf_url`/`bibtex`/`supplementary_url` in
   the adapter; add columns + migration v2; surface in `papers show` / `export papers` /
   `stats overview`. Verify the `rejected` group-field name.
3. Run `confos index rebuild` on the existing `neurips-2025` store → confirm
   `accepted 5286 / rejected 254`, pdf+bibtex populated, **with no network**. ← the instant win.
4. Then Phase 1 (`enrich profiles` + `profiles.jsonl` + rebuild wiring).

---

*This plan is the canonical memory for this work. Keep it updated as phases land — tick
acceptance criteria, log decisions, and move "Open decisions" to "decided" inline.*
