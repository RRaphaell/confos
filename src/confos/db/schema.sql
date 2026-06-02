-- confos SQLite schema (ARCHITECTURE §6).
--
-- This is the COMPLETE v1 schema, applied once at `init` and gated by
-- PRAGMA user_version (db/migrate.py). The raw JSONL snapshots under
-- raw/<source>/<venue>/ are the source of truth; everything here is a derived,
-- rebuildable index. The FTS5 tables at the bottom are dropped + rebuilt by
-- `confos index rebuild`.
--
-- Identity rules (D5): papers.id IS the OpenReview note id; authors.id is the
-- profile id, else email:<addr>, else name:<slug>#<n>. No surrogate autoincrement
-- keys on entities an agent might round-trip.
--
-- Foreign-key enforcement is per-connection and is owned by db/connection.connect()
-- (a `PRAGMA foreign_keys=ON` here would be a no-op inside executescript). Every
-- CREATE uses IF NOT EXISTS so a re-run after a partially-applied schema completes
-- cleanly and `init` stays idempotent (D13).

-- ---------------------------------------------------------------------------
-- Core entities
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS venues (
    slug                  TEXT PRIMARY KEY,        -- user handle, e.g. 'neurips-2025'
    source                TEXT NOT NULL,           -- adapter name, e.g. 'openreview'
    source_venue_id       TEXT NOT NULL,           -- e.g. 'NeurIPS.cc/2025/Conference'
    published_venueid     TEXT,                    -- venueid value that marks 'accepted'
    submission_venueid    TEXT,                    -- under-review bucket (marks 'under_review')
    withdrawn_venueid     TEXT,
    desk_rejected_venueid TEXT,
    submission_name       TEXT,                    -- e.g. 'Submission' (read from group)
    display_name          TEXT,                    -- e.g. 'NeurIPS 2025'
    year                  INTEGER,
    url                   TEXT,
    last_ingested_at      TEXT
);

