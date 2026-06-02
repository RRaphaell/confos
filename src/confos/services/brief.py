"""``confos brief`` — one-command conference landscape (the launch demo + agent primitive).

Pure composition over the existing services: overview + hot topics + rising orgs + top
papers + people-to-know (+ topic-scoped thin areas). LLM-free — every section is data confos
already derives + cites. With ``--topic`` it's a focused brief (relevance-ranked papers +
ranked people); without, it's the venue landscape (top-rated papers if reviews are ingested,
else most-recent; most-prolific people). The ``--json`` form is a superset of
``export context`` — the ideal agent primitive.
"""

from __future__ import annotations

from typing import Any

from ..paths import Paths
from . import authors as authors_service
from . import export as export_service
from . import orgs as orgs_service
from . import ranking as ranking_service
from . import search as search_service
from . import stats as stats_service

_NOTES = (
    "All sections derived locally from OpenReview with provenance; no LLM synthesis. "
    "People/orgs need `confos enrich profiles`; top-rated papers need `ingest --with-reviews`."
)


def build_brief(
    paths: Paths,
    *,
    venue: str | None = None,
    topic: str | None = None,
    paper_limit: int = 10,
    author_limit: int = 10,
    org_limit: int = 10,
    topic_limit: int = 15,
) -> dict[str, Any]:
    overview = stats_service.overview(paths, venue)
    hot_topics = stats_service.topics(paths, venue, limit=topic_limit)["rows"]
    orgs = orgs_service.top_orgs(paths, venue=venue, limit=org_limit)

    thin_areas: list[str] = []
    if topic:
        # Focused brief: relevance-ranked papers + ranked people on the topic.
        top = search_service.search_papers(paths, topic, venue=venue, limit=paper_limit)
        ranked_by = "relevance"
        people = ranking_service.find_authors(paths, topic, venue=venue, limit=author_limit)[
            "authors"
        ]
        thin_areas = export_service.build_context_pack(paths, topic, venue=venue)["thin_areas"]
    else:
        # Venue landscape: top-rated papers (reviews) → recent fallback; most-prolific people.
        top = search_service.top_papers(paths, order="rating", venue=venue, limit=paper_limit)
        ranked_by = "rating"
        if not top:
            top = search_service.recent_papers(paths, venue=venue, limit=paper_limit)
            ranked_by = "recent"
        people = authors_service.top_authors(paths, venue=venue, limit=author_limit)

    return {
        "type": "confos.brief",
        "venue": venue,
        "topic": topic,
        "overview": overview,
        "top_papers": {"ranked_by": ranked_by, "papers": top},
        "hot_topics": hot_topics,
        "rising_orgs": orgs["rows"],
        "people_to_know": people,
        "thin_areas": thin_areas,
        "data_quality": {"orgs": orgs["data_quality"]},
        "notes": _NOTES,
    }


def brief_markdown(brief: dict[str, Any]) -> str:
    """A human/doc-friendly Markdown render of the same data."""
    venue = brief["venue"] or "all venues"
    scope = f"{brief['topic']} @ {venue}" if brief["topic"] else venue
    overview = brief["overview"]
    lines = [f"# confos brief: {scope}", "", f"_{brief['notes']}_", ""]

    status = ", ".join(f"{k} {v}" for k, v in (overview.get("status") or {}).items())
    lines.append(
        f"**Landscape:** {overview['papers']} papers ({status}) · {overview['authors']} authors "
        f"· {overview['orgs']} orgs · {overview['topics']} topics"
    )
    lines.append("")

    papers = brief["top_papers"]
    lines.append(f"## Top papers — by {papers['ranked_by']} ({len(papers['papers'])})")
    for paper in papers["papers"]:
        authors = ", ".join(a["name"] for a in paper["authors"])
        suffix = ""
        if paper.get("rating_mean") is not None:
            suffix = f" · rating {paper['rating_mean']} (n={paper.get('review_count', 0)})"
        lines.append(f"- [{paper['title']}]({paper['url']}) — {authors}{suffix}")
    lines.append("")

    if brief["hot_topics"]:
        lines.append("## Hot topics")
        lines.append(", ".join(f"{t['key']} ({t['papers']})" for t in brief["hot_topics"]))
        lines.append("")

    if brief["rising_orgs"]:
        lines.append("## Organisations")
        for org in brief["rising_orgs"]:
            lines.append(f"- {org['key']}: {org['papers']} paper(s)")
        lines.append("")

    if brief["people_to_know"]:
        lines.append(f"## People to know ({len(brief['people_to_know'])})")
        for person in brief["people_to_know"]:
            extra = person.get("why_relevant") or f"{person.get('paper_count', 0)} paper(s)"
            lines.append(
                f"- **{person['display_name']}** ({person['affiliation_current']}) — {extra}"
            )
        lines.append("")

    if brief["thin_areas"]:
        lines.append("## Thin areas (heuristic — under-represented subtopics)")
        lines.append(", ".join(brief["thin_areas"]))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
