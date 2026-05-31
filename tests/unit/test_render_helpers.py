"""Limit resolution: command flag > root --limit > default, honouring an explicit 0."""

from __future__ import annotations

from confos.commands._render import resolve_limit


def test_resolve_limit_precedence() -> None:
    assert resolve_limit(5, 20, 50) == 5  # command flag wins
    assert resolve_limit(None, 30, 50) == 30  # falls back to root --limit
    assert resolve_limit(None, None, 50) == 50  # default
    assert resolve_limit(0, 20, 50) == 0  # explicit 0 is honoured (not falsy-skipped)