CREATE TABLE IF NOT EXISTS papers (
    id              TEXT PRIMARY KEY,              -- OpenReview note id (== public id, D5)
    venue_slug      TEXT NOT NULL REFERENCES venues(slug) ON DELETE CASCADE,
    number          INTEGER,                       -- paper number within the venue
    title           TEXT NOT NULL DEFAULT '',
    abstract        TEXT NOT NULL DEFAULT '',
    tldr            TEXT,
    keywords_json   TEXT NOT NULL DEFAULT '[]',    -- JSON array of raw keywords
    primary_area    TEXT,
    status          TEXT NOT NULL DEFAULT 'unknown', -- accepted|under_review|withdrawn|desk_rejected|rejected|unknown
    acceptance_type TEXT,                          -- oral|spotlight|poster|null
    raw_venueid     TEXT,                          -- the note's content.venueid value
    venue_string    TEXT,                          -- human 'NeurIPS 2025 poster'
    url             TEXT NOT NULL,
    pdf_url         TEXT,                          -- absolute link to the PDF, or NULL
    bibtex          TEXT,                          -- the note's _bibtex citation block
    supplementary_url TEXT,                        -- absolute link to supplementary material
    pdate           INTEGER,                       -- publication date (ms epoch) if present
    tcdate          INTEGER,                       -- true creation date (ms epoch)
    tmdate          INTEGER,                       -- true modification date (ms epoch)
    -- Review aggregates (Phase 2; populated when reviews are ingested, else 0/NULL).
    review_count    INTEGER NOT NULL DEFAULT 0,    -- number of Official_Reviews
    rating_mean     REAL,                          -- mean review rating (scale varies by venue)
    rating_std      REAL,                          -- population std of ratings (= controversy)
    confidence_mean REAL,                          -- mean reviewer confidence
    decision        TEXT,                          -- the Decision verdict, e.g. 'Accept (poster)'
    created_at      TEXT NOT NULL,                 -- when confos first ingested it
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_papers_venue ON papers(venue_slug);
CREATE INDEX IF NOT EXISTS idx_papers_status ON papers(venue_slug, status);

CREATE TABLE IF NOT EXISTS authors (
    id                  TEXT PRIMARY KEY,          -- profile id | email:<addr> | name:<slug>#<n> (D5)
    profile_id          TEXT,                      -- the ~Tilde_Id when present, else NULL
    display_name        TEXT NOT NULL,
    aliases_json        TEXT NOT NULL DEFAULT '[]',
    affiliation_current TEXT,                      -- normalized org name, or NULL
    affiliation_country TEXT,                      -- normalized country, or NULL
    data_quality        TEXT NOT NULL DEFAULT 'resolved', -- resolved|low|unresolved
    profile_url         TEXT,
    homepage            TEXT,                      -- personal/lab homepage (from profile)
    gscholar            TEXT,                      -- Google Scholar profile URL
    dblp                TEXT,                      -- DBLP author URL
    expertise_json      TEXT NOT NULL DEFAULT '[]' -- JSON array of self-declared expertise keywords
);

CREATE TABLE IF NOT EXISTS paper_authors (
    paper_id  TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    author_id TEXT NOT NULL REFERENCES authors(id) ON DELETE CASCADE,
    position  INTEGER NOT NULL,                    -- 0-based author order
    raw_name  TEXT NOT NULL,                       -- display name as it appeared (order preserved, S6)
    PRIMARY KEY (paper_id, author_id)
);
CREATE INDEX IF NOT EXISTS idx_paper_authors_author ON paper_authors(author_id);

CREATE TABLE IF NOT EXISTS orgs (
    id              TEXT PRIMARY KEY,              -- slug of normalized_name
    name            TEXT NOT NULL,                 -- display name
    normalized_name TEXT NOT NULL,
    country         TEXT,
    aliases_json    TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS author_affiliations (
    author_id  TEXT NOT NULL REFERENCES authors(id) ON DELETE CASCADE,
    org_id     TEXT NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    start_year INTEGER,
    end_year   INTEGER,
    confidence TEXT,                               -- high|low
    PRIMARY KEY (author_id, org_id)
);

CREATE TABLE IF NOT EXISTS paper_topics (
    paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    topic    TEXT NOT NULL,                        -- normalized keyword
    source   TEXT NOT NULL,                        -- where the topic came from (e.g. 'keyword')
    PRIMARY KEY (paper_id, topic)
);
CREATE INDEX IF NOT EXISTS idx_paper_topics_topic ON paper_topics(topic);

-- Per-review rows (Phase 2; derived from raw details.replies, rebuilt with papers). Reviewer
-- identities are anonymous — reviewer_key is an opaque signature segment, never a profile.
CREATE TABLE IF NOT EXISTS reviews (
    paper_id        TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    reviewer_key    TEXT NOT NULL,                 -- opaque anonymous reviewer signature segment
    rating          INTEGER,                       -- leading int of the rating (scale varies)
    confidence      INTEGER,
    sub_scores_json TEXT NOT NULL DEFAULT '{}',    -- {field: int} numeric sub-scores
    raw_rating      TEXT,                          -- the rating field verbatim (provenance)
    PRIMARY KEY (paper_id, reviewer_key)
);
CREATE INDEX IF NOT EXISTS idx_reviews_paper ON reviews(paper_id);

CREATE TABLE IF NOT EXISTS ingest_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    venue_slug    TEXT NOT NULL REFERENCES venues(slug) ON DELETE CASCADE,
    status        TEXT NOT NULL,                   -- ok|partial|error
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    items_seen    INTEGER NOT NULL DEFAULT 0,
    items_added   INTEGER NOT NULL DEFAULT 0,
    items_updated INTEGER NOT NULL DEFAULT 0,
    max_tcdate    INTEGER,                          -- watermark: newest tcdate ingested (S1)
    max_tmdate    INTEGER,                          -- watermark: newest tmdate ingested (S1)
    error         TEXT
);
CREATE INDEX IF NOT EXISTS idx_ingest_runs_venue ON ingest_runs(venue_slug);

-- ---------------------------------------------------------------------------
-- FTS5 (derived, rebuildable — dropped + rebuilt by `index rebuild`)
-- ---------------------------------------------------------------------------

CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
    paper_id UNINDEXED,
    title,
    abstract,
    keywords,
    author_names,
    org_names,
    tokenize = 'unicode61 remove_diacritics 2'
);

CREATE VIRTUAL TABLE IF NOT EXISTS authors_fts USING fts5(
    author_id UNINDEXED,
    name,
    aliases,
    affiliations,
    topics,
    tokenize = 'unicode61 remove_diacritics 2'
);

CREATE VIRTUAL TABLE IF NOT EXISTS orgs_fts USING fts5(
    org_id UNINDEXED,
    name,
    aliases,
    country,
    tokenize = 'unicode61 remove_diacritics 2'
);
