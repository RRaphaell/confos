# confos — Build Plan & Working Manual

**Status:** canonical · **Last updated:** 2026-05-31 · **Audience:** the agent building this.

This is the operating manual for constructing confos. It assumes context will be lost
and rebuilt between sessions — so it must be self-sufficient. Read this, then
[ARCHITECTURE.md](ARCHITECTURE.md) + [CLI_CONTRACT.md](CLI_CONTRACT.md), and you can
build the whole project without re-deriving decisions.

---

## 0. Prime directive

**Do not declare the project "done" until it is finalized, validated, and tested** —
the full v1 surface in [PRODUCT.md](PRODUCT.md) §8, with clean code, passing tests, and
subagent-validated quality. No rushing. No fake-done. Define "done" by the
definition-of-done checklists below, not by elapsed effort.

**Two standards held in tension (both matter):**
- **Production-grade, modern, open-source quality** — this repo is public-facing. Clean
  structure, typed, tested, CI-green, good docs, idiomatic 2026 Python.
- **Not over-engineered** — public data, anonymous reads, a focused CLI. No security
  ceremony, no speculative abstraction, no config knobs nobody needs. Every line earns
  its place. When the two pull against each other, prefer the *simpler* thing that still
  meets the production bar. (See §3 "Simplicity is a hard rule.")

## 1. How I work (process)

A repeating loop per phase:

```
  PLAN ─▶ BUILD ─▶ SELF-CHECK ─▶ SUBAGENT VALIDATE ─▶ FIX ─▶ COMMIT+PUSH ─▶ next phase
   ▲                                                                  │
   └──────────────────  (re-plan if validation fails)  ◀─────────────┘
```

- **Track progress** with a live task list (one item per phase deliverable); mark
  in-progress / done as I go. Keep [PROGRESS.md](PROGRESS.md) updated each session: what's
  done, what's next, what changed.
- **Research before guessing.** When a piece is unfamiliar (an openreview-py call, a typer
  pattern, an FTS5 detail, how `ft`/`gogcli` solved something), look it up — read the
  docs/source/reference repo — *before* writing code. Don't invent an API. Then **write
  down what I learned** so it isn't re-researched: short notes in `docs/research/` (one
  file per topic, e.g. `docs/research/typer-patterns.md`) and a one-line pointer from
  PROGRESS.md. Reference repos to mine: `ft`, `birdclaw`, `gogcli`, the `create-cli`
  rubric (see [REFERENCES.md](REFERENCES.md)).
- **Document decisions & assumptions as they happen.** Every non-obvious choice or
  assumption goes in [DECISIONS.md](DECISIONS.md) (lightweight ADR: what / why / context /
  alternatives). This is for both of us — so future-me doesn't re-litigate, and Raphael
  can see why things are the way they are. If I have to assume something about the data or
  the user, log it as an assumption with how to verify it.
- **Commit at every meaningful checkpoint** and push to the private GitHub repo so
  progress is visible. Conventional-commit style (`feat:`, `fix:`, `test:`, `docs:`,
  `chore:`). **Never add a `Co-Authored-By`/AI-attribution trailer** (Raphael's hard rule
  — the harness adds it by default; omit it). Never commit secrets.
- **Checkpoint discipline:** end each phase only when its definition-of-done is met and
  the subagent pass is clean (or findings are triaged and fixed).

### Working docs I keep current (the paper trail)
| File | Purpose | Updated |
|---|---|---|
| [PROGRESS.md](PROGRESS.md) | What's done / in-progress / next; pointers to notes | every session |
| [DECISIONS.md](DECISIONS.md) | Decisions + assumptions (lightweight ADR) | whenever a choice is made |
| `docs/research/*.md` | Insights/examples gathered while building (one file per topic) | when I research something |
| CHANGELOG.md | User-facing change log | per release/phase |

## 2. Subagent validation strategy (counter my own bias)

I am biased toward my own design and "looks good." So at each phase I spawn independent
subagents and act on their findings before moving on:

