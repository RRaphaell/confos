"""``confos brief`` — one-command conference landscape (human + agent).

Composes the whole toolkit (stats, orgs, top papers, people, thin areas) into one cited
object. The ``--json`` form is the agent primitive (a superset of ``export context``); the
default human form renders the same data as Markdown — the open-source launch demo.
"""

from typing import Annotated

import typer

from ..console import bind_command
from ..services import brief as brief_service


def run(
    ctx: typer.Context,
    venue: Annotated[
        str | None, typer.Option("--venue", help="Venue slug to brief (recommended).")
    ] = None,
    topic: Annotated[
        str | None, typer.Option("--topic", help="Focus the brief on a topic (full-text).")
    ] = None,
) -> None:
    """One-command landscape: top papers, hot topics, orgs, people-to-know, thin areas.

    With --topic it's a focused brief (relevance-ranked papers + ranked people); without, the
    venue landscape (top-rated papers if reviews are ingested, else most-recent). LLM-free.
    Default output is human Markdown; `--json` is the agent primitive.

    Examples:
      confos brief --venue neurips-2025
      confos brief --venue neurips-2025 --topic "agent memory"
      confos brief --venue neurips-2025 --json
    """
    app_ctx = bind_command(ctx, "brief")
    resolved_venue = venue or app_ctx.venue
    brief = brief_service.build_brief(app_ctx.paths, venue=resolved_venue, topic=topic)
    query = {"venue": resolved_venue, "topic": topic}
    if app_ctx.is_json:
        app_ctx.render_json(brief, query=query, venue=resolved_venue)
        return
    # Human + --plain both render the Markdown view (best-effort; JSON is the contract).
    app_ctx.emit(brief_service.brief_markdown(brief))
