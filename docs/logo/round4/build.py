#!/usr/bin/env python3
"""Six marks for Funga, built on the Half Known idea Martin picked.

Round three asked which *dissolve* worked. This round asks a different
question, because the app was renamed on 2026-10-27 and that changed the
brief in two ways.

**The name is five characters now, not twenty.** A lockup -- mark beside
wordmark -- is viable for the first time; "What's That Mushroom?" was too
long to sit next to anything. So each mark here is drawn to work both as a
bare square icon and with the word beside it.

**The name no longer says "mushroom".** The old name did that job in the
App Store grid and the mark could be abstract. Now the mark is the only
thing telling a stranger what this is before they read the subtitle, so a
mark that reads as a pleasant abstract shape is a worse mark than it was
last week.

Everything stays *discrete* -- countable dots, bars and zones, never a
smooth gradient -- because round one failed below 48 px for exactly that
reason, and a smooth fade is the first thing scaling destroys. Every mark
is checked at 29 px, which is the Settings icon and the smallest size iOS
will ask for.

The cap keeps its stem in every variant. Round one lost three concepts to
one mistake: a cap drawn without a stem reads as a hill.
"""

from __future__ import annotations

import json
import math
import pathlib

HERE = pathlib.Path(__file__).parent
INK, PAPER = "#231e17", "#f6f3ea"

# The same mushroom as round three, so this reads as a development of the
# idea Martin chose rather than a fresh start.
CAP = ("M 62 266 C 62 112 450 112 450 266 "
       "C 450 282 392 290 256 290 C 120 290 62 282 62 266 Z")
STEM = ("M 204 288 C 197 346 193 398 198 430 "
        "C 203 462 309 462 314 430 C 319 398 315 346 308 288 Z")

DY = -26  # lifts the mushroom so the spore fall has room beneath it


def svg(body: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" '
        'width="512" height="512">'
        f'<rect width="512" height="512" fill="{PAPER}"/>{body}</svg>'
    )


def mushroom(fill: str = INK, dy: int = DY, extra: str = "") -> str:
    return (f'<path d="{CAP}" fill="{fill}" transform="translate(0,{dy})"{extra}/>'
            f'<path d="{STEM}" fill="{fill}" transform="translate(0,{dy})"{extra}/>')


def spore_fall(y0: int, rows: int, cols: int = 5, spread: float = 1.9,
               r0: float = 17.0, gap: int = 27) -> str:
    """Rows of dots falling and fanning, each row smaller than the last.

    Discrete by construction: you can count the rows. The fan is what stops
    it reading as a barcode -- spores drift outward as they fall.
    """
    out = []
    for row in range(rows):
        t = row / max(rows - 1, 1)
        r = r0 * (1 - t) ** 0.62 + 2.6
        y = y0 + row * gap
        step = 34 + row * spread * 2
        for c in range(cols):
            x = 256 + (c - (cols - 1) / 2) * step
            out.append(f'<circle cx="{x:.0f}" cy="{y}" r="{r:.1f}"/>')
    return f'<g fill="{INK}">' + "".join(out) + "</g>"


# --- a. Top Down -------------------------------------------------------------
# Martin's pick from round three, with the fade started higher as he asked.
# The uncertainty sits at the stem base, which is where it honestly is: the
# volva is down there, and it is the part almost everyone leaves in the soil.

def a_top_down() -> str:
    clip = 318
    body = (
        f'<defs><clipPath id="t"><rect width="512" height="{clip}"/></clipPath></defs>'
        f'<g clip-path="url(#t)">{mushroom()}</g>'
        + spore_fall(clip + 16, rows=7)
    )
    return svg(body)


# --- b. Cut Lengthways -------------------------------------------------------
# An F that is also a mushroom sliced down the middle -- which is the exact
# thing the app asks a user to do ("cut the mushroom in half lengthways,
# including the very base of the stem"). The middle arm is the ring.

