"""``confos ingest <venue>`` — pull a venue into the local store (network).

There is no separate ``sync`` command: re-running ``ingest`` performs the incremental
update via stored watermarks (D6); ``--force`` does a full re-pull.
"""

from typing import Annotated

import typer

from ..adapters.openreview import OpenReviewAdapter
from ..console import bind_command
from ..errors import EXIT_PARTIAL
from ..models import IngestOptions
from ..output.plain import key_value_plain
from ..output.table import key_value_table
from ..services.ingest import ingest_venue


def run(
    ctx: typer.Context,
    venue: Annotated[str, typer.Argument(help="Venue slug to ingest, e.g. neurips-2025.")],
    with_reviews: Annotated[
        bool,
        typer.Option(
            "--with-reviews",
            help="Also fetch reviews + decisions (enables `papers top`/`controversial`; "
            "larger download).",
        ),
    ] = False,
    include_decisions: Annotated[
        bool,
        typer.Option("--include-decisions", help="Alias for --with-reviews (legacy name)."),
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", help="Ignore sync watermarks and do a full re-pull.")
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Report would-fetch/insert/update counts; write nothing."),
    ] = False,
) -> None:
    """Pull a venue's full submission set into the local store (network).

    Status is derived locally from each note's raw venueid (ARCHITECTURE §8), so
    --accepted-only is a read-time filter, not an ingest option.

    Examples:
      confos ingest neurips-2025
      confos ingest neurips-2025 --force
      confos ingest iclr-2025 --dry-run --json
    """
    app_ctx = bind_command(ctx, "ingest")
    # --with-reviews is the clear name; --include-decisions is kept as a legacy alias.
    fetch_reviews = with_reviews or include_decisions
    opts = IngestOptions(include_decisions=fetch_reviews, force=force, dry_run=dry_run)
    adapter = OpenReviewAdapter(baseurl=app_ctx.config.openreview_baseurl)

    result = ingest_venue(
        paths=app_ctx.paths,
        adapter=adapter,
        handle=venue,
        opts=opts,
        on_progress=app_ctx.info,
    )

    data = result.model_dump()
    query = {
        "venue": venue,
        "force": force,
        "dry_run": dry_run,
        "with_reviews": fetch_reviews,
    }

    if app_ctx.is_json:
        app_ctx.render_json(
            # warnings live at the envelope level only (SCHEMAS §5), like every other command.
            {k: v for k, v in data.items() if k != "warnings"},
            query=query,
            sources=["openreview"],
            venue=result.venue,
            warnings=result.warnings,
            # ok must agree with the exit code: a partial ingest exits 5, so ok:false.
            ok=result.status == "ok",
        )
    elif app_ctx.is_plain:
        key_value_plain(app_ctx.out, list(data.items()))
    else:
        _render_human(app_ctx, result)

    if result.status == "partial":
        raise typer.Exit(EXIT_PARTIAL)


def _render_human(app_ctx: object, result: object) -> None:
    from ..console import AppContext
    from ..models import IngestResult

    assert isinstance(app_ctx, AppContext)
    assert isinstance(result, IngestResult)

    mode = "dry-run" if result.dry_run else ("incremental" if result.incremental else "full")
    verb = "Would ingest" if result.dry_run else "Ingested"
    app_ctx.out.print(f"{verb} [bold]{result.venue}[/bold] ({mode})")
    rows = [
        ("submissions seen", str(result.items_seen)),
        ("added", str(result.items_added)),
        ("updated", str(result.items_updated)),
    ]
    if result.items_failed:
        rows.append(("failed/skipped", str(result.items_failed)))
    if result.raw_path:
        rows.append(("raw snapshot", result.raw_path))
    key_value_table(app_ctx.out, rows)
    for warning in result.warnings:
        app_ctx.warn(warning)
