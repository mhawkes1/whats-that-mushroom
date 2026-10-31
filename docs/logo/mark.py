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
# The mark is cream on moss as of 2026-10-31. It was ink on paper, an
# outline, until then. Both halves of that changed and for different
# reasons, both measured.
#
# **Filled rather than outlined.** An outline's only mass is its stroke, so
# the old mark was 18.1% ink at a true 48 px store tile and its luminance was
# 211 against the white a listing is drawn on -- it had no edge and nothing
# to see. Filling the same paths takes it to about 32% without moving a
# control point.
#
# **Cream on moss rather than ink on paper.** Against the cream mark the moss
# carries 5.7:1, and against a white store page 7.4:1 where the book's gold
# managed 4.7. It is also the colour nothing else on a phone's home screen is
# using.
CREAM, MOSS = "#f6f3ea", "#4e6e3f"

# Round five's cap, raised and narrowed on 2026-10-31. This is the only edit
# to Martin's original geometry anywhere in the project, and it is here
# because a launcher masks to a circle.
#
# A circle has the same margin in every direction, so a drawing fits one when
# its own reach is even. Measured as a fraction of the tile's radius, the
# flat cap reached 0.82 sideways and 0.53 upward -- a spread of 0.29, nearly
# touching at the sides with twice that gap above it. It did not clip; it sat
# lopsidedly, which reads as a drawing both too big and floating. The dome
# reaches 0.62 and 0.71, a spread of 0.09.
CAP = ("M 96 286 C 96 60 416 60 416 286 "
       "C 416 304 362 312 256 312 C 150 312 96 304 96 286 Z")

# The same stem, with the closing `Z` gone. That `Z` drew a straight line
# across the top of the stem, inside the cap. It is the only stroke being
# *removed* anywhere in this file, and it survived the cap change untouched.
#
# Two consequences of opening a path, both handled here rather than left to
# show up at 220 px:
#
# The ends sit on the cap underside's own centreline, so each end is in the
# middle of that 30-wide stroke instead of just inside its lower edge.
#
# And the ends take a BUTT cap rather than the round one the rest of the
# drawing uses. A round cap is a half-disc of radius 15 centred on the
# endpoint, and at the stem's near-vertical tangent it bulged out below the
# cap as a small nub on each side. A butt cap is a flat edge along the
# tangent, which the cap's underside swallows completely.
STEM_OPEN = ("M 206 312 C 199 374 195 432 200 466 "
             "C 205 496 307 496 312 466 C 317 432 313 374 306 312")

# Centres the ink box in the 512 canvas. `build_icons.py` measures and
# recentres anyway, so this is for anything that uses the SVG directly.
DY = -22


def mark(stroke: int = 30, ground: str | None = MOSS,
         ink: str = CREAM) -> str:
    bg = (f'<rect width="512" height="512" fill="{ground}"/>' if ground else "")
    # The stem's two open ends are the only butt caps in the drawing; see
    # the note on STEM_OPEN.
    body = (f'<path d="{CAP}"/>'
            f'<path d="{STEM_OPEN}" stroke-linecap="butt"/>')
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" '
        f'width="512" height="512">{bg}'
        f'<g fill="{ink}" stroke="{ink}" stroke-width="{stroke}" '
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
    (HERE / "funga-mark-reversed.svg").write_text(mark(ground=CREAM, ink=MOSS))

    print(f"  {out.relative_to(HERE.parent.parent)}")
    print("  funga-mark-transparent.svg   (no ground, for placing)")
    print("  funga-mark-reversed.svg      (moss on cream, for pale grounds)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
