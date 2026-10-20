#!/usr/bin/env python3
"""Eight ways of dissolving the Half Known mark.

The round-one attempt failed below 48 px because the stipple was a smooth
gradient of tiny dots, and a smooth gradient is exactly what scaling
destroys. Everything here is *discrete* -- a countable number of columns,
blocks, bars or zones -- so that shrinking it loses detail rather than
turning it to noise.

The fade also starts earlier, at about 36% across the mark rather than 55%,
which is what Martin asked for: the mushroom should be coming apart almost
as soon as you have read it.
"""

from __future__ import annotations

import json
import math
import pathlib

CAP = ("M 62 266 C 62 112 450 112 450 266 "
       "C 450 282 392 290 256 290 C 120 290 62 282 62 266 Z")
STEM = ("M 204 288 C 197 346 193 398 198 430 "
        "C 203 462 309 462 314 430 C 319 398 315 346 308 288 Z")
INK, PAPER = "#231e17", "#f6f3ea"

X0 = 188  # where the dissolve begins


def clipped(inner: str, solid_to: int = X0, dy: int = -22) -> str:
    """Clip to the mushroom so the dissolve can never spill outside it."""
    return (
        f'<defs><clipPath id="m">'
        f'<path d="{CAP}" transform="translate(0,{dy})"/>'
        f'<path d="{STEM}" transform="translate(0,{dy})"/></clipPath></defs>'
        f'<g clip-path="url(#m)">'
        f'<rect x="0" y="0" width="{solid_to}" height="512" fill="{INK}"/>'
        f'{inner}</g>'
    )


def svg(body: str, bg: str = PAPER) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" '
        f'width="512" height="512"><rect width="512" height="512" fill="{bg}"/>'
        f'{body}</svg>\n'
    )


def ramp(t: float, power: float = 1.0) -> float:
    """Coverage falling from 1 to 0 across the dissolve."""
    return max(0.0, (1 - t) ** power)


def big_stipple() -> str:
    out, cols = [], 7
    for c in range(cols):
        r = 23 * ramp(c / (cols - 1), 0.85)
        if r < 3:
            continue
        x = X0 + 14 + c * 38
        for row in range(10):
            out.append(f'<circle cx="{x}" cy="{118 + row * 36}" r="{r:.1f}"/>')
    return clipped(f'<g fill="{INK}">{"".join(out)}</g>')


def blocks() -> str:
    out, cols, s = [], 8, 33
    for c in range(cols):
        keep = ramp(c / (cols - 1), 0.8)
        for row in range(12):
            # Deterministic thinning, not random: the same mark every build.
            if ((row * 7 + c * 5) % 11) / 11.0 < keep:
                out.append(
                    f'<rect x="{X0 + c * s}" y="{110 + row * s}" '
                    f'width="{s - 4}" height="{s - 4}"/>'
                )
    return clipped(f'<g fill="{INK}">{"".join(out)}</g>')


def slices() -> str:
    out, n = [], 9
    for i in range(n):
        w = 26 * ramp(i / (n - 1), 0.75)
        if w < 2.5:
            continue
        out.append(f'<rect x="{X0 + i * 30:.0f}" y="0" width="{w:.1f}" height="512"/>')
    return clipped(f'<g fill="{INK}">{"".join(out)}</g>')


def gill_slices() -> str:
    out, n, cx, cy = [], 15, 236, 268
    for i in range(n):
        a = -math.pi / 2 + (math.pi * 0.98) * i / (n - 1)
        w = 25 * ramp(i / (n - 1), 0.7)
        if w < 2.5:
            continue
        out.append(
            f'<line x1="{cx}" y1="{cy}" x2="{cx + 520 * math.cos(a):.0f}" '
            f'y2="{cy + 520 * math.sin(a):.0f}" stroke-width="{w:.1f}"/>'
        )
    # The stem stays solid. Without it the radial fan stops reading as a
    # mushroom losing its gills and starts reading as a wing or a shell.
    stem = f'<path d="{STEM}" fill="{INK}" transform="translate(0,-22)"/>'
    return clipped(
        f'<g stroke="{INK}" stroke-linecap="butt">{"".join(out)}</g>{stem}',
        solid_to=236,
    )


def stepped() -> str:
    out = []
    for x0, x1, dense in [(X0 + 76, X0 + 150, True), (X0 + 150, 460, False)]:
        step, r = (20, 9) if dense else (34, 7)
        y, row = 108, 0
        while y < 470:
            x = x0 + (step / 2 if row % 2 else 0)
            while x < x1:
                out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}"/>')
                x += step
            y += step
            row += 1
    return clipped(f'<g fill="{INK}">{"".join(out)}</g>', solid_to=X0 + 76)