def b_cut_lengthways() -> str:
    body = f'''<g fill="{INK}">
      <path d="M 150 118 C 150 96 196 84 262 84 C 372 84 436 128 436 168
               C 436 182 400 188 300 188 L 300 150 L 150 150 Z"/>
      <rect x="150" y="150" width="54" height="300" rx="6"/>
      <rect x="150" y="250" width="166" height="46" rx="10"/>
      <rect x="150" y="84" width="54" height="80" rx="6"/>
    </g>
    <g fill="{INK}" opacity="0.999">
      <circle cx="238" cy="356" r="13"/><circle cx="292" cy="356" r="13"/>
      <circle cx="232" cy="404" r="9.5"/><circle cx="296" cy="404" r="9.5"/>
      <circle cx="226" cy="448" r="6"/><circle cx="302" cy="448" r="6"/>
    </g>'''
    return svg(body)


# --- c. Half Cap -------------------------------------------------------------
# The bluntest statement of the idea: solid on the left, outline on the
# right. Nothing to lose at small sizes because there is nothing small in it.

def c_half_cap() -> str:
    body = (
        '<defs>'
        '<clipPath id="L"><rect x="0" y="0" width="256" height="512"/></clipPath>'
        '<clipPath id="R"><rect x="256" y="0" width="256" height="512"/></clipPath>'
        '</defs>'
        f'<g clip-path="url(#L)">{mushroom()}</g>'
        f'<g clip-path="url(#R)" fill="none" stroke="{INK}" stroke-width="17" '
        'stroke-linejoin="round" stroke-dasharray="30 26" stroke-linecap="round">'
        f'<path d="{CAP}" transform="translate(0,{DY})"/>'
        f'<path d="{STEM}" transform="translate(0,{DY})"/>'
        '</g>'
    )
    return svg(body)


# --- d. Gill Fan -------------------------------------------------------------
# The underside, which is where identification actually happens, and the view
# the app asks for third ("turn it over -- this one carries the most").
# Martin liked the gill mark in round two; this is that idea with the
# dissolve applied to it.

def d_gill_fan() -> str:
    cx, cy, rin, rout = 256, 262, 34, 196
    blades = []
    for i in range(26):
        a = math.pi * (i + 0.5) / 26
        t = i / 25
        # Gills shorten toward one side rather than fading, so the loss is
        # countable at any size.
        reach = rout * (1 - 0.46 * max(0.0, (t - 0.42) / 0.58) ** 1.25)
        x1, y1 = cx - math.cos(a) * rin, cy - math.sin(a) * rin
        x2, y2 = cx - math.cos(a) * reach, cy - math.sin(a) * reach
        blades.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>')
    body = (
        f'<g stroke="{INK}" stroke-width="13" stroke-linecap="round">'
        + "".join(blades) + "</g>"
        f'<path d="M 60 262 C 60 142 452 142 452 262 Z" fill="none" '
        f'stroke="{INK}" stroke-width="16" stroke-linecap="round" '
        'stroke-dasharray="1 0"/>'
        f'<rect x="228" y="262" width="56" height="150" rx="14" fill="{INK}"/>'
        f'<circle cx="256" cy="262" r="26" fill="{INK}"/>'
    )
    return svg(body)


# --- e. Spore Print ----------------------------------------------------------
# The deposit itself, on the half-black half-white card. This is the app's
# signature feature and the one thing no competitor asks a user to do, so it
# is worth testing as the mark even though it is not a mushroom shape.

