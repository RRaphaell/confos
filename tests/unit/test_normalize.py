"""Pure normalization helpers: topics, orgs, countries (RANKING §1 / research §10)."""

from __future__ import annotations

from confos.normalize.countries import country_from_domain
from confos.normalize.orgs import domain_from_email, org_from_email, org_slug
from confos.normalize.topics import normalize_keywords, normalize_topic


def test_normalize_topic_lowercases_and_collapses() -> None:
    assert normalize_topic("  LLM   Agents ") == "llm agents"
    assert normalize_topic("") == ""


def test_normalize_keywords_dedup_and_alias() -> None:
    topics = normalize_keywords(["LLM Agents", "llm  agents", "Memory", ""])
    assert topics == ["llm agents", "memory"]
    aliased = normalize_keywords(["evals"], aliases={"evals": "evaluation"})
    assert aliased == ["evaluation"]


def test_domain_and_country() -> None:
    assert domain_from_email("a@MIT.edu") == "mit.edu"
    assert domain_from_email("not-an-email") is None
    assert country_from_domain("mit.edu") == "United States"
    assert country_from_domain("ox.ac.uk") == "United Kingdom"
    assert country_from_domain("example.com") is None  # ambiguous TLD


def test_org_from_email_seed_and_fallback() -> None:
    assert org_from_email("alice@mit.edu") == ("MIT", "United States")
    # Unknown domain → derived name + TLD-inferred country (None for .com).
    name, _country = org_from_email("x@acme-research.com") or ("", None)
    assert name  # some readable name was derived
    assert org_from_email("no-domain") is None


def test_org_slug() -> None:
    assert org_slug("Google DeepMind") == "google-deepmind"
    assert org_slug("UC Berkeley") == "uc-berkeley"
