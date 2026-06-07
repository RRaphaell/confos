# OpenReview API & openreview-py — Research Memo (2026-05-23)

**Date:** 2026-05-23
**Purpose:** Working reference for `confos`, ingesting OpenReview metadata into SQLite.

At initial research time, `openreview-py` **v2.2.0** (2026-04-28) was the latest release;
the project now locks **v2.2.1** in `uv.lock`. v2.0.0 was cut on 2026-04-02 as a deliberate
breaking-changes release. The repository is actively maintained and MIT-licensed.

---

## 1. API Versions and Client Choice

OpenReview runs **two parallel APIs**: API v1 (legacy, base URL `https://api.openreview.net`) and API v2 (current, base URL `https://api2.openreview.net`). The Python client ships both in one package: `openreview.Client` talks to v1, and `openreview.api.OpenReviewClient` talks to v2. They are **not interchangeable** — note content fields are wrapped in `{"value": ...}` dicts under v2 but flat under v1, and the v2 client refuses to start if you point it at a v1 base URL (it raises `OpenReviewException` and tells you to use the legacy client).

For a 2026 tool, **target v2**. The OpenReview docs are explicit that v2 is the default and v1 is "being phased out, primarily used for conferences before 2024." All major venues from 2024 onward (NeurIPS, ICLR, ICML, COLM, etc.) are on v2. The only realistic reason to talk to v1 is reading older conference archives. A pragmatic posture for `confos`: v2-only on day one; add v1 fallback later if a user requests historical venues.

The library is actively maintained (releases every 2-4 weeks throughout 2025-2026), Python 3.9+ required, install via `pip install openreview-py`.

## 2. Authentication

Auth on OpenReview is **optional for public reads**. The `OpenReviewClient.__init__` signature takes `baseurl`, `username`, `password`, `token`, `tokenExpiresIn` — all optional. You can instantiate without credentials and read public submissions, decisions, and accepted-paper lists. This was famously demonstrated (and abused) in 2025 when an unauthenticated bug on `/profiles/search` exposed reviewer identities — relevant to `confos` only as confirmation that anonymous reads are real, but the public surface for *notes* is intentional.

Credentialed auth uses username + password to obtain a JWT bearer token (max lifetime 1 week, set via `tokenExpiresIn`). The token is sent as `Authorization: Bearer <jwt>`. You can skip login by passing an existing `token=` directly. There is no separate "API key" concept — sessions are JWTs from `/login`. MFA is supported via `MfaRequiredException` on accounts that have it enabled.

**Default for `confos`**: anonymous-by-default, with optional credentials supplied through
env vars (`OPENREVIEW_USERNAME` / `OPENREVIEW_PASSWORD`) if a future command needs them. There
is no `confos --login` flag today. The only data anonymous mode cannot see is reviewer-private
content (anonymous reviewer identities, reviewer-only discussions, withdrawn-paper internals
on some venues). Public papers, accepted lists, abstracts, PDFs, and decision outcomes are
all reachable without credentials.

## 3. Venue Identification

Venues are addressed by string IDs that look like paths: `NeurIPS.cc/2025/Conference`, `ICLR.cc/2025/Conference`, `ICML.cc/2025/Conference`. The convention is `<host_domain>/<year>/<track>`. Track is usually `Conference`, sometimes `Workshop`, occasionally finer-grained (`Workshop/SubName`).

The domain prefix is **not uniform** across venues:
- NeurIPS: `NeurIPS.cc/2025/Conference`
- ICLR: `ICLR.cc/2025/Conference`
- ICML: `ICML.cc/2025/Conference`
- COLM: `colmweb.org/COLM/2024/Conference` (note the extra `/COLM/` segment — different domain owner)
- ECCV, AAAI, EMNLP, NAACL, ARR etc. all follow similar but not identical patterns

There is no hard rule. The user-facing way to find a venue ID is to visit `openreview.net/group?id=<venue_id>` and read it off the URL after `?id=`. There is a `get_venues()` method on the v2 client (`client.get_venues(id=..., ids=..., invitations=...)`) that returns Venue dicts, and `https://openreview.net/venues` lists everything publicly. So you have both a programmatic list and a UI.