def e_spore_print() -> str:
    """The deposit, which is *radial* -- gills drop spores in lines.

    The first version was a plain disc and read as a ball or a moon. The
    radiating gaps are what make it a spore print rather than a circle,
    and they are cut as negative space so there is nothing thin to lose.
    """
    cx, cy, r = 256, 232, 182
    wedges = []
    for i in range(22):
        a0 = math.tau * i / 22
        a1 = a0 + math.tau / 22 * 0.42
        x0, y0 = cx + math.cos(a0) * r, cy + math.sin(a0) * r
        x1, y1 = cx + math.cos(a1) * r, cy + math.sin(a1) * r
        wedges.append(
            f'<path d="M {cx} {cy} L {x0:.1f} {y0:.1f} '
            f'A {r} {r} 0 0 1 {x1:.1f} {y1:.1f} Z"/>'
        )
    dots = []
    for row in range(5):
        t = row / 4
        rr = 15.0 * (1 - t) ** 0.6 + 2.4
        y = 408 + row * 26
        n = 7 - row
        for c in range(n):
            x = 256 + (c - (n - 1) / 2) * (46 + row * 6)
            dots.append(f'<circle cx="{x:.0f}" cy="{y}" r="{rr:.1f}"/>')
    body = (
        '<defs><clipPath id="s"><rect width="512" height="380"/></clipPath></defs>'
        f'<g clip-path="url(#s)" fill="{INK}">'
        f'<circle cx="{cx}" cy="{cy}" r="{r}"/>'
        f'<g fill="{PAPER}">{"".join(wedges)}</g>'
        f'<circle cx="{cx}" cy="{cy}" r="26" fill="{INK}"/>'
        '</g>'
        f'<g fill="{INK}">{"".join(dots)}</g>'
    )
    return svg(body)


# --- f. Four Spores ----------------------------------------------------------
# The fewest elements that still say mushroom-plus-doubt. Built as the
# small-size insurance policy: if everything else dies at 29 px, this will
# not, because there is nothing in it under about 20 px of its own.

def f_four_spores() -> str:
    clip = 300
    body = (
        f'<defs><clipPath id="f"><rect width="512" height="{clip}"/></clipPath></defs>'
        f'<g clip-path="url(#f)">{mushroom()}</g>'
        f'<g fill="{INK}">'
        '<circle cx="256" cy="336" r="25"/>'
        '<circle cx="190" cy="392" r="19"/><circle cx="322" cy="392" r="19"/>'
        '<circle cx="256" cy="446" r="13"/>'
        '</g>'
    )
    return svg(body)


MARKS = [
    ("a-top-down", "Top Down",
     "Your round-three pick, with the fade started higher as you asked. The "
     "uncertainty sits at the stem base, which is where it honestly is -- the "
     "volva is down there, and it is the part almost everyone leaves in the "
     "soil. The falling dots read as spores, which was an accident worth keeping."),
    ("b-cut-lengthways", "Cut Lengthways",
     "An F that is also a mushroom sliced down the middle -- the exact thing "
     "the app tells you to do when it asks about bruising. The middle arm of "
     "the F is the ring. Doubles as a monogram if you ever need one letter."),
    ("c-half-cap", "Half Cap",
     "The bluntest version: solid on the left, dashed outline on the right. "
     "Nothing in it is small, so nothing in it can be lost. The one to beat "
     "on robustness."),
    ("d-gill-fan", "Gill Fan",
     "The underside, which is where identification actually happens and the "
     "third photo the app asks for. You liked the gill mark in round two; "
     "this is that idea with the dissolve applied, the gills shortening "
     "rather than fading so the loss stays countable."),
    ("e-spore-print", "Spore Print",
     "The deposit itself. It is the app's signature feature and the one thing "
     "no competitor asks a user to do -- but it is not a mushroom shape, so "
     "it leans hardest on the subtitle to explain the app."),
    ("f-four-spores", "Four Spores",
     "The fewest elements that still say mushroom and doubt. The insurance "
     "policy: if everything else dies at 29 px this will not, because nothing "
     "in it is small."),
]

BUILDERS = {
    "a-top-down": a_top_down,
    "b-cut-lengthways": b_cut_lengthways,
    "c-half-cap": c_half_cap,
    "d-gill-fan": d_gill_fan,
    "e-spore-print": e_spore_print,
    "f-four-spores": f_four_spores,
}


def main() -> int:
    for key, _, _ in MARKS:
        (HERE / f"{key}.svg").write_text(BUILDERS[key]())
        print(f"  {key}.svg")
    (HERE / "_meta.json").write_text(json.dumps(MARKS, indent=2))
    print(f"\n  {len(MARKS)} marks + _meta.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
