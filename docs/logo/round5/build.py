#!/usr/bin/env python3
"""Round five: the F developed, and a plain mushroom beside it.

Two groups, both at Martin's request on 2026-10-27.

**The F, without the spore drops.** Round four's Cut Lengthways carried
falling spores under it; they are gone here. Worth being honest about what
that costs and what it does not. The dissolve *was* the Half Known idea --
the mark stating that the app does not know. Removing it removes that
statement. What survives is the cut itself, and the cut is not decoration:
slicing a mushroom in half lengthways, base included, is exactly what the
app tells a user to do when it asks about bruising. So the mark now shows
the *act of checking* rather than the *state of doubt*. Quieter, cleaner,
and it scales better, because the spore fan was the first thing to die
below 48 px.

**A plain mushroom.** No cut, no spores, no dissolve. Asked for as its own
thing, and useful regardless: it is the fallback if the F reads as a letter
rather than a fungus, and it is what a favicon or a 29 px tile may have to
fall back to anyway.

Both groups keep the round-one lesson. A cap drawn without a stem reads as
a hill, and three concepts died of it.
"""

from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).parent
INK, PAPER = "#231e17", "#f6f3ea"

LEFT = 148          # the cut face: the F's spine, and the mushroom's midline


def svg(body: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" '
        'width="512" height="512">'
        f'<rect width="512" height="512" fill="{PAPER}"/>{body}</svg>'
    )


# --- The F -------------------------------------------------------------------

def f_mark(
    cap_top: int = 86,
    cap_right: int = 438,
    cap_bottom: int = 196,
    stem_w: int = 56,
    stem_bottom: int = 446,
    ring_y: int = 252,
    ring_len: int = 168,
    ring_h: int = 46,
    gills: bool = False,
) -> str:
    """A mushroom cut down its middle, which is also the letter F.

    Every variant below is this function with different numbers, so the
    family stays a family rather than six unrelated drawings.

    `cap_right` is the F's top arm. `ring_*` is the annulus, which is the
    F's middle arm -- a real diagnostic feature doing a typographic job
    rather than an ornament added to make the letter work.
    """
    mid = (cap_top + cap_bottom) / 2

    # The cut face is flat; everything right of it is the dome.
    #
    # The outer edge is blunt and the underside slightly concave, and both
    # are load-bearing. The first draft tapered to a point and ran the
    # underside flat, which reads as a *flag* on a pole -- the mushroom
    # only survived in round four because the spore fall underneath it was
    # doing the explaining. With the spores gone the cap has to say
    # "mushroom" unaided, and what says it is overhang: a margin that is
    # wider than the stem, comes down squarely, and tucks back under.
    rim = cap_bottom + 10
    cap = (
        f'M {LEFT} {rim} L {LEFT} {cap_top + 2} '
        f'C {LEFT + 46} {cap_top - 30} {cap_right - 104} {cap_top - 18} '
        f'{cap_right - 44} {mid - 16} '
        f'C {cap_right + 4} {mid + 16} {cap_right} {rim - 14} '
        f'{cap_right - 30} {rim} '
        f'C {cap_right - 96} {rim + 6} {LEFT + 86} {cap_bottom - 10} '
        f'{LEFT} {cap_bottom - 6} Z'
    )

    parts = [
        f'<path d="{cap}"/>',
        f'<rect x="{LEFT}" y="{cap_bottom - 4}" width="{stem_w}" '
        f'height="{stem_bottom - cap_bottom + 4}" rx="5"/>',
        f'<rect x="{LEFT}" y="{ring_y}" width="{ring_len}" height="{ring_h}" '
        f'rx="{ring_h // 2}"/>',
    ]

    if gills:
        # Gills in cross-section: ticks hanging from the cap's underside.
        for i in range(5):
            x = LEFT + stem_w + 24 + i * 40
            parts.append(
                f'<rect x="{x}" y="{cap_bottom - 2}" width="13" '
                f'height="{36 - i * 5}" rx="6"/>'
            )

    return svg(f'<g fill="{INK}">{"".join(parts)}</g>')


def f_flared() -> str:
    """The stem widening into a volva, which is the feature that kills people."""
    cap = (f'M {LEFT} 206 L {LEFT} 88 '
           f'C {LEFT + 46} 56 330 70 392 150 '
           f'C 424 190 420 206 388 206 '
           f'C 320 212 {LEFT + 86} 192 {LEFT} 190 Z')
    stem = (f'M {LEFT} 192 L {LEFT + 56} 192 L {LEFT + 56} 368 '
            f'C {LEFT + 92} 404 {LEFT + 96} 446 {LEFT + 72} 452 '
            f'L {LEFT} 452 Z')
    ring = f'<rect x="{LEFT}" y="250" width="166" height="46" rx="23"/>'
    return svg(f'<g fill="{INK}"><path d="{cap}"/><path d="{stem}"/>{ring}</g>')