**Practical recommendation for `confos`**: ship a curated alias map for major venues (`neurips2025`, `iclr2025`, `icml2025`, `colm2024`, etc. → canonical IDs), expose `confos venues list` (calls `get_venues()`) for discovery, and accept raw venue IDs as a pass-through. Don't try to derive IDs algorithmically — too many exceptions.

## 4. Submission Retrieval (API v2)

The canonical pattern is **invitation-based**. Each venue exposes a submission invitation; the convention is `<venue_id>/-/Submission`, but the exact name varies — it's defined on the venue group itself in a content field called `submission_name`. The robust recipe:

```python
import openreview
client = openreview.api.OpenReviewClient(baseurl='https://api2.openreview.net')

venue_id = 'NeurIPS.cc/2025/Conference'
venue_group = client.get_group(venue_id)
submission_name = venue_group.content['submission_name']['value']  # e.g. 'Submission'

submissions = client.get_all_notes(
    invitation=f'{venue_id}/-/{submission_name}'
)
```

`get_all_notes()` is the high-level wrapper that paginates for you and returns the full list. For memory-sensitive workflows, the `openreview.tools` module has `iterget_notes()` (generator) and `efficient_iterget` for streaming.

**Status filtering — accepted vs rejected vs withdrawn — is the hard part.** Modern OpenReview venues use the `venueid` content field on the submission itself as the authoritative state marker. After decisions are released, accepted papers get their `venueid` rewritten from the under-review value to the venue's published value, and rejected/withdrawn papers get rewritten to dedicated buckets. The clean pattern:

```python
# all accepted (any track)
accepted = client.get_all_notes(content={'venueid': venue_id})

# rejected / withdrawn — venueid points elsewhere; inspect venue_group.content
# for keys like 'submission_venue_id', 'withdrawn_venue_id', 'desk_rejected_venue_id'
```

There are **also** separate `Decision` notes (invitation pattern `<venue_id>/Submission<N>/-/Decision`), which are per-paper replies posted by program chairs. These are useful when you want the *reason* (Accept (oral), Accept (poster), Reject), but they're nested under each submission, not a single flat list. The cleanest way to fetch them in bulk is via `get_all_notes(invitation=..., details='replies')`, which inlines each submission's replies into a `details['replies']` field; you then filter replies by invitation suffix (`endswith('Decision')`).

NeurIPS specifically uses both mechanisms: `venueid` is rewritten post-decision (so `content={'venueid': 'NeurIPS.cc/2025/Conference'}` gives accepted papers), and per-paper `Decision` notes hold finer-grained acceptance type (oral vs spotlight vs poster). For `confos`, **prefer the `venueid` filter** for "is this accepted" — it's a single query — and only join Decision notes if you want acceptance type.

## 5. Note Structure (API v2)

A submission `Note` carries these top-level fields:

- `id` — random 10-char string, the stable primary key
- `number` — integer, paper number within the venue (auto-assigned)
- `invitations` — list of all invitations that have touched this note (latest first)
- `domain` — the venue ID (auto-set, immutable)
- `forum` — for submissions equals `id`; for replies, points to the parent submission
- `replyto` — direct parent note ID (null for top-level submissions)
- `signatures`, `readers`, `writers`, `nonreaders` — ACL lists
- `cdate` / `tcdate` — creation timestamps (ms since epoch); `cdate` is user-settable, `tcdate` is system-managed and immutable
- `mdate` / `tmdate` — modification timestamps (same split)
- `odate`, `pdate` — public-on and publication dates
- `ddate` — soft-delete timestamp (null = alive)
- `license`, `venue`, `venueid` — set after decision; `venue` is human-readable, `venueid` is structured
- `content` — the submission's actual fields, wrapped as `{"value": X}`

Typical submission sketch:

```json
{
  "id": "aBcDeFgHiJ",
  "number": 4271,
  "forum": "aBcDeFgHiJ",
  "invitations": ["NeurIPS.cc/2025/Conference/-/Submission"],
  "domain": "NeurIPS.cc/2025/Conference",
  "signatures": ["NeurIPS.cc/2025/Conference/Submission4271/Authors"],
  "tcdate": 1715731200000,
  "tmdate": 1730908800000,
  "pdate": 1727308800000,
  "venueid": "NeurIPS.cc/2025/Conference",
  "venue": "NeurIPS 2025 poster",
  "license": "CC BY 4.0",
  "content": {
    "title":      {"value": "..."},
    "abstract":   {"value": "..."},
    "authors":    {"value": ["Alice Smith", "Bob Tan"]},
    "authorids":  {"value": ["~Alice_Smith1", "bob@mit.edu"]},
    "keywords":   {"value": ["transformers", "scaling"]},
    "TLDR":       {"value": "..."},
    "pdf":        {"value": "/pdf/abc...def.pdf"},
    "primary_area": {"value": "Deep Learning"}
  }
}
```

What's reliable: `title`, `abstract`, `authors`, `authorids`, `pdf` are present on essentially every venue. `keywords` is common but not universal. `TLDR` is offered on most venues' forms but is optional for authors, so coverage is partial (often 30-60%). `primary_area` is venue-specific. **Treat every field except `id`, `number`, `invitations`, `tcdate`, `tmdate` as optional and use `.get('field', {}).get('value')` defensively.**

Authors are stored in *two* parallel arrays: `authors` (display names, strings) and `authorids` (profile IDs like `~Alice_Smith1` or raw emails). These are positionally aligned — index *i* of one matches index *i* of the other.

## 6. Incremental Sync — the Big Gotcha

This is the answer to read carefully. Yes, every note carries `tcdate` and `tmdate` in ms-since-epoch, plus a stable `id`. **But** if you actually read the v2 client source (`openreview/api/client.py`, lines 1431 and 1570), the parameter exposed on `get_notes` and `get_all_notes` is only `mintcdate` — minimum *true creation date*. There is **no** `mintmdate`, `maxtmdate`, `maxtcdate` on the notes endpoint. `mintmdate` *does* exist on `/tags` (line 1851), so it's a deliberate omission for notes, not an oversight.

What this means for incremental sync: you cannot directly ask "give me notes modified since X." You have two workable strategies:

1. **`mintcdate`-based sync for new submissions.** Track the max `tcdate` you've ingested per venue. Each tick, call `get_all_notes(invitation=..., mintcdate=last_max_tcdate + 1)`. This catches new submissions but misses edits to existing ones (revised abstracts, late-added co-authors, decision-time `venueid` rewrites).
2. **Full re-fetch with diff.** For each venue, periodically (e.g. daily during the active review window, weekly otherwise) re-pull all submissions and compare `tmdate` locally. Cheaper than it sounds — even NeurIPS only has ~15k submissions and the API streams them fast.

A hybrid is best for `confos`: `mintcdate` for daily ticks (cheap, picks up new submissions), full re-sync weekly to catch edits and decision rewrites.

