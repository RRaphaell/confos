# confos — Ranking & Topic Matching Spec

**Status:** canonical · **Last updated:** 2026-05-31

`authors find --topic` is the product's differentiator, and `--topic` matching underlies
`trends`, `stats topics`, `viz topics`, and `export context`. This doc pins down exactly
how both work so the implementation is deterministic, testable, and reproducible — not
"anyone's guess." (Closes critic findings C4 + C6.)

---

## 1. Topic matching (`--topic`)

A "topic" is **not** an exact keyword. OpenReview `content.keywords` is free-text,
inconsistent ("LLM agents" / "llm agent" / "agents"), and only partially populated
(~30–60% coverage per [research/openreview-api.md](research/openreview-api.md) §5). So
exact keyword equality would silently miss most relevant papers.

**Definition:** a paper *matches* `--topic "<t>"` iff its FTS row matches the FTS query
built from `<t>` over **title + abstract + keywords** (the `papers_fts` columns), using
SQLite FTS5. The matcher:

1. Lowercases and trims the topic string.
2. Splits on commas into OR-groups; within a group, tokens are AND-ed.
   `--topic "agent memory, long-running agents"` →
   `(agent AND memory) OR (long-running AND agents)`.
3. Applies the topic-alias table (`aliases/topics.yml`, user-editable) to expand known
   synonyms before building the query (e.g. `evals → (evals OR evaluation OR benchmark)`).
   Ships with a small seed alias set; users extend it.
4. Runs as an FTS5 `MATCH`; relevance via `bm25(papers_fts)`.

This means `--topic "agent memory"` matches a paper titled "Long-term memory for LLM
agents" even when its keywords are `["memory","LLM"]`. Coverage limitations are documented
honestly in PRODUCT §5 (principle #4) — FTS over abstracts is the mitigation, not a
perfect topic model. Semantic/embedding matching is explicitly a later phase.

`stats topics` / `viz topics` aggregate over **normalized keywords** (lowercased,
alias-collapsed) and report coverage (`papers_with_keywords / total`) so a keyword-sparse
venue is visibly sparse, not silently empty.

## 2. `authors find --topic` ranking

### Candidate set
All authors who appear on at least one paper that matches `--topic` (per §1) in the
selected scope (`--venue`, or all ingested venues if none given).

### Score
For each candidate author *a* with matched papers *P_a*:

```
score(a) =
    1.0 * matched_paper_count(a)                 # primary: how much they work on it
  + 0.5 * sum(bm25_relevance(p) for p in P_a)    # weighted by how on-topic each paper is
  + recency_bonus(a)                             # see below
```

- `bm25_relevance(p)` is normalized to 0–1 within the result set (best match = 1).
- **`recency_bonus`** is **0 for single-venue queries** (every paper shares the venue's
  year — recency is meaningless within one venue; this was a flaw the critic caught). For
  **multi-venue** queries it is `0.3 * (newest_year(P_a) - min_year) / (max_year - min_year)`,
  rewarding authors active in the most recent venues. With one year in scope it is 0.

### Deterministic tie-break (required for reproducible JSON + tests)
Sort by: `score desc`, then `matched_paper_count desc`, then `author_id asc`
(OpenReview profile id / normalized email — stable across `index rebuild` per C3).
No reliance on rowid or insertion order.

### Output fields (per ranked author)
```
author_id            # OpenReview profile id (or email:/name: fallback — see C3/S5)
display_name
affiliation_current  # may be "Unknown" (honest)
data_quality         # resolved | low | unresolved
matched_paper_count
score                # rounded to 4 dp
score_components     { paper_count, bm25_sum, recency_bonus }
why_relevant         # human string, e.g. "3 papers matching 'agent memory'; top: <title>"
matched_papers       [ { paper_id, title, url, bm25 } ]   # provenance
profile_url          # OpenReview profile URL when profile id present
```

`why_relevant` is built from the data (no LLM): paper count + the highest-bm25 matched
title. `matched_papers` carries provenance so the human/agent can verify every claim.

### Honesty rules
- Unresolved/email-only authors (no profile id) are included but flagged
  `data_quality: unresolved|low` and are **never merged across papers by name** (C3/S5).
- "Likely relevant" is a ranking, not a claim of ground truth — labelled as such in output.

## 3. Acceptance test (pins "correct")
A fixture venue with a hand-constructed set of papers/authors has a **known expected
ranking** committed in `tests/fixtures/`. The Phase 3 DoD requires `authors find` to
reproduce it exactly (including tie-break order). This is what makes the wedge testable
rather than vibes.