# --- The plain mushroom ------------------------------------------------------

CAP = ("M 62 268 C 62 114 452 114 452 268 "
       "C 452 284 392 292 257 292 C 122 292 62 284 62 268 Z")
STEM = ("M 205 290 C 198 348 194 400 199 432 "
        "C 204 464 310 464 315 432 C 320 400 316 348 309 290 Z")


def plain(ring: bool = False, volva: bool = False, dome: float = 1.0,
          outline: bool = False) -> str:
    cap = CAP
    if dome != 1.0:
        # Lift the cap's control points to arch or flatten it.
        lift = int((1 - dome) * 60)
        cap = CAP.replace("114", str(114 + lift))
    parts = [f'<path d="{cap}" transform="translate(0,-16)"/>',
             f'<path d="{STEM}" transform="translate(0,-16)"/>']
    if ring:
        parts.append('<rect x="176" y="312" width="160" height="34" rx="17"/>')
    if volva:
        parts.append('<path d="M 176 430 C 176 398 336 398 336 430 '
                     'C 336 462 176 462 176 430 Z"/>')
    if outline:
        return svg(
            f'<g fill="none" stroke="{INK}" stroke-width="30" '
            f'stroke-linejoin="round" stroke-linecap="round">'
            f'<path d="{cap}" transform="translate(0,-16)"/>'
            f'<path d="{STEM}" transform="translate(0,-16)"/></g>'
        )
    return svg(f'<g fill="{INK}">{"".join(parts)}</g>')


MARKS = [
    ("f1-baseline", "F · Baseline",
     "Round four's mark with the spore drops off. The cap is not untouched, "
     "though: dropping the spores made it read as a flag, so the rim is "
     "blunter and the underside tucks back under. Overhang is what says "
     "mushroom once nothing beneath it is doing the explaining."),
    ("f2-flat", "F · Flat cap",
     "A shallower cap, so the top arm sits closer to a true F. Reads as a "
     "letter fastest and as a mushroom slowest -- the trade in one picture."),
    ("f3-domed", "F · Domed",
     "The opposite: a deeper, more arched cap. Unmistakably a fungus, and "
     "the F has to work harder to be seen."),
    ("f4-volva", "F · Volva",
     "The stem swelling into a bag at the base. That bag is the single "
     "feature that separates a death cap from a field mushroom, and it is "
     "the part almost everyone leaves in the soil."),
    ("f5-gills", "F · Gills",
     "Gills shown in cross-section under the cap. More information, more "
     "to lose when it shrinks."),
    ("f6-heavy", "F · Heavy",
     "Thicker stem, shorter ring, tighter counters. Drawn for 29 px rather "
     "than scaled down to it -- the usual practice, and worth the extra file."),
    ("m1-classic", "Mushroom · Classic",
     "No cut, no spores, nothing. The silhouette on its own."),
    ("m2-ringed", "Mushroom · Ringed",
     "With an annulus. The ring is what tells you an Amanita has been "
     "there, so it earns its place rather than decorating."),
    ("m3-volva", "Mushroom · Volva",
     "Ring and bag together: a textbook Amanita, which is the shape the "
     "whole app is organised around."),
    ("m4-outline", "Mushroom · Outline",
     "Stroked rather than filled. Lighter on a dark ground, and the first "
     "to clog at small sizes -- check the 29 before falling for it."),
]

BUILDERS = {
    "f1-baseline": lambda: f_mark(),
    "f2-flat": lambda: f_mark(cap_top=104, cap_bottom=184, cap_right=446),
    "f3-domed": lambda: f_mark(cap_top=70, cap_bottom=206, cap_right=420),
    "f4-volva": f_flared,
    "f5-gills": lambda: f_mark(gills=True),
    "f6-heavy": lambda: f_mark(stem_w=70, ring_len=146, ring_h=54,
                               cap_top=92, cap_right=430, cap_bottom=200),
    "m1-classic": lambda: plain(),
    "m2-ringed": lambda: plain(ring=True),
    "m3-volva": lambda: plain(ring=True, volva=True),
    "m4-outline": lambda: plain(outline=True),
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
