#!/usr/bin/env python3
"""The production mark. One file, one drawing, everything else derived.

    python docs/logo/mark.py

Writes `docs/logo/funga-mark.svg`, which is what `scripts/build_icons.py`
rasterises and what a designer should be handed.

The drawing is Martin's round-five outline, unchanged in geometry. One
stroke is removed, and it is the one he spotted: the stem was a *closed*
path, so its top edge was drawn as a straight line across the stem, hidden
inside the cap. Dropping the `Z` that closed it leaves an open U -- left
side, foot, right side -- with nothing drawn across the top.

Why that is the right fix rather than redrawing:

- The silhouette is untouched. Every curve keeps its original control
  points, so this is the same mushroom to the unit.
- The cap keeps its full-width underside, which is what makes it read as a
  cap *sitting on* a stem. An earlier attempt merged cap and stem into one
  continuous path, which removed that underside and turned the mushroom
  into something closer to a tree.
- The open ends land on the cap's underside and the round linecaps merge
  into it, so the join closes visually without a stroke crossing the cap.

`ring` and `volva` are available because the taxonomy's two most
load-bearing features are the annulus and the bag at the stem base, and a
day may come when the mark wants one. Neither is on by default; both cost
legibility at icon sizes.
"""

from __future__ import annotations

import argparse
import pathlib

HERE = pathlib.Path(__file__).parent
INK, PAPER = "#231e17", "#f6f3ea"

# Round five's geometry, read off `round5/m4-outline.svg`.
CAP = ("M 62 268 C 62 114 452 114 452 268 "
       "C 452 284 392 292 257 292 C 122 292 62 284 62 268 Z")

# The same stem, with the closing `Z` gone. That `Z` drew a straight line
# from (309,290) back to (205,290) -- across the top of the stem, inside the
# cap. It is the only stroke being *removed* anywhere in this file.
#
# Two consequences of opening a path, both handled here rather than left to
# show up at 220 px:
#
# The ends move from y=290 to y=292, which is the cap underside's own
# centreline, so each end sits in the middle of that 30-wide stroke instead
# of just inside its lower edge.
#
# And the ends take a BUTT cap rather than the round one the rest of the
# drawing uses. A round cap is a half-disc of radius 15 centred on the
# endpoint, and at the stem's near-vertical tangent it bulged out below the
# cap as a small nub on each side. A butt cap is a flat edge along the
# tangent, which the cap's underside swallows completely.
STEM_OPEN = ("M 205 292 C 198 348 194 400 199 432 "
             "C 204 464 310 464 315 432 C 320 400 316 348 309 292")

DY = -16
RING = "M 171 330 C 214 314 300 314 343 330"
VOLVA = "M 168 424 C 160 468 354 468 346 424"


def mark(stroke: int = 30, ground: str | None = PAPER,
         ring: bool = False, volva: bool = False, ink: str = INK) -> str:
    bg = (f'<rect width="512" height="512" fill="{ground}"/>' if ground else "")
    # The stem's two open ends are the only butt caps in the drawing; see
    # the note on STEM_OPEN.
    body = (f'<path d="{CAP}"/>'
            f'<path d="{STEM_OPEN}" stroke-linecap="butt"/>')
    if ring:
        body += f'<path d="{RING}"/>'
    if volva:
        body += f'<path d="{VOLVA}"/>' 
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" '
        f'width="512" height="512">{bg}'
        f'<g fill="none" stroke="{ink}" stroke-width="{stroke}" '
        f'stroke-linejoin="round" stroke-linecap="round" '
        f'transform="translate(0,{DY})">{body}</g></svg>'
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(HERE / "funga-mark.svg"))
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    out.write_text(mark())
    # The whole point of this file is that nothing is drawn across the
    # stem's top. If a `Z` ever creeps back onto that path the mark quietly
    # regains the line Martin asked to have removed.
    assert "Z" not in STEM_OPEN, "the stem must stay open"

    # Useful siblings, same drawing.
    (HERE / "funga-mark-transparent.svg").write_text(mark(ground=None))
    (HERE / "funga-mark-reversed.svg").write_text(mark(ground=INK, ink=PAPER))

    print(f"  {out.relative_to(HERE.parent.parent)}")
    print("  funga-mark-transparent.svg   (no ground, for placing)")
    print("  funga-mark-reversed.svg      (paper on ink)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
