# Contributing to confos

Thanks for your interest. confos is a small, deliberately-scoped CLI — the goal is a
sharp, well-tested tool for OpenReview conference data, not a kitchen sink. This guide is
how to set up, what the bar is, and the few conventions that keep `main` clean.

## Setup

confos uses [uv](https://docs.astral.sh/uv/). Python 3.12 is pinned via `.python-version`
(uv will fetch it for you).

```bash
git clone https://github.com/RRaphaell/confos
cd confos
uv sync            # create the venv + install runtime and dev deps
uv run confos --help
```

## The gate (run this before every push)

CI runs exactly these four steps, and they must all be green before anything merges:

```bash
uv run ruff check .          # lint
uv run ruff format --check . # formatting
uv run mypy                  # types (strict)
uv run pytest -q             # tests
```

`uv run ruff format .` fixes formatting; `uv run ruff check . --fix` fixes the
auto-fixable lints.

## Tests

- **Unit** (`tests/unit/`) — pure logic that's easy to get wrong: normalization
  (orgs/countries/topics), id/url derivation, ranking, FTS query building, the JSON
  envelope, config precedence.
- **Integration** (`tests/integration/`) — drive the real `main()` in-process via the
  `run_cli` fixture against a temp `$CONFOS_HOME`; assert the JSON shape **and** the exit
  code.
- **No live network in CI.** Tests use a synthetic `FakeAdapter` (`tests/synthetic.py`)
  and one recorded vcrpy cassette. The opt-in `scripts/live-test.sh` is the only thing
  that hits the real API.
- Every command has at least one acceptance test proving its definition-of-done — notably
  the `authors find` fixed-order ranking fixture (`test_authors_find_ranking.py`), which
  pins the ranking contract (RANKING §2/§3). If you touch ranking, expect to update it
  deliberately.

We test what can break; there's no coverage-percentage gate.

## Architecture in one paragraph

Layered, and the layering is enforced by review (see
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) §4): **commands** parse flags and render —
no business logic, no SQL. **services** hold the logic and orchestrate. **repositories**
(`db/repositories/`) own *all* SQL. **adapters** talk to external sources and never touch
the DB. `normalize/` is pure functions. Raw JSONL snapshots are the source of truth; the
SQLite index is fully derivable (`confos index rebuild` re-derives it offline). Keep new
code in the right layer.

Output discipline (CLI_CONTRACT): stdout is data only; progress/warnings go to stderr.
Under `--json`, stdout is a single stable envelope and nothing else. Every command's
`--help` carries 2–3 examples (a test enforces this).

## Conventions

- **Conventional commits**: `feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`.
  Commit at meaningful checkpoints rather than one giant blob.
- **Do not add a `Co-Authored-By` / AI-attribution trailer** to commits. (Project rule.)
- **Never commit secrets.** confos needs none — OpenReview reads are anonymous. Optional
  credentials are read from the environment only, never from flags, never logged.
- **Log non-obvious decisions** in [docs/DECISIONS.md](docs/DECISIONS.md) (lightweight
  ADR: what / why / alternatives) so they aren't re-litigated.
- **Determinism**: list queries need an explicit `ORDER BY` with a unique tiebreak, so
  `--json` and tests are reproducible.

## Scope

v1 is OpenReview, done well (see [docs/PRODUCT.md](docs/PRODUCT.md) §8). Adapters for
other sources, semantic search, an LLM `ask`, and an MCP server are designed-for-later —
the seams exist, the code doesn't. PRs that add a whole new source or a server are likely
out of scope for now; open an issue first.

## Pull requests

1. Branch from `main`.
2. Make the change; keep it in the right layer; add/adjust tests.
3. Update docs if behaviour or output changed (and `CHANGELOG.md` under `[Unreleased]`).
4. Run the gate locally — all four steps green.
5. Open the PR with a clear description of what and why.

Questions or proposals: open an [issue](https://github.com/RRaphaell/confos/issues).
