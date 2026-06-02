"""Output-contract descriptions for ``confos schema <command>`` (AGENTS.md discovery).

Each entry documents the stable ``--json`` shape for a command: the envelope is always
the standard one (SCHEMAS §1); ``data`` is described as a field→type map. These are
hand-maintained against docs/SCHEMAS.md + RANKING.md (the canonical specs). Field names
are the contract; types are descriptive (not a formal JSON-Schema validator).
"""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "1"

_ENVELOPE = {
    "ok": "bool",
    "schema_version": "string",
    "command": "string",
    "query": "object (echo of resolved args)",
    "data": "see 'data' below",
    "warnings": "string[]",
    "provenance": {
        "db": "string",
        "sources": "string[]",
        "venue": "string?",
        "generated_at": "iso8601",
    },
}

_PAPER = {
    "paper_id": "string (OpenReview note id)",
    "title": "string",
    "abstract": "string (present in show + context packs; omitted in list/search views)",
    "authors": "[{author_id, name, position}]",
    "keywords": "string[]",
    "status": "accepted|under_review|withdrawn|desk_rejected|rejected|unknown",
    "acceptance_type": "oral|spotlight|poster|null",
    "venue": "string (slug)",
    "url": "string",
    "pdf_url": "string|null (present in show + `export papers`; omitted in list/search views)",
    "bibtex": "string|null (present in show + `export papers`; omitted in list/search views)",
    "supplementary_url": "string|null (present in show + `export papers`; omitted elsewhere)",
    "bm25": "number (search/find only; bigger = more relevant)",
}

_AUTHOR = {
    "author_id": "string (profile id | email:<addr> | name:<slug>#…)",
    "display_name": "string",
    "affiliation_current": "string ('Unknown' if absent)",
    "affiliation_country": "string|null (profile ISO code → name, else domain heuristic)",
    "data_quality": "resolved|low|unresolved",
    "profile_url": "string|null (OpenReview profile)",
    "homepage": "string|null (from profile enrichment)",
    "gscholar": "string|null (Google Scholar URL, from profile)",
    "dblp": "string|null (DBLP URL, from profile)",
    "expertise": "string[] (self-declared keywords from profile; [] until enriched)",
}

_FOUND_AUTHOR = {
    **_AUTHOR,
    "matched_paper_count": "int",
    "score": "number (4dp)",
    "score_components": {"paper_count": "int", "bm25_sum": "number", "recency_bonus": "number"},
    "why_relevant": "string",
    "matched_papers": "[{paper_id, title, url, bm25}]",
}

_STATS = {
    "rows": "[{key: string, papers: int}]",
    "data_quality": {
        "papers_total": "int",
        "papers_with_signal": "int",
        "unknown": "int",
        "low_confidence": "int",
        "method": "string",
    },
}

_VENUE = {
    "slug": "string",
    "source": "string (e.g. 'openreview')",
    "source_venue_id": "string (e.g. NeurIPS.cc/2025/Conference)",
    "display_name": "string|null",
    "year": "int|null",
    "submission_name": "string|null",
    "last_ingested_at": "iso8601|null (null = registered but not yet ingested)",
    "paper_count": "int",
}

