#!/usr/bin/env python3
"""Round six: the outline mushroom, drawn properly.

Martin picked `m4-outline` from round five for its simplicity, and it was
the one mark on that sheet I had flagged as clogging at 29 px. Both things
are true, and the clogging is a drawing fault rather than a fault in the
idea.

**What was wrong.** Round five stroked the cap and the stem as two
overlapping closed paths. That puts a line *inside* the mark, where the
stem's top edge crosses under the cap, and at 29 px that hidden line and
the two real ones merge into a blot. Everything here is a single
continuous path instead -- one outline, no internal strokes, nothing to
merge with.

**Optical sizing, not scaling.** An outline mark cannot be one drawing.
Stroke weight is absolute but counters shrink with everything else, so a
weight that looks confident at 512 fills the gaps at 29. The same problem
a typeface solves with optical sizes, solved the same way: a display
drawing and a small drawing, and the small one is not the big one
reduced.

Everything is built from one function so the family stays a family. Cap
width, dome height, stem width, waist and stroke are all parameters; any
variant here is any other variant plus different numbers.
"""

from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).parent
INK, PAPER = "#231e17", "#f6f3ea"

CX = 256


def svg(body: str, ground: str = PAPER) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" '
        'width="512" height="512">'
        f'<rect width="512" height="512" fill="{ground}"/>{body}</svg>'
    )


def outline(
    stroke: int = 30,
    cap_half: int = 182,
    cap_top: int = 128,
    cap_bottom: int = 268,
    stem_half: int = 52,
    stem_bottom: int = 404,
    waist: int = 10,
    brim: int = 16,
    base_round: int = 0,
    junction: bool = False,
    split: bool = False,
    ring: bool = False,
    volva: bool = False,
    gills: int = 0,
) -> str:
    """One mushroom, as a single continuous outline.

    `brim` is how far the cap's underside lifts toward the middle -- the
    overhang that stops a cap reading as a dome sitting on a stick. A
    *negative* brim bulges it downward instead, which is what the round-five
    drawing did and is a good part of why that one looked generous rather
    than narrow. `waist` pinches the stem inward; negative values barrel it
    outward. `base_round` swells the stem's foot into a rounded base rather
    than closing it with a straight line.

    Drawn as one closed path on purpose. Two overlapping paths put a stroke
    inside the mark where nobody wants one, and at small sizes that is the
    stroke that closes the gap and turns the mark into a blot.
    """
    # A cubic's apex sits at 3/4 of its control offset, so to put the dome's
    # top exactly on `cap_top` the controls go further up than that.
    h = cap_bottom - cap_top
    ctrl_y = cap_bottom - h * 4 / 3

    path = (
        f'M {CX - stem_half} {stem_bottom} '
        # up the left of the stem, slightly waisted
        f'C {CX - stem_half - waist} {stem_bottom - 60} '
        f'{CX - stem_half - waist} {cap_bottom + 40} '
        f'{CX - stem_half} {cap_bottom} '
        # out along the cap's underside to the left margin
        f'C {CX - 110} {cap_bottom - brim} {CX - cap_half + 26} {cap_bottom} '
        f'{CX - cap_half} {cap_bottom} '
        # over the dome
        f'C {CX - cap_half} {ctrl_y} {CX + cap_half} {ctrl_y} '
        f'{CX + cap_half} {cap_bottom} '
        # back along the underside to the stem
        f'C {CX + cap_half - 26} {cap_bottom} {CX + 110} {cap_bottom - brim} '
        f'{CX + stem_half} {cap_bottom} '
        # down the right of the stem
        f'C {CX + stem_half + waist} {cap_bottom + 40} '
        f'{CX + stem_half + waist} {stem_bottom - 60} '
        f'{CX + stem_half} {stem_bottom} '
        + (
            # A rounded foot, closed as part of the same path so the mark
            # stays one continuous outline.
            f'C {CX + stem_half - 4} {stem_bottom + base_round} '
            f'{CX - stem_half + 4} {stem_bottom + base_round} '
            f'{CX - stem_half} {stem_bottom} '
            if base_round else ''
        )
        + 'Z'
    )

    extra = []
    if junction:
        # The cap's underside crossing behind the stem.
        #
        # In the two-path drawing this appeared by accident, as the stem's
        # top edge showing through the cap. It is worth having on purpose:
        # it is the difference between a cap *sitting on* a stem and one
        # continuous blob. Separate from the outline so it can be dropped
        # for the small-size cut, which is the only place it costs anything.
        extra.append(
            f'<path d="M {CX - stem_half - 2} {cap_bottom + 4} '
            f'C {CX - 20} {cap_bottom + 12} {CX + 20} {cap_bottom + 12} '
            f'{CX + stem_half + 2} {cap_bottom + 4}"/>'
        )
    if ring:
        y = cap_bottom + 54
        extra.append(f'<path d="M {CX - stem_half - 34} {y} '
                     f'C {CX - 40} {y - 16} {CX + 40} {y - 16} '
                     f'{CX + stem_half + 34} {y}"/>')
    if volva:
        y = stem_bottom
        extra.append(f'<path d="M {CX - stem_half - 40} {y - 4} '
                     f'C {CX - stem_half - 48} {y + 40} {CX + stem_half + 48} {y + 40} '
                     f'{CX + stem_half + 40} {y - 4}"/>')
    for i in range(gills):
        t = (i + 1) / (gills + 1)
        x = CX - cap_half + 34 + t * (cap_half * 2 - 68)
        if abs(x - CX) < stem_half + 18:
            continue
        extra.append(f'<path d="M {x:.0f} {cap_bottom - 6} '
                     f'L {x:.0f} {cap_bottom + 26}"/>')

    if split:
        # Cap closed across its full width, stem drawn as an open U hung
        # beneath it.
        #
        # This is the construction the original wanted and did not have.
        # Drawing the cap and the stem as two *closed* shapes puts the
        # stem's top edge inside the cap, and that buried stroke is what
        # merged with the cap's underside and blotted at small sizes.
        # Merging them into one path fixed the blot and cost the shape:
        # without a full-width underside the cap becomes a shoulder and
        # the mushroom starts reading as a tree. Leaving the stem's top
        # edge *undrawn* keeps the silhouette exactly and removes the only
        # stroke that was ever in the way.
        h2 = cap_bottom - cap_top
        cy2 = cap_bottom - h2 * 4 / 3
        cap = (
            f'M {CX - cap_half} {cap_bottom} '
            f'C {CX - cap_half} {cy2} {CX + cap_half} {cy2} '
            f'{CX + cap_half} {cap_bottom} '
            f'C {CX + cap_half - 40} {cap_bottom + max(brim, 0) + 8} '
            f'{CX + 90} {cap_bottom - brim} {CX} {cap_bottom - brim} '
            f'C {CX - 90} {cap_bottom - brim} {CX - cap_half + 40} '
            f'{cap_bottom + max(brim, 0) + 8} {CX - cap_half} {cap_bottom} Z'
        )
        stem = (
            f'M {CX - stem_half} {cap_bottom - brim - 6} '
            f'C {CX - stem_half - waist} {cap_bottom + 50} '
            f'{CX - stem_half - waist} {stem_bottom - 60} '
            f'{CX - stem_half} {stem_bottom} '
            + (f'C {CX - stem_half + 4} {stem_bottom + base_round} '
               f'{CX + stem_half - 4} {stem_bottom + base_round} '
               f'{CX + stem_half} {stem_bottom} '
               if base_round else f'L {CX + stem_half} {stem_bottom} ')
            + f'C {CX + stem_half + waist} {stem_bottom - 60} '
            f'{CX + stem_half + waist} {cap_bottom + 50} '
            f'{CX + stem_half} {cap_bottom - brim - 6}'
        )
        return svg(
            f'<g fill="none" stroke="{INK}" stroke-width="{stroke}" '
            f'stroke-linejoin="round" stroke-linecap="round">'
            f'<path d="{cap}"/><path d="{stem}"/>{"".join(extra)}</g>'
        )

    return svg(
        f'<g fill="none" stroke="{INK}" stroke-width="{stroke}" '
        f'stroke-linejoin="round" stroke-linecap="round">'
        f'<path d="{path}"/>{"".join(extra)}</g>'
    )


