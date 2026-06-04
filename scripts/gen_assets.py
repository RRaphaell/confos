#!/usr/bin/env python
"""Regenerate the README demo SVGs from a real local store.

Renders confos's human (colored) output to crisp, version-controllable terminal SVGs via
Rich's record→save_svg, so the README screenshots can be refreshed deterministically on
every release instead of hand-captured. Run it against an ingested store:

    uv run python scripts/gen_assets.py                 # uses ~/.confos
    uv run python scripts/gen_assets.py --home ~/.confos --venue neurips-2025

Needs the venues below already ingested (neurips-2025 for the landscape/topics/people,
a reviewed venue like colm-2024 for the rated-papers shot). Writes docs/assets/*.svg.

Pass --png to also rasterise each SVG to a 2x PNG (the README embeds PNGs via absolute
GitHub URLs because PyPI doesn't render SVGs). PNG conversion needs cairosvg + the cairo
C library; on macOS/Homebrew run it with the lib on the dyld path, e.g.:

    DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
        uv run --with cairosvg python scripts/gen_assets.py --png
"""

from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console

from confos.commands._render import render_found_authors, render_rated_papers
from confos.commands.brief import render_brief
from confos.config import Config
from confos.console import AppContext, OutputMode, confos_theme
from confos.output.table import bar_chart
from confos.paths import Paths
from confos.services import brief as brief_service
from confos.services import ranking as ranking_service
from confos.services import search as search_service
from confos.services import stats as stats_service

ASSETS = Path(__file__).resolve().parent.parent / "docs" / "assets"


def _ctx(paths: Paths, width: int) -> tuple[AppContext, Console]:
    """A human-mode AppContext whose stdout Console records for SVG export (colour forced on)."""
    out = Console(
        record=True,
        force_terminal=True,
        color_system="truecolor",
        width=width,
        theme=confos_theme(),
        highlight=False,
        soft_wrap=False,
    )
    err = Console(stderr=True, theme=confos_theme())
    ctx = AppContext(
        mode=OutputMode.HUMAN,
        quiet=True,
        verbose=0,
        no_input=True,
        use_color=True,
        use_unicode=True,
        supports_hyperlinks=False,
        paths=paths,
        config=Config(),
        venue=None,
        limit=None,
        out=out,
        err=err,
    )
    return ctx, out


def _save(out: Console, name: str, title: str) -> None:
    path = ASSETS / name
    out.save_svg(str(path), title=title)
    print(f"  wrote {path.relative_to(ASSETS.parent.parent)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--home", default=str(Path.home() / ".confos"), help="confos store home")
    ap.add_argument("--venue", default="neurips-2025", help="venue for landscape/topics/people")
    ap.add_argument("--reviewed-venue", default="colm-2024", help="venue with reviews (rated shot)")
    ap.add_argument("--topic", default="language models", help="topic for the people/find shot")
    ap.add_argument("--png", action="store_true", help="also rasterise each SVG to a 2x PNG")
    args = ap.parse_args()
    paths = Paths(home=Path(args.home))
    ASSETS.mkdir(parents=True, exist_ok=True)

    # 1. The flagship one-screen landscape dashboard.
    ctx, out = _ctx(paths, width=84)
    render_brief(ctx, brief_service.build_brief(paths, venue=args.venue))
    _save(out, "brief-demo.svg", f"confos brief · {args.venue}")

    # 2. Ranked people-discovery (the well-engineered `authors find`).
    ctx, out = _ctx(paths, width=96)
    authors = ranking_service.find_authors(paths, args.topic, venue=args.venue, limit=8)["authors"]
    render_found_authors(ctx, authors)
    _save(out, "authors-find.svg", f"confos authors find --topic '{args.topic}'")

    # 3. Colored topic bar chart.
    ctx, out = _ctx(paths, width=72)
    rows = stats_service.topics(paths, args.venue, limit=12)["rows"]
    bar_chart(
        out,
        [(str(r["key"]), int(r["papers"])) for r in rows],
        title="[confos.heading]Top topics[/]",
        hue="confos.bar",
        unicode=True,
    )
    _save(out, "viz-topics.svg", f"confos viz topics --venue {args.venue}")

    # 4. Review intelligence — highest-rated papers (needs a reviewed venue).
    ctx, out = _ctx(paths, width=92)
    rated = search_service.top_papers(
        paths, order="rating", venue=args.reviewed_venue, min_reviews=1, limit=8
    )
    if rated:
        render_rated_papers(ctx, rated)
        _save(out, "papers-top.svg", f"confos papers top --venue {args.reviewed_venue}")
    else:
        print(f"  (skipped papers-top.svg — no reviews in {args.reviewed_venue})")

    if args.png:
        _rasterise_pngs()


def _rasterise_pngs(scale: int = 2) -> None:
    """Convert every docs/assets/*.svg to a 2x PNG (README embeds PNGs for PyPI)."""
    try:
        import cairosvg
    except (ImportError, OSError) as exc:  # cairo C lib missing / not on the dyld path
        print(
            f"  PNG step skipped ({exc}). Needs cairosvg + cairo — see this script's docstring "
            "for the DYLD_FALLBACK_LIBRARY_PATH invocation."
        )
        return
    for svg in sorted(ASSETS.glob("*.svg")):
        png = svg.with_suffix(".png")
        cairosvg.svg2png(url=str(svg), write_to=str(png), scale=scale)
        print(f"  wrote {png.relative_to(ASSETS.parent.parent)}")


if __name__ == "__main__":
    main()
