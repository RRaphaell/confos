# confos — JSON Output Schemas

**Status:** canonical · **Last updated:** 2026-05-31

The `--json` output is a **public contract**. Agents and scripts depend on field paths
(AGENTS.md hard-codes e.g. `.data.papers[].title`). This doc defines the stable shapes.
Every schema carries `schema_version`; `confos schema <command>` prints the matching
schema. Fields may be *added* in a minor version; renames/removals bump `schema_version`.
(Closes critic finding C5.)

---

## 1. Standard envelope (all `--json` commands)

```json
{
  "ok": true,
  "schema_version": "1",
  "command": "papers.search",
  "query": { "...": "echo of the resolved query/args" },
  "data": [ /* or {} — command-specific, see below */ ],
  "warnings": ["human-readable, non-fatal notes"],
  "provenance": {
    "db": "~/.confos/confos.db",
    "sources": ["openreview"],
    "venue": "neurips-2025",
    "generated_at": "<ISO-8601, stamped by caller, not in tests>"
  }
}
```
Error form:
```json
{ "ok": false, "schema_version": "1", "command": "...",
  "error": { "code": 4, "type": "network", "message": "..." } }
```

## 2. Paper object (shared by search/show/related/export)
```json
{
  "paper_id": "aBcDeFgHiJ",                 // OpenReview note id == public id (C3)
  "title": "…",
  "abstract": "…",                          // present in `show` + context packs; omitted in list/search views
  "authors": [ { "author_id": "~Alice_Smith1", "name": "Alice Smith", "position": 0 } ],
  "keywords": ["…"],
  "status": "accepted|under_review|withdrawn|desk_rejected|unknown",  // derived locally (C2)
  "acceptance_type": "oral|spotlight|poster|null",   // when decisions ingested (S7)
  "venue": "neurips-2025",
  "url": "https://openreview.net/forum?id=aBcDeFgHiJ",
  "bm25": 7.4                                // search/find only; relevance score
}
```

## 3. Author object (shared by find/show/papers/coauthors)
```json
{
  "author_id": "~Alice_Smith1",             // profile id, or "email:a@mit.edu", or "name:alice-smith#1" (C3/S5)
  "display_name": "Alice Smith",
  "affiliation_current": "MIT" ,            // or "Unknown"
  "data_quality": "resolved|low|unresolved",
  "profile_url": "https://openreview.net/profile?id=~Alice_Smith1"  // null if no profile
}
```
`authors find` extends this with the ranking fields in [RANKING.md](RANKING.md) §2.

## 4. Stats object (topics/orgs/countries; `orgs top` carries it too)
Every stats payload includes a `data_quality` block — confos never fakes clean numbers.
`rows` lists only the *known* keys; the unknown count lives in `data_quality.unknown`
(it is not a synthetic `"Unknown"` row — that would distort `share` math in trends).
```json
{
  "rows": [ { "key": "USA", "papers": 2100 }, { "key": "Germany", "papers": 480 } ],
  "data_quality": {
    "papers_total": 5020,
    "papers_with_signal": 3590,           // e.g. papers with a parseable country
    "unknown": 1430,                      // papers_total - papers_with_signal
    "low_confidence": 240,                // v1: all email-domain affiliations are low-confidence
    "method": "author_affiliation_domain_v1"
  }
}
```
(`stats overview` is a summary object — `papers`, a `status` map, and `authors`/`orgs`/
`topics`/`venues` counts — not the rows/data_quality shape above.)

## 5. Trends object
```json
{
  "topic": "evals",
  "series": [ { "venue": "neurips-2024", "year": 2024, "matched": 88, "total": 4100,
                "share": 0.0215, "top_authors": ["…"], "top_orgs": ["…"] },
              { "venue": "neurips-2025", "year": 2025, "matched": 142, "total": 4500,
                "share": 0.0316, "top_authors": ["…"], "top_orgs": ["…"] } ],
  "delta": { "matched_abs": 54, "share_pp": 1.01 }
}
```

## 6. Context pack (`export context`) — the headline agent artifact
A single self-contained, fully-cited object an agent ingests to plan real work. Like every
other command it uses the standard envelope (§1); the pack itself is the `data` object, so
agents read `.data.papers[].title`, `.data.authors[]`, etc. **v1 is LLM-free**
(principle #5) — it contains only data confos can derive + cite.
```json
{
  "ok": true,
  "schema_version": "1",
  "command": "export.context",
  "query": { "topic": "agent evals", "venue": "neurips-2025" },
  "data": {
    "type": "confos.context_pack",
    "topic": "agent evals",
    "venue": "neurips-2025",
    "papers":  [ /* Paper objects, ranked by bm25, WITH abstract + url (self-contained) */ ],
    "authors": [ /* ranked Author objects per RANKING.md, with matched_papers */ ],
    "orgs":    [ { "name": "…", "papers": 12 } ],
    "stats":   { "matched": 142, "total": 4500, "share": 0.0316, "by_status": { "accepted": 130 } },
    "thin_areas": [ "keyword pairs / subtopics with few papers" ],  // heuristic, LABELLED — NOT "open questions"
    "notes": "All fields derived locally from OpenReview with provenance; no LLM synthesis."
  },
  "provenance": { "db": "~/.confos/confos.db", "sources": ["openreview"], "venue": "neurips-2025" }
}
```
**Removed from v1:** the earlier "open_questions" field — it implied LLM synthesis, which
v1 explicitly excludes (PRODUCT §8). Its honest, no-LLM stand-in is `thin_areas`
(under-represented keyword combinations), clearly labelled as a heuristic, not a claim.
An LLM-synthesized `open_questions` may return in a later phase behind `--llm`.

### Free-text in HTML output
The one real correctness note: when `viz --format html` emits paper/author strings into
HTML, escape them (standard `html.escape`) so a stray `<` doesn't break the page. That's
it — nothing more elaborate. The data is public; there's no secret to protect.
