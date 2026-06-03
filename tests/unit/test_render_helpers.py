"""Human-output visual layer (VISUAL.md) + limit resolution: capability resolvers, the
colour theme, and the pure render helpers — protecting the one invariant that matters,
that richness never leaks into a no-colour / non-Unicode stream.
"""

from __future__ import annotations

import pytest

from confos.commands._render import resolve_limit
from confos.console import build_consoles, confos_theme, should_use_unicode


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


def test_resolve_limit_precedence() -> None:
    assert resolve_limit(5, 20, 50) == 5  # command flag wins
    assert resolve_limit(None, 30, 50) == 30  # falls back to root --limit
    assert resolve_limit(None, None, 50) == 50  # default
    assert resolve_limit(0, 20, 50) == 0  # explicit 0 is honoured (not falsy-skipped)