| Subagent | Mandate | Runs when |
|---|---|---|
| **code-reviewer** | Read the diff. Find bugs, edge cases, unclear code, dead code, missing types/tests, deviations from ARCHITECTURE/CLI_CONTRACT. | every build phase |
| **fresh-user** | Given ONLY the README + `--help` output (not the source), try to *use* the CLI for a real task. Report confusion, missing affordances, bad errors. | after any user-facing command lands |
| **architecture-critic** | Pressure-test design choices against the spec; flag drift back toward the killed "generic browser." | design checkpoints + before v1 sign-off |
| **agent-consumer** | Drive the CLI the way an LLM agent would (JSON only, no prompts); verify the contract + provenance hold. | after JSON output stabilizes |

Rule: a phase is not "done" until its subagent findings are either fixed or explicitly
deferred with a logged reason. Don't mark green on my own say-so.

## 3. Coding standards (modern, clean — and deliberately NOT over-built)

**Simplicity is a hard rule.** confos reads *public* conference data with *anonymous*
requests. It is a focused CLI, not an enterprise platform. Agents (me included) have a
strong bias to over-engineer — add abstraction layers, security ceremony, config knobs,
and "just in case" code nobody asked for. Don't. Every line must earn its place. When in
doubt, write the simpler version.

- **Python 3.12**, full type hints, **mypy** clean. Plain functions over clever classes.
- **ruff** for lint + format.
- **pydantic v2** at real boundaries (adapter payloads, JSON output) — not on every dict.
- Small, single-responsibility functions; the layering in ARCHITECTURE §4 is enforced
  (no network in repositories, no SQL in commands, no business logic in commands). That
  layering is the *only* structural ceremony — it exists to keep code testable and is not
  an invitation to add more layers.
- **Errors:** a small set of typed exceptions → exit codes (CLI_CONTRACT §5); full stack
  trace only at higher `--verbose` (`-vv`).
- **No hidden I/O:** read commands never touch the network; only `ingest` does.
- **Determinism:** explicit `ORDER BY` with a unique tiebreak on list queries, so `--json`
  and tests are reproducible (pairs with RANKING §2). This is clean code, not complexity.
- **Secrets:** none are needed (anonymous reads). If optional OpenReview creds are used,
  read from env only, never via flags, never logged or committed. That's the whole
  "security" story — no policy doc, no auditing pipeline, no SBOM. The only output-safety
  rule is `html.escape` on free-text in HTML graphs (ordinary correctness).

**What we are explicitly NOT doing** (cut as over-engineering): no SECURITY.md, no
dependency-audit/SBOM/Dependabot pipeline, no `--wrap-untrusted` fencing, no plugin
system, no coverage-percentage gate, no premature abstraction for sources beyond the one
documented adapter Protocol. Add any of these only if a concrete need actually appears.

## 4. Testing & validation

Test what can actually break; don't chase a coverage number.
- **Unit:** the logic that's easy to get wrong — normalization (orgs/countries/topics),
  id/url derivation, ranking (RANKING §2/§3), FTS query building, JSON envelope, config
  precedence. Pure functions, fast.
- **Integration:** temp `$CONFOS_HOME`, run migrations, ingest from a **recorded fixture**
  venue, run search/find/stats/trends/export end-to-end, assert JSON shape + exit codes.
- **Fixtures:** record one small venue once with **vcrpy**; replay in tests. **No live API
  in default CI.** An opt-in `scripts/live-test.sh` hits the real API.
- **Acceptance per command:** each command has at least one test proving its
  definition-of-done (incl. the `authors find` fixed-order ranking fixture).
- CI (GitHub Actions): ruff + mypy + pytest on push. Green before any phase is "done."
  Keep CI to those three steps — no audit/SBOM/coverage-gate jobs.

## 5. Phased roadmap (each phase ships a working, tested slice)

> Full v1 = all phases. Order gives a usable tool at every step and never a giant
> unshipped spec. Each phase ends with: tests green, subagent pass clean, committed+pushed.

### Phase 0 — Foundation  *(repo skeleton)*
Scaffold: `pyproject.toml` (uv), `.python-version`, `ruff`/`mypy`/`pytest` config,
`src/confos/` package, `cli.py` with typer app, `console.py` (stdout/stderr discipline),
`config.py`+`paths.py` (precedence + `~/.confos`), `errors.py` (exit codes), `output/`
(json envelope + table + plain), `db/` (connection, `schema.sql`, `migrate.py`),
`commands/` stubs, CI workflow, `.agents/skills/confos/SKILL.md` stub.
**DoD:** `confos --help`, `confos --version`, `confos init`, `confos doctor` work (doctor
checks env/DB/FTS5 only at this phase — network/openreview-py checks are added in Phase 1
when the adapter exists); CI green; pushed.

