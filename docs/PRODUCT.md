# confos — Product Specification

**Status:** canonical · **Last updated:** 2026-05-31

This document defines *what* confos is and *why*. For *how it's built* see
[ARCHITECTURE.md](ARCHITECTURE.md), [CLI_CONTRACT.md](CLI_CONTRACT.md), and
[BUILD_PLAN.md](BUILD_PLAN.md).

---

## 1. One-liner

`confos` is a local-first, agent-native CLI that turns AI/ML conferences into a
queryable knowledge base — search, people discovery, trends, visualization, and
agent-ready exports, all offline, all with provenance.

## 2. Goal

Give a human **or an agent** one tool that answers the questions conference websites
and dashboards can't, without leaving the terminal and without a network round-trip per
query:

- What papers are about *X*, ranked?
- Who actually works on *X*, and how do I reach them?
- Which labs / orgs / countries dominate a topic?
- How did a topic change across years or venues?
- What does the field look like (as a chart / graph)?
- Give my agent a self-contained context pack about *X* so it can plan real work.

## 3. The wedge — why this is good (and not the thing we killed)

An earlier version of confos was a "generic OpenReview browser." We **killed** it: the
web already does generic browsing (OpenReview's site) and dashboards (PaperCopilot,
627k users), it was seasonal, and it signalled "academic-tools," not "agent builder."

This version is deliberately different. The spine that keeps it sharp:

| Edge | Why it matters | Why the web can't copy it cheaply |
|---|---|---|
| **Agent-native** | An agent drives the *entire* surface via stable JSON | Dashboards are for human eyes/clicks |
| **Local-first** | Millisecond queries, offline, no rate limits, no per-query cost | Web tools are network round-trips |
| **Composable** | Pipe into `jq`, other CLIs, agent shells; scriptable | Dashboards don't pipe |
| **Analysis depth** | People discovery, trends, aggregates, graphs — not just a paper list | OpenReview lists; it doesn't rank people-by-topic |
| **Provenance** | Every paper / stat / person traces to an OpenReview id + URL | Trust is the whole game for agents |

Every feature below must reinforce at least one of these. If a feature is "a worse
version of the OpenReview website," it doesn't ship.

## 4. Who uses it, and how

### Researcher / enthusiast (primary human)
Surveys a field, preps for a conference, finds collaborators. Drives confos directly:
`confos authors find --topic "world models"`, `confos trends ...`, `confos viz ...`.

### Builder / founder
Tracks what labs and people are doing in an area; finds who to talk to. Uses people
discovery + org stats + export.

### Agent (first-class user)
Claude Code / Codex calls confos to do real work — "build me a reading list on agent
evals at NeurIPS 2025 with citations," "who should I follow on long-running agents,"
"draft outreach to the top 10 authors on context engineering." The agent relies on
`--json`, provenance, and the bundled skill. **This is the user the web tools ignore.**

## 5. Capabilities — worked examples

Every capability has a human form (rich tables) and an agent form (`--json`).

### 5.1 Search
```bash
confos papers search "long-running agents" --venue neurips-2025
confos papers search "tool use" --venue neurips-2025 --accepted-only --limit 50 --json
confos papers show <paper-id> --json
confos papers related <paper-id>
```
FTS5/BM25 over title + abstract + keywords + author names + normalized orgs. Filters:
`--venue`, `--year`, `--org`, `--accepted-only`. Every result carries its OpenReview id + URL.

### 5.2 Find people (the differentiator)
```bash
confos authors find --topic "agent memory" --venue neurips-2025 --limit 30
# -> ranked authors: name, affiliation, #relevant papers, recency, why-relevant, profile link
confos authors show <author-id>
confos authors papers <author-id> --venue neurips-2025
confos authors coauthors <author-id>
```
Ranks the people *actually publishing* on a topic at a venue — with an explanation of
*why* each ranked. This is the query no conference site answers.

### 5.3 Explore
```bash
confos orgs top --venue neurips-2025 --limit 50
confos orgs papers "Google DeepMind" --venue neurips-2025
confos venues list                       # local, offline
confos venues search "ICLR 2026"         # network — queries OpenReview live
```