MARKS = [
    ("o1-regular", "Regular",
     "One continuous path, stroke 30. The round-five mark redrawn so there "
     "is no stroke hidden inside it. This is the default."),
    ("o2-light", "Light",
     "Stroke 22. More air, more delicate, and the first to disappear "
     "against a busy wallpaper."),
    ("o3-bold", "Bold",
     "Stroke 40. Holds on any ground and starts to lose its counters -- "
     "look at the 29 before choosing it."),
    ("o4-small", "Drawn for 29",
     "Stroke 26 with a wider stem and a shallower cap, so the counters "
     "survive the reduction. Not the regular one shrunk: an outline mark "
     "needs two drawings the way a typeface needs optical sizes."),
    ("o5-wide", "Wide cap",
     "A broader, shallower cap. More overhang, which is the thing that "
     "stops an outline cap reading as a dome balanced on a stick."),
    ("o6-tall", "Tall",
     "A narrower cap and a longer stem. Elegant, and the furthest from the "
     "squat button-mushroom every competitor uses."),
    ("o7-ringed", "Ringed",
     "One extra line for the annulus. It is the feature that says Amanita, "
     "so it carries meaning rather than decoration -- and it is one more "
     "thing to lose at 29."),
    ("o8-gilled", "Gilled",
     "Short ticks under the cap. The most information of the eight and the "
     "least robust; included so the trade is visible."),
]

BUILDERS = {
    "o1-regular": lambda: outline(),
    "o2-light": lambda: outline(stroke=22),
    "o3-bold": lambda: outline(stroke=40),
    "o4-small": lambda: outline(stroke=26, stem_half=62, cap_top=146,
                                cap_bottom=262, cap_half=176, brim=12),
    "o5-wide": lambda: outline(cap_half=204, cap_top=152, cap_bottom=266, brim=22),
    "o6-tall": lambda: outline(cap_half=156, cap_top=112, cap_bottom=252,
                               stem_bottom=430, stem_half=46),
    "o7-ringed": lambda: outline(ring=True),
    "o8-gilled": lambda: outline(gills=7, brim=20),
}


def main() -> int:
    for key, _, _ in MARKS:
        (HERE / f"{key}.svg").write_text(BUILDERS[key]())
        print(f"  {key}.svg")
    (HERE / "_meta.json").write_text(json.dumps(MARKS, indent=2))
    print(f"\n  {len(MARKS)} marks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