### Phase 1 — Ingest (OpenReview)
`adapters/openreview.py` (resolve venue, `get_all_notes`, paginate), `services/ingest.py`
(raw JSONL snapshot → normalize → SQLite upsert → `ingest_runs` watermark),
`normalize/` v1 (topics from keywords; orgs/countries best-effort), `venues` command +
built-in alias map, `confos ingest <venue>` (+ `--dry-run`, `--force`).
**DoD:** ingest a small fixture venue into SQLite + raw JSONL; incremental re-sync works;
provenance stamped; tests green (recorded fixture); pushed.

### Phase 2 — Search & explore
FTS5 schema + `papers_fts`; `services/search.py`; `papers search/show/related`,
`authors search/show/papers`, `orgs top/papers`. Stable `--json` envelope + tables.
**DoD:** search returns ranked, cited results offline (fast — target <300ms on a cached
venue, measured in the opt-in bench script, not asserted in gating CI); `--json` matches
SCHEMAS.md; fresh-user + agent-consumer subagents pass; pushed.

### Phase 3 — People discovery & stats
`authors find --topic` (the differentiator: rank people by topic with explanation),
`coauthors`; `stats overview/topics/orgs/countries` with `data_quality` reporting +
`--explain`; org/country normalization + user-editable alias files.
**DoD:** people ranking is explainable and provenance-backed; stats never fake clean
numbers; architecture-critic confirms it's not "a worse OpenReview site"; pushed.

### Phase 4 — Trends & visualization
`trends topic` + `trends compare`; `viz topics/orgs` (rich charts) + `viz network`
(networkx → terminal / mermaid / html).
**DoD:** trends produce correct deltas on fixtures; viz renders terminal + exports valid
mermaid/html; tests green; pushed.

### Phase 5 — Export & agent surface
`export context` (JSON + markdown context packs), `export papers/authors` (csv/jsonl);
finalize `.agents/skills/confos/SKILL.md` + `AGENTS.md`; `confos schema`.
**DoD:** context pack is self-contained + fully cited; agent-consumer subagent completes
a real task (e.g. "top 20 papers + 10 people on topic X, cited") using only confos; pushed.

### Phase 6 — Hardening & release polish
README polish + asciinema/gif demo; full help text per CLI_CONTRACT §10; error-path
tests; `uv tool install confos` works from a clean machine; final architecture-critic +
code-reviewer sweep; tag `v0.1.0`.
**DoD:** clean-checkout install + quickstart works; all subagent passes clean; v1 surface
(PRODUCT §8) complete, validated, tested. **Only now is it "done."**

### Designed-for-later (NOT v1)
AIE/PMLR/OpenAlex adapters, semantic search, LLM `ask`, MCP server. Seams exist; code doesn't.

## 6. Git & GitHub workflow
- Repo: private `RRaphaell/confos`. `main` is always green.
- Commit per checkpoint, push after each phase (and within phases at stable points).
- Conventional-commit messages; each phase's final commit summarizes the DoD met.
- Commit `uv.lock` for reproducible installs. `.gitignore` excludes `~/.confos`
  artifacts, `.venv`, caches, `__pycache__`, `*.db`, `.env`.

## 7. Definition of done (whole project)
- [ ] All v1 commands (PRODUCT §8) implemented per CLI_CONTRACT.
- [ ] ruff + mypy(strict) + pytest green in CI; integration tests on recorded fixtures.
- [ ] Every command: stable `--json`, provenance, correct exit codes, helpful `--help`.
- [ ] Subagent passes (code-reviewer, fresh-user, architecture-critic, agent-consumer) clean.
- [ ] `uv tool install confos` works from a clean machine; README quickstart reproduces.
- [ ] `.agents/skills/confos/SKILL.md` + `AGENTS.md` complete and accurate.
- [ ] Tagged `v0.1.0`, pushed to private GitHub.
