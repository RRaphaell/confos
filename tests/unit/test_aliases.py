"""User-editable alias files (topics / orgs / countries) — load + apply."""

from __future__ import annotations

from pathlib import Path

from confos.aliases import load_normalize_aliases, load_topic_aliases
from confos.normalize.orgs import org_from_email
from confos.paths import Paths


def _paths(tmp_path: Path) -> Paths:
    paths = Paths(home=tmp_path / "store")
    paths.ensure()
    return paths


def test_missing_files_are_empty(tmp_path: Path) -> None:
    paths = Paths(home=tmp_path / "nope")  # not even created
    assert load_topic_aliases(paths) == {}
    aliases = load_normalize_aliases(paths)
    assert aliases.orgs == {} and aliases.countries == {}


def test_load_topic_aliases_list_and_csv(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.alias_file("topics.yml").write_text(
        "evals: [evals, evaluation, benchmark]\nagents: agents, agent\n", encoding="utf-8"
    )
    aliases = load_topic_aliases(paths)
    assert aliases["evals"] == ["evals", "evaluation", "benchmark"]
    assert aliases["agents"] == ["agents", "agent"]  # comma-string form


def test_load_normalize_aliases(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.alias_file("orgs.yml").write_text('"acme.com": "Acme Corp"\n', encoding="utf-8")
    paths.alias_file("countries.yml").write_text('"acme.com": "Wonderland"\n', encoding="utf-8")
    aliases = load_normalize_aliases(paths)
    assert aliases.orgs["acme.com"] == "Acme Corp"
    assert aliases.countries["acme.com"] == "Wonderland"


def test_org_from_email_prefers_user_alias() -> None:
    name, country = org_from_email(
        "x@acme.com",
        org_aliases={"acme.com": "Acme Corp"},
        country_aliases={"acme.com": "Wonderland"},
    ) or ("", None)
    assert name == "Acme Corp"
    assert country == "Wonderland"


def test_malformed_alias_file_is_empty(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.alias_file("topics.yml").write_text("::: not valid yaml :::", encoding="utf-8")
    assert load_topic_aliases(paths) == {}
