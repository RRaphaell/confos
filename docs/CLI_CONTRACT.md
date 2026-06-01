# confos — CLI Contract

**Status:** canonical · **Last updated:** 2026-05-31

The CLI is a public contract — especially the JSON, which agents and scripts depend on.
This doc is the spec the implementation must satisfy. It applies the `create-cli`
rubric (see [REFERENCES.md](REFERENCES.md)).

---

## 1. Invocation

```
confos [global flags] <group> <command> [args] [command flags]
```
Human-first output by default; fully scriptable via flags. `-h/--help` on any node prints
help and ignores other args. `--version` prints version to stdout.

## 2. Command tree

```
confos
  init                              create local store (~/.confos)
  doctor                            check env, DB, FTS5, openreview-py (offline)

  venues
    list                            list known/ingested venues
    search <query>                  find a venue (OpenReview)
    show <slug>                     venue detail
    add --slug S --openreview-id ID register a custom venue
    aliases                         show built-in alias map

  ingest <venue> [--include-decisions] [--force] [--dry-run]
        # pulls the full submission set; status derived locally (see ARCHITECTURE §8).
        # --include-decisions: also fetch Decision notes to populate acceptance_type
        #   (oral/spotlight/poster); off by default (heavier fetch). --force ignores
        #   sync watermarks for a full re-pull. Re-running ingest = incremental update.
        # (--accepted-only is a query-time filter on read commands, not an ingest flag.)

  papers
    search <query> [--venue V] [--year Y] [--org O] [--accepted-only] [--limit N]
    show <paper-id> [--with related]   # authors + abstract are always included
    related <paper-id> [--limit N]

  authors
    find --topic T [--venue V] [--limit N]      # ranked people working on a topic
    search <name>
    show <author-id>
    papers <author-id> [--venue V]
    coauthors <author-id>

  orgs
    top [--venue V] [--limit N]
    papers <org> [--venue V]

  stats
    overview [--venue V]
    topics [--venue V]
    countries [--venue V] [--explain]
    orgs [--venue V]

  trends
    topic <topic> --venues V1,V2,...
    compare <venue-a> <venue-b> --topic T

  viz
    topics [--venue V]                           # terminal bar chart
    orgs [--venue V]
    network --topic T [--venue V] [--format terminal|mermaid|html]

  export
    context --topic T [--venue V] [--format json|markdown]
    papers [--venue V] --format csv|jsonl
    authors [--venue V] --format csv|jsonl

  index
    rebuild                          re-normalize from raw JSONL (no network)
    status

  schema <command>                   print JSON schema for a command's --json output
```

## 3. Global flags

| Flag | Meaning |
|---|---|
| `-h, --help` | Show help, ignore other args |
| `--version` | Print version to stdout |
| `--json` | Emit stable JSON to stdout (and only JSON) |
| `--plain` | Stable line/TSV output for scripts |
| `-q, --quiet` | Suppress non-essential stderr |
| `-v, --verbose` | More diagnostics on stderr (repeatable) |
| `--no-input` | Never prompt; fail if input required |
| `--no-color` | Disable color (also respects `NO_COLOR`, `TERM=dumb`, non-TTY) |
| `--home <path>` | Override data dir (else `$CONFOS_HOME` else `~/.confos`) |
| `--venue <slug>` | Default venue for the command |
| `--limit <n>` | Cap result count |

Output modes are mutually exclusive: default (human) · `--json` · `--plain`.

## 4. Output contract

- **stdout:** the requested data only. Under `--json`, valid JSON and nothing else.
- **stderr:** progress, warnings, cache notices, diagnostics, errors.
- Human output may evolve freely. **JSON output is versioned and treated as a contract**
  (`schema_version` field; `confos schema <cmd>` documents it).
- Network-heavy commands stream progress to stderr so stdout stays parseable.

### JSON envelope
```json
{
  "ok": true,
  "schema_version": "1",
  "command": "papers.search",
  "query": { "venue": "neurips-2025", "q": "agent memory", "limit": 20 },
  "data": [ /* results */ ],
  "warnings": [],
  "provenance": { "db": "~/.confos/confos.db", "sources": ["openreview"] }
}
```
Errors under `--json`:
```json
{ "ok": false, "error": { "code": 4, "type": "network", "message": "..." } }
```

## 5. Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Generic failure |
| 2 | Invalid usage / validation error |
| 3 | Config / environment problem |
| 4 | Network / backend failure |
| 5 | Partial ingest failure |
| 130 | Interrupted (Ctrl-C), bounded cleanup |

Keep this set small; don't invent per-command codes without a real scripting need.

## 6. Safety classes

| Class | Commands | Network | Writes DB | Guard |
|---|---|---|---|---|
| local-read | search, show, related, find, stats, trends, viz, export, venues list/show | no | no | none |
| network | ingest, venues search | yes | yes (ingest) | explicit command; progress on stderr |
| local-write | index rebuild, venues add | no | yes | none (idempotent) |
| destructive | future prune/reset (not in v1) | maybe | yes | confirm (TTY) or `--force` (non-interactive) |

> There is **no `sync` command.** Incremental update = re-running `confos ingest` (it uses
> stored watermarks); `--force` does a full re-pull. (Exit code 5 = a partial ingest.)
> `venues search` hits the network — agents/scripts should treat it as a network call.

Agent rule: `--json --no-input` on any local-read command must **never** prompt and never
hit the network.

## 7. Config precedence

```
command-line flags  >  env vars  >  user ~/.confos/config.toml  >  built-in defaults
```
(No per-project config layer — confos has one global store, so a `./.confos.toml` would be
a layer with no real use case. Kept deliberately simple.)
Env vars: `CONFOS_HOME`, `CONFOS_CONFIG`, `OPENREVIEW_USERNAME`/`OPENREVIEW_PASSWORD`
(optional; anonymous reads are the default), `NO_COLOR`.

## 8. Dry-run

State-changing commands accept `--dry-run` and report would-fetch / would-insert /
would-update / would-skip counts (structured under `--json`).

## 9. Examples (the README/help set)

```bash
confos init
confos doctor --json
confos ingest neurips-2025
confos papers search "long-running agents" --venue neurips-2025 --json
confos authors find --topic "agent memory" --venue neurips-2025 --limit 20
confos trends compare neurips-2024 neurips-2025 --topic "evals" --json
confos viz network --topic "agents" --venue neurips-2025 --format mermaid
confos export context --topic "agent evals" --venue neurips-2025 --json | jq '.data.papers[].title'
```

## 10. Help text requirements

Every command's `--help` includes: one-line purpose · usage · 2–3 examples · flags ·
output notes (how `--json`/`--plain` differ) · safety note for network/destructive.
Missing required args → concise help + one example, exit `2`.
