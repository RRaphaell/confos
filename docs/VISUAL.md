# confos — Visual Enrichment (Human Output)

**Status:** proposed (design spec — not yet implemented) · **Last updated:** 2026-06-02

How the **human** output path should evolve from "correct and plain" to "correct and
delightful," without touching the machine contract. This doc is the implementation plan
for five visual enhancements plus the shared infrastructure they sit on. It applies only
to the default (human) mode; `--json` and `--plain` are out of scope by construction
(see [CLI_CONTRACT.md](CLI_CONTRACT.md) §4).

The lineage is deliberate: confos already borrowed `ft`'s *storage* shape
([REFERENCES.md](REFERENCES.md)). This borrows its *face* — the interactive-terminal
polish — and confines it to the one surface where it belongs.

---

## 0. The one rule (read this before writing any code)

confos is **agent-first and heavily piped**. A large fraction of real invocations are
`--json` or redirected to a file, where visual richness is noise at best and a contract
violation at worst. Every change in this doc must obey these invariants:

1. **Human path only.** All richness lives *behind* the existing `app_ctx.is_json` /
   `app_ctx.is_plain` guards. JSON and plain output must be **byte-identical** before and
   after. The seams already exist in every command — `commands/*.py` already branches on
   `is_json` → `is_plain` → human render. Add to the human branch, nowhere else.
2. **Color is already resolved — don't second-guess it.** `console.should_use_color()`
   honors `--no-color`, `NO_COLOR`, `TERM=dumb`, and non-TTY. The resolved flag is
   `app_ctx.use_color`, and the consoles are built once in `build_consoles()` (and rebuilt
   there on a late `--no-color`). Inject anything color-related at that single touchpoint.
3. **Unicode ≠ color.** A no-color TTY still renders block glyphs fine; a `TERM=dumb` or
   non-UTF-8 stream does not. Resolve a *separate* `use_unicode` capability (see §2.2) and
   degrade glyphs (sparklines, bars, box borders) to ASCII when it's false.
4. **Progress goes to stderr.** Per §4 of the contract, progress/spinners render on the
   `err` console only, so stdout stays clean and parseable even mid-ingest.
5. **Helpers stay pure and testable.** Follow the existing pattern: small functions in
   `output/` that take a `Console` (or return a string), unit-tested in
   `tests/unit/test_render_helpers.py`. No business logic leaks into the render layer.
6. **No new runtime dependency.** Everything here is `rich` (already pinned `>=13.7`) plus
   stdlib `difflib`/`contextlib`.

> Guardrail test (add it once, it protects all five): capture stdout for a representative
> command under `--json`, under `--no-color | pipe`, and under `--plain`, and assert the
> bytes are unchanged from a golden file and contain **zero** `\x1b` escape sequences.

---

## 1. Baseline — what already exists (do not rebuild)

| Capability | Where | Notes |
|---|---|---|
| Rich result tables | `commands/_render.py` (`render_papers`, `render_found_authors`, `render_authors`) | ellipsize, score column, why-relevant |
| Generic table helpers | `output/table.py` (`key_value_table`, `data_table`) | reused across commands |
| Terminal bar chart | `output/table.py` (`bar_chart`) | `█` bars scaled to max; powers `viz topics`/`viz orgs` |
| Co-authorship export | `output/graph.py` (`to_mermaid`, `to_html`) | `viz network --format mermaid|html` |
| Color resolution | `console.py` (`should_use_color`, `build_consoles`) | the single color touchpoint |
| 3 output modes | `console.py` (`OutputMode`, `is_json`, `is_plain`) | human / json / plain |
| Diagnostics styling | `console.py` (`info`/`warn`/`debug`/`trace`) | dim / yellow, all on stderr |

The work below **extends** these; it does not replace any of them.

---

## 2. Shared infrastructure (build once; all five depend on it)

### 2.1 A centralized Rich `Theme`

