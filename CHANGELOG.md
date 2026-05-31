# Changelog

All notable changes to confos are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); versions follow SemVer.

## [Unreleased]

### Added
- **Phase 2 — Search & explore.** `confos papers search` (FTS5/bm25, ranked + cited,
  filters: `--venue`/`--year`/`--org`/`--accepted-only`/`--limit`), `papers show`
  (+authors, `--with related`), `papers related`. `confos authors search/show/papers`
  and `confos orgs top/papers`. `confos index rebuild` re-derives the whole index from
  the raw JSONL snapshots offline (sync watermarks preserved) and `index status` reports
  row counts. All offline, deterministic, with the stable JSON envelope.
- **Phase 1 — Ingest (OpenReview).** `confos ingest <venue>` pulls a venue's full
  submission set, snapshots raw JSONL (the source of truth), normalizes, and upserts into
  SQLite + FTS in one transaction; status (accepted/under_review/withdrawn/desk_rejected)
  is derived locally from each note's raw venueid. Incremental re-runs use a hybrid
  watermark (new submissions by creation date + edited notes by modify date, so
  post-decision status flips are caught); `--force` re-pulls, `--dry-run` reports counts,
  partial failures exit 5. New `confos venues` group: list / search (network) / show / add
  / aliases, with a built-in alias map for major venues. Author identity follows OpenReview
  profile ids (else email / unresolved name), never merged across papers by name.
- **Phase 0 — Foundation.** Python/uv package scaffold; typer CLI with the full command
  tree (`init`, `doctor`, and stubbed groups for later phases); global flag handling that
  works before *and* after the subcommand; strict stdout/stderr split with a stable
  versioned JSON envelope; SQLite schema + apply-once migration with FTS5; `init` creates
  the `~/.confos` store; `doctor` checks env/DB/FTS5; GitHub Actions CI (ruff + mypy +
  pytest); unit + integration tests.

### Project setup
- Blueprint complete: product spec, architecture, CLI contract, ranking/topic spec, JSON
  schemas, build plan, references, agent docs.
