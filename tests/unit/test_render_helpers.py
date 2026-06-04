"""Human-output visual layer (VISUAL.md) + limit resolution: capability resolvers, the
colour theme, and the pure render helpers — protecting the one invariant that matters,
that richness never leaks into a no-colour / non-Unicode stream.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from rich.console import Console

from confos.commands._render import render_rated_papers, resolve_limit
from confos.config import Config
from confos.console import AppContext, OutputMode, build_consoles, confos_theme, should_use_unicode
from confos.errors import UsageError
from confos.output.progress import spinner
from confos.paths import Paths


def _human_ctx(width: int) -> AppContext:
    """A minimal human-mode AppContext whose stdout Console has a fixed width."""
    out = Console(width=width, no_color=True, highlight=False, soft_wrap=False)
    err = Console(width=width, stderr=True, no_color=True)
    return AppContext(
        mode=OutputMode.HUMAN,
        quiet=False,
        verbose=0,
        no_input=False,
        use_color=False,
        use_unicode=True,
        supports_hyperlinks=False,
        paths=Paths(home=Path("/tmp/confos-render-test")),
        config=Config(),
        venue=None,
        limit=None,
        out=out,
        err=err,
    )


class _Stream:
    """Minimal stand-in for a text stream with a known encoding."""

    def __init__(self, encoding: str | None) -> None:
        self.encoding = encoding


def test_should_use_unicode_true_on_utf8(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CONFOS_ASCII", raising=False)
    monkeypatch.delenv("TERM", raising=False)
    assert should_use_unicode(stream=_Stream("utf-8")) is True


def test_should_use_unicode_false_on_dumb_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CONFOS_ASCII", raising=False)
    monkeypatch.setenv("TERM", "dumb")
    assert should_use_unicode(stream=_Stream("utf-8")) is False


def test_should_use_unicode_opt_out_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TERM", raising=False)
    monkeypatch.setenv("CONFOS_ASCII", "1")
    assert should_use_unicode(stream=_Stream("utf-8")) is False


def test_should_use_unicode_false_on_non_utf8(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CONFOS_ASCII", raising=False)
    monkeypatch.delenv("TERM", raising=False)
    assert should_use_unicode(stream=_Stream("ascii")) is False
    assert should_use_unicode(stream=_Stream(None)) is False


def test_theme_collapses_to_plain_without_colour() -> None:
    # A themed style must render with ZERO ansi escapes when colour is off — the core
    # invariant that lets us scatter [status.*]/[dq.*] markup safely.
    out, _ = build_consoles(use_color=False)
    with out.capture() as cap:
        out.print("[status.oral]oral[/] [dq.high]high[/]")
    text = cap.get()
    assert "\x1b" not in text
    assert "oral" in text and "high" in text


def test_theme_defines_the_expected_vocabulary() -> None:
    theme = confos_theme()
    for name in ("status.oral", "status.rejected", "dq.high", "score.hi", "confos.accent"):
        assert name in theme.styles


def test_spinner_noop_when_disabled_writes_nothing() -> None:
    # The disabled path is the contract-critical one: non-TTY / --quiet / --json must emit
    # nothing, so scripted ingest output stays byte-identical.
    _, err = build_consoles(use_color=True)
    with err.capture() as cap, spinner(err, "working", enabled=False):
        pass
    assert cap.get() == ""


def test_bar_chart_themed_and_ascii_degradable() -> None:
    from confos.output.table import bar_chart

    out, _ = build_consoles(use_color=False)
    with out.capture() as cap:
        bar_chart(out, [("agents", 10), ("evals", 4)], title="Top topics")
    text = cap.get()
    assert "\x1b" not in text  # no colour leaks when colour is off
    assert "█" in text  # eighth-block bars by default
    with out.capture() as cap2:
        bar_chart(out, [("agents", 10)], unicode=False)
    ascii_out = cap2.get()
    assert "#" in ascii_out and "█" not in ascii_out


def test_resolve_limit_precedence() -> None:
    assert resolve_limit(5, 20, 50) == 5  # command flag wins
    assert resolve_limit(None, 30, 50) == 30  # falls back to root --limit
    assert resolve_limit(None, None, 50) == 50  # default
    assert resolve_limit(0, 20, 50) == 0  # explicit 0 is honoured (not falsy-skipped)


def test_resolve_limit_rejects_negative() -> None:
    # A negative LIMIT is "unbounded" in SQLite, so it must be rejected at this funnel —
    # whether it arrives via the command flag or the root --limit.
    with pytest.raises(UsageError):
        resolve_limit(-1, None, 50)
    with pytest.raises(UsageError):
        resolve_limit(None, -5, 50)


def test_result_tables_keep_short_columns_at_normal_width() -> None:
    # Regression (P1-5): a long title used to starve the numeric columns to ~zero width at
    # common terminal widths, because the text columns were no_wrap with no cap. The
    # rating/±std/reviews values must remain visible.
    paper = {
        "paper_id": "x1",
        "venue": "neurips-2025",
        "title": "A very long paper title that would devour the whole row when uncapped " * 2,
        "authors": [{"name": "Ada Lovelace"}, {"name": "Alan Turing"}],
        "rating_mean": 7.5,
        "rating_std": 1.25,
        "review_count": 4,
    }
    ctx = _human_ctx(width=100)
    with ctx.out.capture() as cap:
        render_rated_papers(ctx, [paper])
    text = cap.get()
    assert "7.50" in text  # rating column survived
    assert "1.25" in text  # ±std column survived
    assert "4" in text  # reviews column survived