def outline() -> str:
    dash = 'stroke-dasharray="4 36" stroke-linecap="round"'
    return (
        f'<defs><clipPath id="L"><rect width="{X0}" height="512"/></clipPath></defs>'
        f'<g clip-path="url(#L)">'
        f'<path d="{CAP}" fill="{INK}" transform="translate(0,-22)"/>'
        f'<path d="{STEM}" fill="{INK}" transform="translate(0,-22)"/></g>'
        f'<path d="{CAP}" fill="none" stroke="{INK}" stroke-width="20" {dash} '
        f'transform="translate(0,-22)"/>'
        f'<path d="{STEM}" fill="none" stroke="{INK}" stroke-width="20" {dash} '
        f'transform="translate(0,-22)"/>'
    )


def bands() -> str:
    out, n, h = [], 11, 30
    for i in range(n):
        w = X0 + 264 * ramp(i / (n - 1), 0.9)
        out.append(f'<rect x="0" y="{104 + i * h}" width="{w:.0f}" height="{h - 7}"/>')
    return clipped(f'<g fill="{INK}">{"".join(out)}</g>', solid_to=0)


def top_down() -> str:
    """Cap and upper stem solid; the stem BASE comes apart.

    The first attempt dissolved everything below the cap, which took the
    stem with it and left a jellyfish. Keeping the stem means the mark
    still reads as a mushroom, and it puts the uncertainty exactly where
    it belongs: the base is where the volva is, and it is the part most
    people leave in the ground.

    The falling dots also read as spores, which is an accident worth
    keeping -- it ties this mark to the spore-print idea.
    """
    out, n = [], 7
    for i in range(n):
        r = 17 * ramp(i / (n - 1), 0.85)
        if r < 2.5:
            continue
        y = 352 + i * 27
        spread = 1.0 + 0.5 * (i / (n - 1))
        for col in range(5):
            x = 256 + (col - 2) * 34 * spread
            out.append(f'<circle cx="{x:.0f}" cy="{y}" r="{r:.1f}"/>')
    solid = (
        f'<path d="{CAP}" fill="{INK}" transform="translate(0,-22)"/>'
        f'<path d="{STEM}" fill="{INK}" transform="translate(0,-22)"/>'
    )
    return (
        f'<defs><clipPath id="t"><rect width="512" height="352"/></clipPath></defs>'
        f'<g clip-path="url(#t)">{solid}</g>'
        f'<g fill="{INK}">{"".join(out)}</g>'
    )


VARIANTS = [
    ("a-big-stipple", "Big Stipple", big_stipple,
     "The original idea with far fewer, far larger dots, and the fade starting "
     "at 36%. Seven countable columns rather than a gradient."),
    ("b-blocks", "Blocks", blocks,
     "A pixel dissolve. Hard edges survive scaling in a way soft ones never do, "
     "and squares read as data rather than as decay."),
    ("c-slices", "Slices", slices,
     "Vertical bars thinning to nothing. The simplest dissolve there is, and the "
     "likeliest to still work at 29&nbsp;px."),
    ("d-gill-slices", "Gill Slices", gill_slices,
     "The dissolve follows gills radiating from the stem, so it is the same "
     "mushroom losing its gills rather than an arbitrary left-to-right fade. "
     "Joins this idea to the other one you liked."),
    ("e-stepped", "Stepped", stepped,
     "Three flat zones: solid, half, sparse. No gradient anywhere, and the most "
     "mechanically robust of the eight."),
    ("f-outline", "Outline", outline,
     "Solid, and then the shape persists only as a dashed line. The most elegant "
     "and the most fragile."),
    ("g-bands", "Bands", bands,
     "Horizontal strips of decreasing length &mdash; a mushroom coming apart line "
     "by line, like a print that only half developed."),
    ("h-top-down", "Top Down", top_down,
     "Cap and stem solid, the base coming apart. The uncertainty is where it "
     "really is &mdash; the base is where the volva is, and the part most people "
     "leave in the ground. The falling dots read as spores, which was an "
     "accident and is worth keeping."),
]


def main() -> int:
    here = pathlib.Path(__file__).parent
    for key, _, fn, _ in VARIANTS:
        (here / f"{key}.svg").write_text(svg(fn()))
    (here / "_meta.json").write_text(
        json.dumps([[k, n, d] for k, n, _, d in VARIANTS], indent=2)
    )
    print(f"wrote {len(VARIANTS)} variants of Half Known")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
