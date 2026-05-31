# confos

**Conference intelligence in your terminal — for humans and agents.**

`confos` turns AI/ML conferences (NeurIPS, ICLR, ICML, COLM, …) into a local,
queryable knowledge base. Ingest a venue once from OpenReview, then search papers,
find the people working on a topic, see what's trending, visualize the landscape, and
export agent-ready context — all locally, all scriptable, all with provenance back to
the source.

It is built for terminals, shell scripts, CI, and **coding agents** (Claude Code, Codex,
or any agent with shell access). Every command speaks stable JSON, and after a one-time
ingest every query is local and offline — answers come back in milliseconds, and unlike
asking an LLM, every number is real and traceable, not guessed.

```bash
confos ingest neurips-2025
confos papers search "long-running agents" --venue neurips-2025
confos authors find --topic "agent memory" --venue neurips-2025   # who works on this?
confos trends topic "evals" --venues neurips-2024,neurips-2025      # what's rising?
confos viz topics --venue neurips-2025                              # see the landscape
confos export context --topic "agent evals" --venue neurips-2025 --json
```

---

## Why confos exists

Conference data is public but not *usable*. OpenReview and conference sites are browsing
surfaces — fine for clicking through one paper at a time, useless for "show me everyone
working on X, ranked," "how did this topic change year over year," or "give my agent
everything it needs to plan a literature review." PaperCopilot has great dashboards but
they live on the web, you can't script them, and an agent can't drive them.

`confos` owns the missing layer: **a local, agent-native, composable index** with
real analysis (trends, people discovery, aggregates, graphs) and honest provenance.
The differentiator is not "search papers" — it's that an agent can *drive* the whole
surface to do real work, offline, repeatably.

## What you can do

- **Search** papers by full text (title, abstract, keywords) with ranking and filters.
- **Find people** — rank the authors actually working on a topic, with their papers,
  affiliations, and a relevance explanation.
- **Explore** authors, organizations, and topics; follow related papers.
- **Analyze** — aggregate stats (topics, orgs, countries) with visible data-quality.
- **Trends** — how a topic moves across years / venues; compare two venues head-to-head.
- **Visualize** — terminal charts, plus exportable HTML/Mermaid topic & co-authorship graphs.
- **Export** — context packs (JSON/Markdown) purpose-built for agents; CSV/JSONL dumps.

## Who it's for

- **Researchers & enthusiasts** preparing for a conference or surveying a field.
- **Builders / founders** tracking what labs and people are doing in an area.
- **Agents** — `confos` is a first-class tool for Claude Code / Codex: stable `--json`,
  clean stdout/stderr separation, a bundled skill, and provenance so the agent never
  has to hallucinate a statistic.

## Install

```bash
uv tool install confos          # recommended
# or: uvx confos <command>      # run without installing
```
Requires Python 3.12+.

## First run

```bash
confos init                       # one-time: create the local store at ~/.confos
confos ingest neurips-2025        # pull the venue (network; ~4–5k papers, a few minutes)
confos papers search "agents" --venue neurips-2025
confos authors find --topic "agent memory" --venue neurips-2025
```
`confos venues search "ICLR 2026"` (or `confos venues aliases`) shows what you can ingest.
After ingest, everything is local and offline. See [docs/PRODUCT.md](docs/PRODUCT.md) for
the full tour and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how it works.

## Documentation

| Doc | What's in it |
|---|---|
| [docs/PRODUCT.md](docs/PRODUCT.md) | Goal, the wedge, who uses it, worked examples for every capability |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, ASCII diagrams, components, data model, stack |
| [docs/CLI_CONTRACT.md](docs/CLI_CONTRACT.md) | Full command tree, flags, output contract, exit codes, safety |
| [docs/RANKING.md](docs/RANKING.md) | How `authors find` ranks people + how `--topic` matching works |
| [docs/SCHEMAS.md](docs/SCHEMAS.md) | Stable `--json` output shapes (the agent/script contract) |
| [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md) | How the project is built: phases, standards, testing, validation |
| [docs/REFERENCES.md](docs/REFERENCES.md) | Lessons taken from `ft`, `birdclaw`, `gogcli`, `create-cli` |
| [AGENTS.md](AGENTS.md) | How an agent should drive confos |

## Status

Early development. Built in public-grade phases — see [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md).

## License

MIT — see [LICENSE](LICENSE).