`sort='tmdate:desc'` is supported and useful — you can pull descending-by-modify and short-circuit when you hit an unchanged note (a poor man's mintmdate). The `sort` parameter accepts `number`, `cdate`, `ddate`, `tcdate`, `tmdate`, `replyCount`, each with `:asc` or `:desc`.

**Pagination** is offset/limit, with `after=<note_id>` cursor pagination also supported. `limit` is hard-capped at **1000** server-side — values higher than 1000 silently clamp. The pragmatic page size is 1000 (max throughput). `get_all_notes()` handles pagination for you automatically using the `after` cursor; trust it.

## 7. Rate Limits

OpenReview does not publish formal rate limits. The bug-bounty disclosure of an unmetered `/profiles/search` in 2025 confirms there was *no* per-IP throttle on at least that endpoint, and the patch focused on closing the public access rather than introducing limits. In practice the client is polite by construction:

The v2 client wraps `requests` with retry behavior for backend failures and sets a
`User-Agent` of `openreview-py/{version} (Python/{x.y})`, which is reasonable
identification. In live profile-enrichment testing, `openreview-py` also printed 429/retry
messages while waiting out the `/profiles` window; confos swallows that stdout noise during
profile fetches so `--json` stays parseable.

Best practices for `confos`:
- Don't parallelize aggressively — sequential `get_all_notes` per venue is fine and predictable
- Cache aggressively in SQLite — the whole point of `confos`. Re-fetch only what's needed (use `mintcdate` and `sort=tmdate:desc` tricks above)
- Identify your tool in the User-Agent if you can (`requests.Session()` patch or env var)
- Be especially polite to `/profiles` — it's the endpoint that has been historically abused

A sensible default: between page fetches, add nothing. Do not add a public rate-limit knob
unless a concrete endpoint needs it; for profiles, the shipped answer is sequential,
resumable fetching rather than user-tuned concurrency.

## 8. Decisions — Joining Strategy

Three viable strategies, ordered by clean-to-messy:

1. **`venueid` filter** (cleanest for "is it accepted"). After decisions release, accepted-paper `venueid` is overwritten to the public venue ID. So `client.get_all_notes(content={'venueid': 'NeurIPS.cc/2025/Conference'})` returns exactly the accepted set. Doesn't tell you Accept-Oral vs Accept-Poster.
2. **`venue` field string parsing** (for acceptance type). The `venue` field is human-readable: `"NeurIPS 2025 poster"`, `"NeurIPS 2025 oral"`, `"NeurIPS 2025 spotlight"`. Useful but venue-specific; needs per-venue parsers.
3. **Decision notes** (for review-text + decision rationale). Fetched via `get_all_notes(invitation=..., details='replies')`, then filter `reply['invitations'][0].endswith('Decision')` and read `reply['content']['decision']['value']`. Heavier query, but you get the actual program-chair-set decision string.

For NeurIPS 2025 specifically, all three work. For `confos`, **build on (1) for the accepted-list query, augment with (2) for track type, and only do (3) when the user explicitly asks for review text**.

## 9. Authors

Authors are dual-tracked: `content.authors` (display name strings) and `content.authorids` (identity references). An authorid is **either** a tilde profile ID like `~Yann_LeCun1` **or** a raw email address, depending on whether the author has an OpenReview profile and whether the venue requires one. Profile-id presence is the norm for major venues — ICLR, NeurIPS, ICML require all authors to claim a profile before submission, so >95% of authorids in those venues are tildes.

To fetch profile metadata, the cleanest path is `openreview.tools.get_profiles(client, ids_or_emails)` — it handles batching and falls back gracefully on missing profiles. The Profile object exposes `id`, `state`, `content.names`, `content.emails`, `content.history` (career), `content.expertise`, `content.dblp`, `content.gscholar`, `content.homepage`, sometimes `content.orcid`. Profiles can also have **multiple tilde IDs** if a user has merged accounts — store `id` as canonical and treat alternate names as aliases.

What's reliable: preferred name, current institution (`history[0]`). What's messy: middle-name variants, name-change history (especially Chinese name romanizations), the merge graph. What's missing for many authors: ORCID, structured affiliation country.

## 10. Affiliations, Orgs, Countries

**Affiliations are free-text.** The Profile `history` array stores `{"institution": {"name": "...", "domain": "..."}, "position": "...", "start": YYYY, "end": YYYY}` per entry. The `domain` subfield (when present) is the school's email domain (`mit.edu`, `stanford.edu`) — much more normalizable than the name string, but only set when the user verified via institutional email.

Realistic expectations for `confos`:
- Name normalization is hard. "MIT", "Massachusetts Institute of Technology", "MIT CSAIL", "M.I.T." all appear and refer to one place
- Email domain (`history[i].institution.domain`) is your best bet for clean grouping — supplement with a hand-curated alias list for top-200 orgs
- Country is essentially absent from the profile schema. You either infer from domain TLD/registry, geolocate the institution, or skip
- About 10-15% of authors will have no profile at all (anonymous emails, unconfirmed accounts) — these have *no* affiliation data

If `confos` wants org-level stats, plan to ship a curated normalization table (start with top universities, FAANG, top AI labs) and treat the rest as "Other / Unknown." Don't try to be exhaustive on day one — it's a long tail.

## 11. PDFs

Submission notes carry `content.pdf.value` — a path like `/pdf/abc123.pdf`. The full URL is `https://openreview.net/pdf?id=<note_id>` (preferred, stable) or `https://openreview.net{content.pdf.value}` (also works). Both are publicly accessible for accepted papers without auth. Caveats:

- **Withdrawn submissions** often have the PDF deleted or access-restricted to authors/reviewers — expect 403s
- **Under-review papers** may be public or anonymized depending on venue policy (NeurIPS 2025 is open-review for accepted, closed for under-review until acceptance)
- **Desk-rejected** papers are usually private
- File sizes can be 5-50MB — if downloading, stream and respect bandwidth

The client also exposes `client.get_pdf(id)` which returns bytes. For `confos`, store the URL only; download lazily on demand.

## 12. PMLR Fallback

ICML proceedings are **dual-published**: OpenReview is the official submission/review platform, and PMLR (Proceedings of Machine Learning Research) is the formal archival publication. For ICML 2024 specifically, the final proceedings volume is PMLR v235 (published July 2024); ICML 2025 will land as a subsequent PMLR volume.

The substantive difference for a metadata tool:
- **OpenReview** has the full process metadata (submissions, reviews, rebuttals, decisions, withdrawal history, decision rationale)
- **PMLR** has the final canonical paper records (final PDF, BibTeX, official citation, author order) for *accepted* papers only

For `confos`, OpenReview is the right primary source — it covers more (the rejected/withdrawn longtail is interesting for stats) and the schema is queryable via API. PMLR has no comparable API; you'd scrape HTML. The known data-coverage gap: a small number of ICML papers historically had PDF-only-on-PMLR after acceptance (the OpenReview PDF was an earlier version). For 2024+ this gap is mostly closed. If you want canonical post-publication PDFs, plan a PMLR cross-link step later. NeurIPS proceedings flow through proceedings.neurips.cc rather than PMLR but the same principle applies.

## 13. Library Specifics — Concrete Code

What a `confos` ingest call looks like in practice:

```python
import openreview
import os

client = openreview.api.OpenReviewClient(
    baseurl='https://api2.openreview.net',
    # anonymous by default; honors OPENREVIEW_USERNAME / OPENREVIEW_PASSWORD env vars
    username=os.environ.get('OPENREVIEW_USERNAME'),
    password=os.environ.get('OPENREVIEW_PASSWORD'),
)

venue_id = 'NeurIPS.cc/2025/Conference'
venue_group = client.get_group(venue_id)
submission_name = venue_group.content['submission_name']['value']  # 'Submission'

# Resume cursor: max tcdate we've ingested
last_tcdate = 1_715_000_000_000  # ms epoch, from local DB

# All new submissions since last_tcdate, paginated for us
submissions = client.get_all_notes(
    invitation=f'{venue_id}/-/{submission_name}',
    mintcdate=last_tcdate + 1,
    details='replies',  # inline reviews/decisions in details['replies']
    sort='tcdate:asc',
)

for note in submissions:
    title    = (note.content.get('title')    or {}).get('value')
    abstract = (note.content.get('abstract') or {}).get('value')
    authors  = (note.content.get('authors')  or {}).get('value', [])
    aids     = (note.content.get('authorids') or {}).get('value', [])
    pdf_path = (note.content.get('pdf')      or {}).get('value')
    venueid  = (note.content.get('venueid')  or {}).get('value')

    is_accepted = (venueid == venue_id)
    decisions = [
        r for r in (note.details or {}).get('replies', [])
        if any(inv.endswith('Decision') for inv in r['invitations'])
    ]
    decision_str = (
        decisions[0].get('content', {}).get('decision', {}).get('value')
        if decisions else None
    )

    # ... upsert into SQLite ...

# Catch edits to already-seen notes (no mintmdate on notes endpoint, sadly)
# Use sort='tmdate:desc' and short-circuit when you hit an unchanged tmdate
```

The `submission_name`-from-group-content pattern is the canonical way; don't hard-code `/-/Submission` because some venues use `Blind_Submission`, `Paper_Submission`, etc.

## 14. Known Issues and Gotchas

A grab-bag of things that bite new builders:

- **Venue convention churn.** NeurIPS 2022 used a different submission invitation name than 2023, and 2023 vs 2024 changed again. Always read `submission_name` from the venue group; never hard-code.
- **`venueid` rewrite timing.** Between paper-submission and decision-release, `venueid` points to the under-review bucket (e.g. `NeurIPS.cc/2025/Conference/Submission`). After decisions, accepted papers get rewritten to the public venue. So a stale ingest can mis-tag papers as "unaccepted." Re-sync after each conference's decision release.
- **Withdrawn vs desk-rejected vs rejected.** Each is a distinct `venueid` bucket on most venues, with names like `.../Withdrawn_Submission` and `.../Desk_Rejected_Submission`. Read them from the venue group's content (`withdrawn_venue_id`, `desk_rejected_venue_id` keys when they exist) — they're documented in the group's metadata but not standardized across venues.
- **Replies invitation patterns.** Per-paper invitations look like `<venue>/Submission<N>/-/Official_Review`, `<venue>/Submission<N>/-/Decision`, `<venue>/Submission<N>/-/Rebuttal`. Filter by `endswith('Decision')` etc. rather than full-string match.
- **v2.0.0 (April 2026) was a breaking-changes release.** Removed deprecated code, removed numpy dependency, shifted templates. If you pin a version, pin to ≥2.0.0; the older 1.x line still works against the same server but has different method names in a few places.
- **`mintmdate` is not on `/notes`.** This is the big incremental-sync sharp edge — see section 6.
- **Anonymous reviewer identity leakage.** OpenReview had a public-disclosed bug in 2025 where `/profiles/search` could de-anonymize reviewers; patched. Treat reviewer-side endpoints as security-sensitive and don't store reviewer→profile mappings even when accessible.
- **Profile merges.** A single human can have multiple tilde IDs (`~John_Smith1`, `~J_Smith3`) that have been merged. The Profile API returns one canonical record with merge history. If you index by tilde naively you'll double-count authors.
- **`content` is wrapped under v2 but flat under v1.** Code that works on v1 silently returns `None` when run against v2 if you forget to unwrap `{'value': ...}`.
- **Empty `details`.** If you pass `details='replies'` but the venue hasn't released reviews/decisions yet, you get `details={'replies': []}`, not an error. Don't treat empty replies as "no decision exists" — re-sync later.

## 15. Recent Activity (2025-2026)

- **v2.0.0 cut 2026-04-02**: deliberate breaking changes, removed deprecated code, dropped numpy dependency
- **v2.1.0 (2026-04-15)**: added "MCP-friendly docstrings" — the library is being prepped for LLM tool-calling agents; relevant because `confos` essentially is an LLM-targeted reference DB
- **v2.2.0 (2026-04-28)**: DBLP integration with author schema migration (richer publication cross-linking), Docker Compose setup for integration tests, Senior Area Chair role support in venue UI
- **Active issue count**: 322 open issues on the repo — high churn, but releases are regular (every 2-4 weeks). Pin your version.
- **No deprecations of read methods** in the v2.x line; the v2 API surface for note retrieval is stable
- **Security**: 2025 disclosure of unauthenticated profile-search leak; patched. No knock-on rate-limit changes that affect anonymous reads of notes

---

## Addendum — Profile fetch, verified live (2026-06-02, Enrichment Phase 1)

§9/§10 above recommended `openreview.tools.get_profiles(client, ids)` as the clean batched
path. **That is wrong for anonymous clients.** Verified against the live API on 2026-06-02:

- **Batched `client.search_profiles(ids=…)` (which `tools.get_profiles` calls) returns
  HTTP 403 `ForbiddenError` for a guest** ("You must be logged in to access this resource").
  This is the post-2025-disclosure lockdown of `/profiles/search` (see §14). So the batched
  path needs credentials.
- **Per-profile `client.get_profile("~Handle1")` works anonymously.** It returns the full
  profile with `content.history[].institution {name, domain, country}` (country is an
  explicit **ISO 3166-1 alpha-2** code, e.g. `US`/`GB`/`CN` — map it to a display name),
  plus `homepage`, `gscholar`, `dblp`, `expertise[].keywords`, `names`, `relations`. The
  current institution is the `history` entry with `end == null` (else the most recent).
- A handle with no public profile raises `OpenReviewException(['Profile Not Found'])` —
  distinct from a transient HTTP/throttle error. confos records the former (won't re-fetch)
  but **not** the latter (a resume retries it).
- **`/profiles` is rate-limited to ~20 requests/min per IP** (HTTP 429 `RateLimitError`,
  `{limit: 20, resetTime: <~60s out>}`). It's a *total* cap, so concurrency doesn't beat it —
  measured 8 workers @ 0.33/s vs sequential @ 0.39/s (concurrency was slightly slower, all
  429 churn). confos fetches **sequentially** and lets the client's built-in 429-retry
  self-pace; the whole pass is resumable (snapshot to `raw/<venue>/profiles.jsonl`). A large
  venue (~23k authors) is therefore a multi-hour, run-it-incrementally backfill.
- Anonymous reads **redact email local-parts** (`****@domain`), so emails aren't harvestable;
  confos doesn't store them anyway (it keeps only history/links/expertise).

**confos implementation:** `OpenReviewAdapter.fetch_profile(s)` + `services/enrich.py` +
`confos enrich profiles --venue <slug>`. See DECISIONS D24.

## Practical Takeaways for `confos`

- Target API v2, anonymous-by-default
- Sync via `mintcdate` + `sort='tmdate:desc'` for incrementals (no `mintmdate` on notes endpoint)
- Use `venueid` filter for the accepted-papers query
- Paginate at `limit=1000` (server cap); the client handles cursoring
- Ship a curated venue-alias map and an org-normalization table — OpenReview itself is freeform on both
- Pin `openreview-py>=2.0.0`; v2.0.0 was a breaking release just last month

## Sources

- [openreview-py GitHub repo](https://github.com/openreview/openreview-py)
- [openreview-py releases](https://github.com/openreview/openreview-py/releases)
- [client.py source — OpenReviewClient class](https://github.com/openreview/openreview-py/blob/master/openreview/api/client.py)
- [openreview-py docs (readthedocs)](https://openreview-py.readthedocs.io/en/latest/)
- [Package documentation — Python Client](https://openreview-py.readthedocs.io/en/latest/api.html)
- [OpenReview documentation home](https://docs.openreview.net/)
- [Using the API](https://docs.openreview.net/getting-started/using-the-api)
- [Installing and instantiating the Python client](https://docs.openreview.net/getting-started/using-the-api/installing-and-instantiating-the-python-client)
- [llms-full.txt corpus](https://docs.openreview.net/llms-full.txt)
- [How to Get all Notes (submissions, reviews, rebuttals, etc.)](https://docs.openreview.net/how-to-guides/data-retrieval-and-modification/how-to-get-all-notes-for-submissions-reviews-rebuttals-etc)
- [How do I find a venue id?](https://docs.openreview.net/getting-started/frequently-asked-questions/how-do-i-find-a-venue-id)
- [Introduction to Notes](https://docs.openreview.net/getting-started/objects-in-openreview/introduction-to-notes)
- [Note entity fields reference](https://docs.openreview.net/reference/api-v2/entities/note/fields)
- [Default Submission Form](https://docs.openreview.net/reference/default-forms/default-submission-form)
- [Loop through accepted papers and print authors/affiliations](https://docs.openreview.net/how-to-guides/data-retrieval-and-modification/how-to-loop-through-accepted-papers-and-print-the-authors-and-their-affiliations)
- [Introduction to Profiles](https://docs.openreview.net/getting-started/objects-in-openreview/introduction-to-profiles)
- [OpenAPI definition (API v2)](https://docs.openreview.net/reference/api-v2/openapi-definition)
- [OpenReview public venues directory](https://openreview.net/venues)
- [NeurIPS 2025 Conference venue](https://openreview.net/group?id=NeurIPS.cc%2F2025%2FConference)
- [ICML 2025 Conference venue](https://openreview.net/group?id=ICML.cc%2F2025%2FConference)
- [COLM 2024 Conference venue](https://openreview.net/group?id=colmweb.org%2FCOLM%2F2024%2FConference)
- [PMLR v235 — ICML 2024 proceedings](https://github.com/mlresearch/v235)
- [OpenReview API anonymous-search bug disclosure (2025)](https://www.ctol.digital/news/openreview-api-bug-exposed-anonymous-peer-reviewers-academic-publishing-crisis/)
