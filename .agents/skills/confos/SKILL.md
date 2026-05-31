---
name: confos
description: >
  Query AI/ML conferences locally — search papers, find researchers working on a topic,
  see trends, and export cited context packs. Use when the user asks about conference
  papers/authors/trends (NeurIPS, ICLR, ICML, COLM), wants a reading list, wants to know
  who works on a topic, or needs research context for a field. Runs the `confos` CLI.
---

# confos — conference intelligence skill

## When to use
The user asks anything like: "what papers are about X at NeurIPS," "who works on agent
memory," "how did topic Y trend year over year," "build me a reading list / context pack
on Z," "which labs dominate area W." Also when *you* (the agent) need grounded, cited
conference context to do a downstream task (thread, lit review, outreach).

## Prerequisite
`confos` installed (`uv tool install confos`). Verify with `confos doctor --json`.
If the target venue isn't local yet, ingest it (network, one-time): `confos ingest <venue>`.

## Workflow
1. **Confirm availability:** `confos venues list --json`; ingest if missing.
2. **Pick the right command** (always `--json --no-input`):
   - reading list / find papers → `confos papers search "<q>" --venue V --json`
   - who works on a topic → `confos authors find --topic "<t>" --venue V --json`
   - trends → `confos trends compare V1 V2 --topic "<t>" --json`
   - landscape stats → `confos stats topics --venue V --json` (+ `viz` for charts)
   - everything-about-X → `confos export context --topic "<t>" --venue V --json`
3. **Read the JSON, cite the provenance.** Every row has a source id + URL. Use them.
   Report `unknown`/low-confidence counts honestly; never fabricate stats.
4. **Summarize for the user** with citations; offer the context pack for deeper work.

## Safety
- Read commands (search/find/stats/trends/viz/export) are offline + safe — no approval needed.
- `ingest`/`sync` hit the network and take time — show progress, fine to run.
- Never run destructive commands without explicit user intent.

## Notes
- `confos schema <command>` documents any command's JSON output (versioned).
- "Likely relevant / likely attending" is a labelled proxy (e.g. authored a paper at the
  venue), not a certainty — present it as such.
- See `AGENTS.md` in the repo for full recipes.
