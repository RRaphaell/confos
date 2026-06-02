"""``confos enrich`` — backfill enrichment data the base ingest skips (network, one-time).

``enrich profiles`` fetches author profiles so the affiliation/country/links/expertise
surfaces stop being empty. It's a one-time, resumable, cached step: results land in
``raw/<venue>/profiles.jsonl`` and thereafter ``index rebuild`` reproduces them offline.
"""

from typing import Annotated

import typer

from ..adapters.openreview import OpenReviewAdapter
from ..console import bind_command, global_output_options
from ..errors import UsageError
from ..output.plain import key_value_plain
from ..output.table import key_value_table
from ..services import enrich as enrich_service

app = typer.Typer(
    no_args_is_help=False, help="Backfill enrichment data (author profiles) into the store."
)


@app.command()
@global_output_options
def profiles(
    ctx: typer.Context,
    venue: Annotated[
        str | None, typer.Option("--venue", help="Venue slug to enrich (must be ingested).")
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="Refetch every profile (ignore the existing snapshot).")
    ] = False,
    limit: Annotated[
        int | None,
        typer.Option("--limit", help="Cap profiles fetched this run (resumable across runs)."),
    ] = None,
) -> None:
    """Fetch author profiles → affiliations, countries, homepage/Scholar/DBLP/expertise.

    Anonymous + best-effort (some handles have no public profile). OpenReview rate-limits
    this to ~20 profiles/min, so a big venue takes a while — it's **resumable** (cached in
    raw/<venue>/profiles.jsonl), so re-run it to continue, or use --limit. Thereafter a
    plain `index rebuild` reproduces the enrichment offline.

    Examples:
      confos enrich profiles --venue neurips-2025 --limit 500   # a chunk now; re-run for more
      confos enrich profiles --venue iclr-2025                  # the whole venue (slow, resumable)
      confos enrich profiles --venue iclr-2025 --force --json
    """
    app_ctx = bind_command(ctx, "enrich.profiles")
    resolved_venue = venue or app_ctx.venue
    if not resolved_venue:
        raise UsageError(
            "--venue is required.",
            hint="e.g. `confos enrich profiles --venue neurips-2025`.",
        )

    adapter = OpenReviewAdapter(baseurl=app_ctx.config.openreview_baseurl)
    result = enrich_service.enrich_profiles(
        app_ctx.paths,
        resolved_venue,
        fetcher=adapter,
        force=force,
        limit=limit,
        on_progress=app_ctx.info,
    )
    query = {"venue": resolved_venue, "force": force, "limit": limit}

    if app_ctx.is_json:
        app_ctx.render_json(result, query=query, venue=resolved_venue, sources=["openreview"])
        return
    if app_ctx.is_plain:
        key_value_plain(app_ctx.out, list(result.items()))
        return

    key_value_table(
        app_ctx.out,
        [
            ("venue", str(result["venue"])),
            ("author handles", str(result["handles_total"])),
            ("already enriched", str(result["already_enriched"])),
            ("fetched now", str(result["fetched"])),
            ("no public profile", str(result["not_found"])),
            ("errored (will retry)", str(result["errors"])),
            ("papers reindexed", str(result["papers_reindexed"])),
            ("snapshot", str(result["profiles_path"])),
        ],
        title=f"Enriched profiles: {result['venue']}",
    )
    remaining = result["handles_total"] - result["already_enriched"] - result["attempted"]
    if remaining > 0:
        app_ctx.info(f"{remaining} handle(s) not yet fetched — re-run to continue (resumable).")
    app_ctx.info("Affiliations/countries/links are now populated — try `confos stats orgs`.")