### 5.4 Analyze (stats, honest about uncertainty)
```bash
confos stats overview --venue neurips-2025
confos stats topics --venue neurips-2025
confos stats countries --venue neurips-2025 --explain   # shows known/unknown/method
```
Every stats output reports `data_quality` (known / unknown / low-confidence counts +
method). We never fake clean numbers — affiliation/country data is genuinely messy and
we show it.

### 5.5 Trends
```bash
confos trends topic "evals" --venues neurips-2023,neurips-2024,neurips-2025
confos trends compare iclr-2025 iclr-2026 --topic "agents"
```
Counts, top authors/labs, and deltas across years/venues. `--json` for charting.

### 5.6 Visualize
```bash
confos viz topics --venue neurips-2025                 # terminal bar chart (rich)
confos viz orgs --venue neurips-2025
confos viz network --topic "agents" --venue neurips-2025 --format html   # co-authorship graph
confos viz network --topic "agents" --format mermaid                     # paste into md
```
Terminal-first (rich charts/tables); exportable HTML and Mermaid for graphs you can
drop into a doc or share.

### 5.7 Export (built for agents)
```bash
confos export context --topic "agent evals" --venue neurips-2025 --json
confos export context --topic "agent evals" --venue neurips-2025 --format markdown
confos export papers --venue neurips-2025 --format csv
confos export papers --venue neurips-2025 --format jsonl
```
The **context pack** is the killer agent primitive: one self-contained artifact (top
papers + authors + orgs + topic-scoped stats + thin-areas + sources) an agent ingests to
plan a literature review, a thread, or outreach — with every claim cited. (Schema:
[SCHEMAS.md](SCHEMAS.md) §6.)

## 6. Setup & maintenance
```bash
confos init        # create local store at ~/.confos (or $CONFOS_HOME)
confos doctor      # check environment, DB, FTS5, openreview-py (offline)
confos ingest neurips-2025          # pull venue into local store (network)
confos ingest neurips-2025 --force  # full re-sync
```

## 7. Product principles

1. **Local-first.** Ingest touches the network; everything else is offline & fast.
2. **Agent-native by default.** Every read command supports stable `--json`. Data →
   stdout, progress/warnings → stderr. `--no-input` never prompts.
3. **Provenance everywhere.** Every paper, stat, person traces to source id + URL.
4. **Honest uncertainty.** Show unknown/low-confidence counts; never fake clean stats.
   "Likely attending / likely relevant" is always a *labelled proxy*, never a claim.
5. **Useful without an LLM.** Search, stats, trends, viz, export all work with zero LLM.
   LLM synthesis (`ask`) is optional and additive.
6. **Visualize by default.** Humans get charts/tables; agents get JSON; both from the
   same data.
7. **Adapters, not scraping spaghetti.** OpenReview is one adapter; the seam is designed
   so AIE / PMLR / OpenAlex slot in later without a rewrite.
8. **Boring and trustworthy beats clever.** Stable contracts, tested, documented.

## 8. Scope

**v1 (this build):** full-featured **on OpenReview** — ingest, search, people, orgs,
stats, trends, viz, export, context packs, skill wrapper. Not thin: the whole surface
above, done well, for OpenReview venues.

**Designed-for-later (seams only in v1):** AIE talks/speakers adapter, PMLR fallback,
OpenAlex citation enrichment, semantic search (embeddings), LLM `ask`, MCP server.

**Explicit non-goals:** a hosted web app; a PaperCopilot stats-dashboard clone; a paper
PDF library; anything that requires a server we operate.

## 9. Success criteria

- **Human:** a researcher ingests a venue and gets a useful "top papers + people to
  know + trend" read in one session, offline, that they trust enough to act on.
- **Agent:** Claude Code / Codex produces a credible "top 20 papers + 10 people on topic
  X, with citations and no hallucinated stats" from confos alone.
- **Public:** a stranger installs it, ingests a venue, searches locally, exports JSON,
  and trusts the provenance — and the repo reads as a serious, modern OSS project.
