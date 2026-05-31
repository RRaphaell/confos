# Changelog

All notable changes to confos are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); versions follow SemVer.

## [Unreleased]

### Added
- **Phase 0 — Foundation.** Python/uv package scaffold; typer CLI with the full command
  tree (`init`, `doctor`, and stubbed groups for later phases); global flag handling that
  works before *and* after the subcommand; strict stdout/stderr split with a stable
  versioned JSON envelope; SQLite schema + apply-once migration with FTS5; `init` creates
  the `~/.confos` store; `doctor` checks env/DB/FTS5; GitHub Actions CI (ruff + mypy +
  pytest); unit + integration tests.

### Project setup
- Blueprint complete: product spec, architecture, CLI contract, ranking/topic spec, JSON
  schemas, build plan, references, agent docs.
