# AGENTS.md — driving confos from an agent

confos is built to be operated by coding agents (Claude Code, Codex, or any agent with
shell access). This file tells an agent how to use it well.

## What confos is (for an agent)
A local, offline, queryable index of AI/ML conferences. You ingest a venue once, then
run fast local queries that return **stable JSON with provenance**. Use it to build
reading lists, find people on a topic, compute trends, and produce cited context packs.

## Golden rules
1. **Always pass `--json --no-input`** for programmatic use. stdout is pure JSON; logs go
   to stderr. Never parse the human table format.
2. **Check the data is local first.** Run `confos venues list --json`. If the venue isn't
   present, `confos ingest <venue>` (the network commands are `ingest` — re-run it to
   update — and `venues search`; everything else is offline).
3. **Trust, but cite.** Every paper/stat/person includes a source id + URL in
   `provenance` / per-row fields. Cite those. Do **not** invent statistics — if confos
   reports `unknown` counts, report them as unknown.
4. **Read-only commands never need approval** (search/show/find/stats/trends/viz/export).
   `ingest` (and re-running it to update) and `venues search` are the network commands —
   fine to run, but they take time; show progress.
5. **Exit codes matter:** 0 ok · 1 generic · 2 usage · 3 config · 4 network · 5 partial
   ingest · 130 interrupted. Branch on them. On 4 (network): retry once, then surface the
   error. On 5 (partial): proceed but tell the user the dataset is incomplete.

## Recipes

```bash
# 1. Make sure a venue is available
confos doctor --json
confos venues list --json
confos ingest neurips-2025            # if not already local

# 2. Build a cited reading list on a topic
confos papers search "agent memory" --venue neurips-2025 --json --limit 20

# 3. Find people to know / reach out to on a topic
confos authors find --topic "long-running agents" --venue neurips-2025 --json --limit 15

# 4. Compute a trend across years
confos trends compare neurips-2024 neurips-2025 --topic "evals" --json

# 5. One self-contained context pack to plan real work
confos export context --topic "agent evals" --venue neurips-2025 --json
```

## The context pack (your best primitive)
`confos export context --topic T --venue V --json` returns one object (under `.data`) with
top papers, authors, orgs, topic-scoped stats, thin-areas, and sources — everything needed
to plan a literature review, a thread, or outreach, with every claim cited. Prefer it over
many small queries when the task is "tell me about area X".

## Cost & payload notes
- `confos ingest <venue>` hits the network and takes minutes for a large venue (e.g.
  NeurIPS ~4–5k papers ≈ a few minutes, tens of MB). Everything else is local and fast.
- Keep JSON payloads small: prefer `--limit` and the context pack over dumping
  `export papers --format jsonl` (which can be large) straight into your context.

## Discovering the contract
`confos schema <command>` prints the JSON schema for that command's output. The JSON is
versioned (`schema_version`); rely on field names, not column order.

## Don't
- Don't scrape OpenReview directly — confos already normalized it with provenance.
- Don't treat "likely relevant" as fact — it's a labelled ranking, not ground truth.
- `venues search` and `ingest` are the only network commands; everything else is offline.