SCHEMAS: dict[str, dict[str, Any]] = {
    "papers.search": {"envelope": _ENVELOPE, "data": [_PAPER]},
    "papers.show": {
        "envelope": _ENVELOPE,
        "data": {**_PAPER, "related": "[Paper] (with --with related)"},
    },
    "papers.related": {"envelope": _ENVELOPE, "data": [_PAPER]},
    "authors.find": {"envelope": _ENVELOPE, "data": [_FOUND_AUTHOR]},
    "authors.search": {"envelope": _ENVELOPE, "data": [{**_AUTHOR, "paper_count": "int"}]},
    "authors.show": {
        "envelope": _ENVELOPE,
        "data": {**_AUTHOR, "paper_count": "int", "venues": "[{venue, papers}]"},
    },
    "authors.papers": {"envelope": _ENVELOPE, "data": {"author": _AUTHOR, "papers": [_PAPER]}},
    "authors.coauthors": {
        "envelope": _ENVELOPE,
        "data": {"author": _AUTHOR, "coauthors": [{**_AUTHOR, "shared_papers": "int"}]},
    },
    "orgs.top": {
        "envelope": _ENVELOPE,
        "data": {"rows": "[{name, country, papers}]", "data_quality": _STATS["data_quality"]},
    },
    "orgs.papers": {
        "envelope": _ENVELOPE,
        "data": {"org": {"name": "string", "country": "string|null"}, "papers": [_PAPER]},
    },
    "stats.overview": {
        "envelope": _ENVELOPE,
        "data": {
            "venue": "string|null",
            "papers": "int",
            "status": "{status: int}",
            "authors": "int",
            "orgs": "int",
            "topics": "int",
            "venues": "int",
        },
    },
    "stats.topics": {"envelope": _ENVELOPE, "data": _STATS},
    "stats.orgs": {"envelope": _ENVELOPE, "data": _STATS},
    "stats.countries": {"envelope": _ENVELOPE, "data": _STATS},
    "trends.topic": {
        "envelope": _ENVELOPE,
        "data": {
            "topic": "string",
            "series": "[{venue, year, matched, total, share, top_authors, top_orgs}]",
            "delta": {"matched_abs": "int", "share_pp": "number"},
        },
    },
    "trends.compare": {"envelope": _ENVELOPE, "data": "same as trends.topic (two venues)"},
    "viz.topics": {"envelope": _ENVELOPE, "data": _STATS},
    "viz.orgs": {"envelope": _ENVELOPE, "data": _STATS},
    "viz.network": {
        "envelope": _ENVELOPE,
        "data": {
            "topic": "string",
            "venue": "string|null",
            "matched_papers": "int (papers the topic matched)",
            "node_count": "int",
            "edge_count": "int",
            "truncated": "bool",
            "nodes": "[{id, label, degree}]",
            "edges": "[[id, id]]",
        },
    },
    "export.context": {
        "envelope": _ENVELOPE,
        "data": {
            "type": "confos.context_pack",
            "topic": "string",
            "venue": "string|null",
            "papers": [_PAPER],
            "authors": [_FOUND_AUTHOR],
            "orgs": "[{name, papers}]",
            "stats": {
                "matched": "int",
                "total": "int",
                "share": "number",
                "by_status": "{status:int}",
            },
            "thin_areas": "string[] (heuristic, labelled)",
            "notes": "string",
        },
    },
    "venues.list": {"envelope": _ENVELOPE, "data": [_VENUE]},
    "venues.search": {
        "envelope": _ENVELOPE,
        "data": "[{slug, source_venue_id, via}] (network; 'via' = how it was matched)",
    },
    "venues.show": {"envelope": _ENVELOPE, "data": _VENUE},
    "venues.add": {"envelope": _ENVELOPE, "data": _VENUE},
    "venues.aliases": {
        "envelope": _ENVELOPE,
        "data": "{slug: source_venue_id} (the built-in alias map)",
    },
    "ingest": {
        "envelope": _ENVELOPE,
        "data": {
            "venue": "string (resolved slug)",
            "status": "ok|partial (partial → exit 5, ok:false)",
            "items_seen": "int",
            "items_added": "int",
            "items_updated": "int",
            "items_failed": "int",
            "max_tcdate": "int|null (creation-date watermark)",
            "max_tmdate": "int|null (modify-date watermark)",
            "dry_run": "bool",
            "incremental": "bool",
            "raw_path": "string|null (the JSONL snapshot written)",
        },
    },
    "index.rebuild": {
        "envelope": _ENVELOPE,
        "data": {"venues": "int", "papers": "int", "failed": "int (notes skipped)"},
    },
    "index.status": {
        "envelope": _ENVELOPE,
        "data": {
            "counts": "{table: int} (row counts per core table)",
            "venues": "[{slug, papers, last_ingested_at}]",
            "db": "string (path)",
        },
    },
    "init": {
        "envelope": _ENVELOPE,
        "data": {
            "home": "string",
            "db": "string",
            "schema_version": "string",
            "created": "bool (false = store already existed)",
        },
    },
    "doctor": {"envelope": _ENVELOPE, "data": {"ok": "bool", "checks": "[{name, status, detail}]"}},
    "schema": {
        "envelope": _ENVELOPE,
        "data": {
            "command": "string",
            "schema_version": "string",
            "envelope": "object (the standard envelope shape)",
            "data": "object|array (the command's data shape)",
        },
    },
}


def schema_for(command: str) -> dict[str, Any] | None:
    return SCHEMAS.get(command)


def available_commands() -> list[str]:
    return sorted(SCHEMAS)