Today color is ad-hoc inline (`[red]error`, `[yellow]warning`, `[dim]…` scattered in
`console.py` and `viz.py`). Promote it to one `rich.theme.Theme` injected inside
`build_consoles()` so both the initial and the rebuilt-on-`--no-color` consoles carry it.
Proposed named styles (tune freely — that's the point of centralizing):

```
confos.success  = "green"        confos.muted   = "dim"
confos.warn     = "yellow"       confos.accent  = "bold cyan"
confos.error    = "bold red"     confos.count   = "bold"

status.oral      = "bold magenta"   status.accepted  = "green"
status.spotlight = "magenta"        status.active    = "yellow"   # under review
status.poster    = "cyan"           status.rejected  = "dim red"
                                    status.withdrawn = "dim"

dq.high = "green"   dq.med = "yellow"   dq.low = "red"     # data-quality badges
score.hi = "bold"   score.lo = "dim"                       # BM25 / relevance heat
```

Then markup like `[status.oral]oral[/]` resolves through the theme and collapses to plain
when `no_color` is set. Migrate the existing inline `[red]`/`[yellow]`/`[dim]` usages onto
these names as part of this step so there's one vocabulary.

### 2.2 Capability flags on `AppContext`

`use_color` already exists. Add two siblings, resolved once in the root callback alongside
color and stored on `AppContext`:

- `use_unicode: bool` — `False` if `TERM=dumb`, the stream encoding isn't UTF-8, or an
  opt-out is set (see §7); else `True`. Consulted by sparkline/bar/box renderers.
- `supports_hyperlinks: bool` — gate OSC-8 link decoration. A pragmatic heuristic:
  `app_ctx.out.is_terminal and use_unicode`. (Rich also degrades links on its own; this
  just avoids decorating output we know is headed somewhere dumb.)

### 2.3 New `output/` modules

- `output/progress.py` — a context-manager wrapper around `rich.progress.Progress` bound
  to the stderr console (§3.1).
- `output/charts.py` — pure string helpers: `sparkline(values, *, unicode=True) -> str`
  and `inline_bar(value, max_value, width, *, unicode=True) -> str` (§3.4).
- `output/states.py` — `empty_state(console, title, body, *, hints)` (a `rich.panel.Panel`)
  and `did_you_mean(query, candidates, *, n=1) -> list[str]` (stdlib `difflib`) (§3.5).

All three are unit-test targets in `tests/unit/test_render_helpers.py`.

---

## 3. The five enhancements

### 3.1 Ingest progress on stderr — **Priority 1**

**Why.** `ingest` is the only genuinely slow command (~4–5k papers, multi-minute network
pull). Today it emits dim one-liners via `on_progress=app_ctx.info`
(`commands/ingest.py:54`) and otherwise goes quiet — to a user it *looks hung*. This is the
biggest experiential gap and the cheapest contract-safe win (progress already belongs on
stderr).

**Target UX** (stderr; stdout stays empty until the final result/JSON):

```
  ⠹ Ingesting neurips-2025  ━━━━━━━━━━━━━━━╸━━━━━━━  3,847/4,901 · page 5/9 · 0:48
    added 3,120 · updated 727 · skipped 0
```

**Files.**
- New `output/progress.py`: a `@contextmanager` yielding a small handle with
  `.advance(seen, total)` and `.note(msg)`, built from `Progress(SpinnerColumn(),
  TextColumn(...), BarColumn(), MofNCompleteColumn(), TimeElapsedColumn(),
  console=err, transient=False)`.
- `services/ingest.py`: widen the progress seam. Keep `on_progress(message: str)` for
  notes (backward-compatible) and **add** an optional `on_advance(seen: int,
  total: int | None)` callback. The service already knows page/paper counts.
- `commands/ingest.py`: when `app_ctx.err.is_terminal and not app_ctx.quiet`, drive the
  Progress; otherwise pass the existing `app_ctx.info` note callback and no advance (today's
  behavior).

**Contract & fallback.** Renders on `err` only — stdout/JSON untouched. Falls back to dim
lines when non-TTY or `--quiet`. Under `--json` the final envelope is unchanged.

**Done when.** Live `confos ingest <venue>` shows a moving bar; `confos ingest <venue> --json`
produces the identical envelope as before; `... | cat` (non-TTY) shows plain note lines, no
spinner control codes.

### 3.2 Theme + semantic color in tables — **Priority 2**

**Why.** Color should encode *meaning* so results are scannable without reading. The two
highest-value encodings for confos data:
- **Acceptance status** in `render_papers` — orals/spotlights pop, rejected/withdrawn dim.
  When scanning "long-running agents" hits, the accepted work should be obvious at a glance.
- **Data-quality** in `stats` — the `coverage: N/M papers have signal` line and the
  `data_quality` table (`commands/stats.py`) are where a green/yellow/red badge earns its
  keep, because *honest stats* is the product's whole differentiator. Make the honesty
  visible.
- A subtle **score heat** (bold the top BM25 rows via `score.hi`, dim the tail) is a cheap
  third win in `render_papers`.

**Files.** `console.py` (§2.1 theme), then `commands/_render.py` and `commands/stats.py`
apply `[status.*]` / `[dq.*]` / `[score.*]` markup in the human branch only.

**Contract & fallback.** A themed console with `no_color=True` strips color automatically;
non-color/dumb terminals degrade for free. JSON unaffected (status/score are already plain
fields there).

**Done when.** `confos papers search …` color-codes status and bolds the top score;
`confos stats topics --explain` shows a colored data-quality badge; `NO_COLOR=1 confos …`
emits zero color escapes.

### 3.3 Clickable titles + a real `papers show` card — **Priority 3** (highest wow/LOC)

**Why.** confos is a *paper-discovery* tool, so links are close to a killer feature. Rich
emits **OSC-8 hyperlinks** (`[link=URL]text[/link]`) honored by iTerm2, WezTerm, kitty, and
the VS Code terminal, and degrades to plain text everywhere else.

- In `render_papers`, make each title a link to its OpenReview forum
  (`https://openreview.net/forum?id=<paper_id>` — `paper_id` is already in the row;
  see `papers_tsv`) and author names link to profiles where available. Search results
  become a clickable index instead of a copy-paste list.
- Give `papers show` a real **card**: a `rich.panel.Panel` with a key/value header
  (venue · status · score · authors), the abstract rendered via `rich.markdown.Markdown`,
  and a links footer. The Markdown instinct already exists — `services/export.py:112`
  renders context packs as Markdown.

**Target UX** (search):

```
  Search "long-running agents" · neurips-2025                          12 results
  #  title                                          authors   status   score
  1  τ-Bench: Benchmarking Long-Horizon Agents…     Yao +6    oral     18.4
  2  Memory-Augmented Agents for Multi-Day Tasks    Park +3   poster   12.1
  3  When Agents Run for Hours: A Stability Study   Li +4     reject    9.7
       (titles clickable · "oral" green · "reject" dim-red · top score bold)
```

**Files.** `commands/_render.py` (link titles in `render_papers`; new `render_paper_detail`
for `papers show`), `commands/papers.py` (call the detail renderer in the human branch).

**Contract & fallback.** Gate link decoration on `supports_hyperlinks` (§2.2); Rich strips
links when unsupported. JSON already carries the raw ids/urls — unchanged.

**Done when.** In a modern terminal, titles are clickable; in `cat`/`--plain`/`--json` the
output is plain text/ids exactly as today.

### 3.4 Sparklines for `trends`, inline bars for `stats` — **Priority 4**

**Why.** `trends` is the "what's rising" story and today it's a table plus a one-line delta
(`commands/trends.py:_render`). A topic moving across years is *intrinsically a shape* —
give it one. Add a tiny `sparkline()` (`▁▂▃▄▅▆▇█`, 8 levels) and a colored ▲/▼ delta.

**Target UX:**

```
  Trend: "evals" across NeurIPS 2023 → 2025
    2023   3.1%  ▇▇▇            141 / 4,533
    2024   4.6%  ▇▇▇▇▇▇▇        237 / 5,102
    2025   5.5%  ▇▇▇▇▇▇▇▇▇▇     291 / 4,901
    share ▁▅█   ▲ +2.4pp        matched ▲ +150
```

**Files.** `output/charts.py` (`sparkline`, `inline_bar` — pure, ASCII-degradable),
`commands/trends.py:_render` (per-year `inline_bar` + a series `sparkline` + colored delta).

**Scope decision (see §7):** keep `stats` *textual* (numbers, honest coverage) and keep the
*pictures* in `viz` — that's the existing stats-vs-viz boundary. `trends` is the exception
that gets a sparkline, because a trend without its shape is just a table.

**Contract & fallback.** Glyphs degrade to an ASCII ramp when `use_unicode` is false; delta
arrows are plain `+`/`-` without color. JSON series unchanged.

**Done when.** `confos trends topic "evals" --venues …` shows per-year bars + a sparkline +
a green/red delta; `TERM=dumb` shows the ASCII ramp; `--json` series is identical.

### 3.5 Guided empty / error / did-you-mean states — **Priority 5**

**Why.** confos's whole flow is **init → ingest → query**, so the *empty state is the most
common first experience* — and right now it's a bare `"No data yet."` (`commands/stats.py:24`)
or `"No data to chart yet."` (`commands/viz.py:29`). Those are dead ends. Turn them into
guidance that teaches the next command, and add did-you-mean for venue typos (you already
have the alias map in `aliases.py`).

**Target UX:**

```
  ╭─ Nothing to show yet ────────────────────────────────────╮
  │ No papers ingested for 'neurips-2025'.                    │
  │   Pull it:        confos ingest neurips-2025              │
  │   Unsure of slug? confos venues search "neurips"          │
  ╰──────────────────────────────────────────────────────────╯
```
```
  error: unknown venue 'neurips2025'
  hint: did you mean 'neurips-2025'?   (confos venues aliases)
```

**Files.** `output/states.py` (`empty_state` panel, `did_you_mean` via `difflib`), called
from the human branch of `commands/stats.py`, `commands/viz.py`, `commands/papers.py`;
`did_you_mean` wired into the `UsageError(..., hint=…)` path for unknown venues (the `hint`
field already exists in `errors.py`).

**Contract & fallback.** Strictly human-mode — JSON already returns structured empties
(`data: []`) and typed errors. Panel borders degrade to ASCII under `use_unicode=False`.

**Done when.** A query against an un-ingested venue shows the guided panel; a venue typo
suggests the closest alias; `--json` empties/errors are byte-identical to today.

---

## 4. Bonus — a real terminal co-authorship graph (closes a contract gap)

`viz network --format terminal` is the **default** format, but it currently renders a flat
"author / co-author-count" table (`commands/viz.py:109-122`), not a graph — while the
contract advertises it as a graph view. Render it as a `rich.tree.Tree` ego-network
(top-degree author → co-authors → their co-authors, depth-bounded) so `--format terminal`
becomes an actual terminal *graph*. This both improves the UX and closes a doc-vs-impl gap.
Folds naturally into the §2/§3 infra (theme + unicode capability). Lower priority than the
five, but cheap once the rest lands.

---

## 5. Phasing & rough effort

| Phase | Contents | Why this order | Effort |
|---|---|---|---|
| **P1** | §2.1 theme + §2.2 capability flags | substrate for everything else | S |
| **P2** | §3.1 ingest progress | fixes the only "looks broken" command | S–M |
| **P3** | §3.2 semantic color | first user-visible payoff on the substrate | S |
| **P4** | §3.3 links + `papers show` card | highest wow per line; serves the hot path | M |
| **P5** | §3.4 trends sparkline + §3.5 guided states | polish; both small once charts/states exist | M |
| **P6** | §4 terminal network graph | closes the contract gap | S–M |

Each phase is independently shippable and leaves `main` green.

## 6. Definition of done (applies to every phase)

- [ ] `confos <cmd> --json` output is **byte-identical** to pre-change (golden test).
- [ ] `--plain` output unchanged.
- [ ] `NO_COLOR=1` / `--no-color` / piped stdout → **zero** `\x1b` escapes.
- [ ] `TERM=dumb` → ASCII fallback for all glyphs/borders; no block characters.
- [ ] Progress/spinners appear on **stderr** only, and only on a TTY without `--quiet`.
- [ ] New pure helpers covered in `tests/unit/test_render_helpers.py`.
- [ ] `ruff` clean + `mypy --strict` clean (the gate; see [CONTRIBUTING.md](CONTRIBUTING.md)).
- [ ] No new runtime dependency (Rich + stdlib only).

## 7. Open decisions (resolve before/while implementing)

1. **`use_unicode` opt-out.** Infer only (UTF-8 + `TERM != dumb`), or also add a `--ascii`
   flag and `CONFOS_ASCII` env? *Recommendation:* infer + an env var; defer a flag until
   there's demand (keep the flag surface small, per the rubric).
2. **Hyperlinks on by default?** *Recommendation:* yes — Rich degrades gracefully; add
   `--no-links` later only if it proves noisy.
3. **Sparklines in `stats`?** *Recommendation:* no — keep `stats` textual and put charts in
   `viz`; give `trends` the sparkline as the one exception (trend = shape). Preserves the
   stats-vs-viz boundary.
4. **Score heat aggressiveness.** *Recommendation:* subtle — bold the top row(s), dim the
   tail; avoid a full rainbow that fights the status colors.

---

## Related

- [CLI_CONTRACT.md](CLI_CONTRACT.md) — §3 modes, §4 output contract (the rule this doc obeys)
- [REFERENCES.md](REFERENCES.md) — `ft`/`birdclaw` (storage shape borrowed; visual polish borrowed here)
- [ARCHITECTURE.md](ARCHITECTURE.md) — where `output/` and `commands/` sit in the layering
- [CONTRIBUTING.md](CONTRIBUTING.md) — the gate (ruff + mypy strict + pytest) every phase must pass
