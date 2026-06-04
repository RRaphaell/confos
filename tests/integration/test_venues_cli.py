"""venues command (offline paths): aliases / add / list / show."""

from __future__ import annotations

from tests.conftest import RunCli


def test_aliases_json_lists_builtin_map(run_cli: RunCli) -> None:
    result = run_cli("venues", "aliases", "--json")
    assert result.exit_code == 0
    data = result.json()["data"]
    assert data["neurips-2025"] == "NeurIPS.cc/2025/Conference"


def test_list_empty_then_after_add(run_cli: RunCli) -> None:
    empty = run_cli("venues", "list", "--json")
    assert empty.exit_code == 0
    assert empty.json()["data"] == []

    added = run_cli(
        "venues", "add", "--slug", "myws", "--openreview-id", "Foo.cc/2025/Workshop", "--json"
    )
    assert added.exit_code == 0
    assert added.json()["data"]["source_venue_id"] == "Foo.cc/2025/Workshop"

    listed = run_cli("venues", "list", "--json")
    slugs = {v["slug"] for v in listed.json()["data"]}
    assert "myws" in slugs


def test_show_known_alias_when_not_ingested(run_cli: RunCli) -> None:
    result = run_cli("venues", "show", "neurips-2025", "--json")
    assert result.exit_code == 0
    assert result.json()["data"]["source_venue_id"] == "NeurIPS.cc/2025/Conference"


def test_show_unknown_is_error(run_cli: RunCli) -> None:
    result = run_cli("venues", "show", "no-such-venue", "--json")
    assert result.exit_code == 1
    payload = result.json()
    assert payload["ok"] is False
    assert payload["error"]["type"] == "not_found"


def test_add_rejects_non_openreview_id(run_cli: RunCli) -> None:
    result = run_cli("venues", "add", "--slug", "x", "--openreview-id", "notanid", "--json")
    assert result.exit_code == 2
    assert result.json()["error"]["type"] == "usage"


def test_search_has_a_real_limit_option(run_cli: RunCli) -> None:
    # P1-9: the documented `venues search ... --limit 5` must be a real option. Proven offline
    # by feeding a bad value: a defined option fails as an INVALID VALUE during parsing (before
    # any network), whereas an undefined one would fail as "No such option".
    result = run_cli("venues", "search", "q", "--limit", "notanint", "--json")
    assert result.exit_code == 2
    message = result.json()["error"]["message"].lower()
    assert "no such option" not in message  # --limit is recognised…
    assert "limit" in message  # …it's the value that's rejected
