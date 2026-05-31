# confos — References & Lessons

**Status:** canonical · **Last updated:** 2026-05-31

What we studied and the concrete decisions each reference drove. We take the *shape* of
the good agent-CLIs, not their language.

---

## `create-cli` — steipete/agent-scripts (the CLI rubric)

Source: `github.com/steipete/agent-scripts/blob/main/skills/create-cli/SKILL.md`

The checklist we hold the CLI to (→ [CLI_CONTRACT.md](CLI_CONTRACT.md)):
- Structure `command [global flags] <subcommand> [args]`; human-first then script-safe.
- Data → stdout; diagnostics → stderr. `--json` machine output; `--plain` stable lines.
- `--quiet` / `--verbose`; `--no-input`; `--dry-run`; `--force`/confirm for destructive.
- Prompts only when stdin is a TTY. Respect `NO_COLOR` / `TERM=dumb`; offer `--no-color`.
- Config precedence: flags > env > project > user > system.
- Exit codes 0 / 1 / 2 (we extend with 3/4/5 for config/network/partial).
- Never accept secrets via flags. 5–10 example invocations incl. piped/scripting.

## `gogcli` — openclaw/gogcli (the serious agent-CLI shape)

Source: `github.com/openclaw/gogcli` · Go, MIT, "Google Workspace in your terminal …
built for terminals, shell scripts, CI, and coding agents."

What we copy (shape, not language):
- **Repo layout:** `cmd/` (commands) + `internal/` (core) + `docs/` + `.agents/skills/`
  + `testdata/`. We mirror as `commands/` + the rest of `src/confos/` + `docs/` +
  `.agents/skills/confos/` + `tests/fixtures/`.
- **Hierarchical subcommands:** `gog gmail search` → `confos papers search`.
- **Unified flags** across every command: `--json`, `--plain`, `--dry-run`, `--no-input`,
  `--force` — we adopt the same global set.
- **Agent safety:** gogcli ships allowlist/denylist + `--wrap-untrusted` for LLM-safe
  free-text. We adopt the safety-class model and (later) a wrap-untrusted option for
  abstracts/free-text fed to agents.
- **`AGENTS.md`** at the root documenting agent workflows — we ship one.
- **XDG-style dirs** (`*_CONFIG_DIR`, `*_DATA_DIR`, …) — we use `CONFOS_HOME` + a clean
  `~/.confos` layout.
- **Tests:** integration tests gated from default CI; opt-in live smoke script.

What we do differently: confos is **data-/analysis-heavy with a durable local index**
(SQLite+FTS5 + raw snapshots). gogcli is action-oriented and stateless-ish (keyring
only, no SQLite). So we add the `ft`/`birdclaw` storage pattern on top of the gogcli shape.

## `ft` (fieldtheory-cli) & `birdclaw` — the local-first storage pattern

Source: `github.com/afar1/fieldtheory-cli`, `github.com/steipete/birdclaw` (TS, MIT).

What we copy:
- **Raw snapshot + derived index.** `ft` keeps JSONL *and* a SQLite FTS index; truth is
  the raw file, the index is rebuildable. confos does exactly this: `raw/<venue>/*.jsonl`
  is truth, `confos.db` is derived (`confos index rebuild`).
- **Local-first, no telemetry, inspectable `~/.confos`** the user owns and can `rm -rf`.
- **Stable JSON for agents + a bundled skill** (`ft skill install` → `/fieldtheory`).
  confos ships `.agents/skills/confos/SKILL.md`.
- **One verb + noun command shape**; same data feeds human UI and agent JSON.

What we adapt: their domain is short text (tweets/bookmarks, ~2MB → FTS is trivially
instant). Conference abstracts are larger and aggregations are heavier, so we invest more
in the schema, normalization (orgs/countries), and ranking than a bookmark tool needs.

## `openreview-py` — the data layer

Source: `github.com/openreview/openreview-py` (MIT). Full mechanics in
[research/openreview-api.md](research/openreview-api.md). Key decisions it drives:
- Target **API v2** (`api2.openreview.net`), **anonymous reads** by default.
- `get_all_notes(invitation=…)` with `limit=1000`; read `submission_name` from the venue
  group (don't hard-code `/-/Submission`).
- Accepted set via `content={'venueid': venue_id}`; decision *type* via the `venue` string
  or Decision notes.
- Incremental: `mintcdate` watermark + `sort='tmdate:desc'` short-circuit (no `mintmdate`
  on `/notes`). Pin `openreview-py>=2.0.0` (v2.0.0 was a breaking release).

## Summary: what confos = a synthesis of

```
gogcli shape           (cmd/internal split, unified flags, AGENTS.md, agent safety)
  + ft/birdclaw storage (raw JSONL truth + derived SQLite/FTS, bundled skill, local-first)
  + create-cli rubric   (output/exit/flag/config discipline)
  + openreview-py        (the actual conference data)
  in Python              (typer + rich + pydantic + uv) — because the data + analysis live there
```
