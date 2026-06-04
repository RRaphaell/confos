"""``confos venues`` — list/search/show/add venues, show the alias map."""

from typing import Annotated

import typer

from ..adapters.openreview import OpenReviewAdapter
from ..console import bind_command, global_output_options
from ..errors import NotFoundError
from ..output.plain import key_value_plain, tsv_rows
from ..output.table import data_table, key_value_table
from ..services import venues as venues_service
from ._render import resolve_limit

app = typer.Typer(no_args_is_help=False, help="List, search, and register venues.")


@app.command("list")
@global_output_options
def list_(ctx: typer.Context) -> None:
    """List known and locally-ingested venues (offline).

    Examples:
      confos venues list
      confos venues list --json
    """
    app_ctx = bind_command(ctx, "venues.list")
    venues = venues_service.list_local_venues(app_ctx.paths)
    if app_ctx.is_json:
        app_ctx.render_json(venues, query={}, sources=["openreview"])
        return
    if app_ctx.is_plain:
        tsv_rows(app_ctx.out, [(v["slug"], v["source_venue_id"], v["paper_count"]) for v in venues])
        return
    if not venues:
        app_ctx.out.print("No venues yet. Find one with [bold]confos venues search[/bold].")
        return
    data_table(
        app_ctx.out,
        ["slug", "openreview id", "year", "papers", "last ingested"],
        [
            (
                v["slug"],
                v["source_venue_id"],
                v["year"] or "",
                v["paper_count"],
                v["last_ingested_at"] or "—",
            )
            for v in venues
        ],
        title="Local venues",
    )


@app.command()
@global_output_options
def search(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Venue query, e.g. 'ICLR 2025'.")],
    limit: Annotated[int | None, typer.Option("--limit", help="Cap suggestions returned.")] = None,
) -> None:
    """Find a venue on OpenReview (network).

    Hits the network. Returns suggested slugs + OpenReview ids you can pass to `ingest`.

    Examples:
      confos venues search "ICLR 2025"
      confos venues search "NeurIPS" --limit 5 --json
    """
    app_ctx = bind_command(ctx, "venues.search")
    app_ctx.info(f"Searching OpenReview for {query!r} …")
    adapter = OpenReviewAdapter(baseurl=app_ctx.config.openreview_baseurl)
    limit = resolve_limit(limit, app_ctx.limit, 25)  # honours an explicit --limit 0
    matches = venues_service.search_venues(adapter, query, limit=limit)
    if app_ctx.is_json:
        app_ctx.render_json(matches, query={"q": query, "limit": limit}, sources=["openreview"])
        return
    if app_ctx.is_plain:
        tsv_rows(app_ctx.out, [(m["slug"], m["source_venue_id"], m["via"]) for m in matches])
        return
    if not matches:
        app_ctx.out.print(f"No venues matched {query!r}. Try an OpenReview id directly.")
        return
    data_table(
        app_ctx.out,
        ["suggested slug", "openreview id", "via"],
        [(m["slug"], m["source_venue_id"], m["via"]) for m in matches],
        title=f"Venues matching {query!r}",
        caption="ingest with: confos ingest <slug-or-id>",
    )


@app.command()
@global_output_options
def show(
    ctx: typer.Context,
    slug: Annotated[str, typer.Argument(help="Venue slug, e.g. neurips-2025.")],
) -> None:
    """Show details for a known venue.

    Examples:
      confos venues show neurips-2025
      confos venues show iclr-2025 --json
    """
    app_ctx = bind_command(ctx, "venues.show")
    venue = venues_service.get_local_venue(app_ctx.paths, slug)
    if venue is None:
        aliases = venues_service.builtin_aliases()
        if slug in aliases:
            venue = {
                "slug": slug,
                "source_venue_id": aliases[slug],
                "status": "known alias (not ingested)",
            }
        else:
            raise NotFoundError(
                f"Venue '{slug}' is not known locally.",
                hint="See `confos venues list` / `aliases` / `search`.",
            )
    if app_ctx.is_json:
        app_ctx.render_json(venue, query={"slug": slug}, sources=["openreview"], venue=slug)
        return
    if app_ctx.is_plain:
        key_value_plain(app_ctx.out, list(venue.items()))
        return
    key_value_table(app_ctx.out, [(k, str(v)) for k, v in venue.items()], title=f"Venue: {slug}")


@app.command()
@global_output_options
def add(
    ctx: typer.Context,
    slug: Annotated[str, typer.Option("--slug", help="Local handle for the venue.")],
    openreview_id: Annotated[
        str,
        typer.Option(
            "--openreview-id", help="OpenReview venue id, e.g. NeurIPS.cc/2025/Conference."
        ),
    ],
) -> None:
    """Register a custom venue by its OpenReview id (local-write).

    Use this when a venue isn't in the built-in alias map. Writes only to the local
    store; the next `ingest <slug>` will pull it.

    Examples:
      confos venues add --slug colm-2025 --openreview-id colmweb.org/COLM/2025/Conference
      confos venues add --slug my-workshop --openreview-id NeurIPS.cc/2025/Workshop/Foo --json
    """
    app_ctx = bind_command(ctx, "venues.add")
    venue = venues_service.add_local_venue(app_ctx.paths, slug, openreview_id)
    if app_ctx.is_json:
        app_ctx.render_json(
            venue, query={"slug": slug, "openreview_id": openreview_id}, sources=["openreview"]
        )
        return
    if app_ctx.is_plain:
        key_value_plain(app_ctx.out, list(venue.items()))
        return
    app_ctx.out.print(f"Registered [bold]{slug}[/bold] → {openreview_id}")
    app_ctx.info(f"Next: confos ingest {slug}")


@app.command()
@global_output_options
def aliases(ctx: typer.Context) -> None:
    """Show the built-in venue alias map.

    Examples:
      confos venues aliases
      confos venues aliases --plain
    """
    app_ctx = bind_command(ctx, "venues.aliases")
    alias_map = venues_service.builtin_aliases()
    if app_ctx.is_json:
        app_ctx.render_json(alias_map, query={}, sources=["openreview"])
        return
    if app_ctx.is_plain:
        tsv_rows(app_ctx.out, list(alias_map.items()))
        return
    data_table(
        app_ctx.out,
        ["slug", "openreview id"],
        list(alias_map.items()),
        title="Built-in venue aliases",
    )
