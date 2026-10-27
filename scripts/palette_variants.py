#!/usr/bin/env python3
"""Candidate palettes, each run through the rules `theme.test.ts` enforces.

    python scripts/palette_variants.py --out docs/palettes

Martin asked on 2026-10-27 whether the scheme should change now the mark is
black and white, and whether it wants darker greens. A monochrome mark means
the palette is free -- nothing can clash with it -- so the only constraints
left are the ones that were always the real ones, and they are safety
properties rather than taste:

- `danger` must clear **7:1** against every ground it appears on. AAA, not
  AA, because it marks a lethal ambiguity. The old dark-theme red read at
  about 3:1 on paper, which made the most important warning the hardest
  thing on the screen.
- Nothing semantic may be **green**. `POSITIONING.md` kept green out
  entirely because green is the colour of permission, and this app never
  gives a go. Greens are allowed as *chrome* -- header grounds, rules,
  dividers -- and barred from anything that names a species or states an
  outcome.
- The hazard stripes must get **fainter** as the hazard gets milder, with
  no-hazard faintest of all. It once fell through to `textMuted` and drew a
  darker bar than a TOXIC row, so the species the app had nothing to say
  about was the loudest thing in the list.

Every variant below is scored against those, by the same arithmetic the
test suite uses. The report says which pass and which do not; it does not
pick one.
"""

from __future__ import annotations

import argparse
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

CHROME = {"canopy", "lichen", "canopySurface"}


# --- the same maths as theme.test.ts ----------------------------------------

def _lum(hex_: str) -> float:
    v = hex_.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(v[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def rgb(hex_: str) -> tuple[int, int, int]:
    v = hex_.lstrip("#")
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore


def is_green(hex_: str) -> bool:
    r, g, b = rgb(hex_)
    return g > r + 12 and g > b + 12


# --- the variants -----------------------------------------------------------

A_CURRENT = {
    "background": "#f6f3ea", "surface": "#fffdf7", "surfaceRaised": "#efeade",
    "border": "#d9d2c0", "text": "#231e17", "textMuted": "#5c5447",
    "textFaint": "#8a8173", "danger": "#941613", "dangerSurface": "#fbe9e7",
    "caution": "#7d5206", "cautionSurface": "#fbf0d8", "confident": "#2f5a78",
    "accent": "#9a6a24", "onAccent": "#fffdf7", "onDisabled": "#8a8173",
    "canopy": "#3f5d37", "lichen": "#8fa07a", "canopySurface": "#eaefe2",
}

# Same paper, much deeper woodland chrome. The header band becomes a solid
# dark green with cream on it rather than a pale tint.
# `headerOnCanopy` is not a colour: it says whether the header band is the
# pale tint (`canopySurface`, the current look) or the solid chrome green
# (`canopy`, with `onAccent` on it). Darkening `canopy` alone changes
# almost nothing visible, because the band that a user actually sees is
# the tint -- which is how the first draft of this sheet managed to render
# A and B as near-identical.
B_DEEP_CHROME = {**A_CURRENT,
    "canopy": "#20341c", "lichen": "#5d7350", "canopySurface": "#dde5d4",
}

# The paper itself cools from warm bone toward a sage off-white. Stays under
# the green threshold -- a tint, not a hue.
C_SAGE_PAPER = {
    "background": "#f0f2ea", "surface": "#fafcf5", "surfaceRaised": "#e5e9dc",
    "border": "#ccd3c0", "text": "#1c231a", "textMuted": "#4e5749",
    "textFaint": "#7d8678", "danger": "#8f1511", "dangerSurface": "#fae8e5",
    "caution": "#6f4a07", "cautionSurface": "#f7efd6", "confident": "#2a5572",
    "accent": "#8c6420", "onAccent": "#fafcf5", "onDisabled": "#7d8678",
    "canopy": "#1e3119", "lichen": "#5a7050", "canopySurface": "#dbe4d2",
}

# The inversion Martin asked about: deep forest grounds, light text.
#
# Two things had to change from the obvious first draft, and both are
# instructive about why this app went to paper in the first place.
#
# `border` was #38452f, which the hue test flags: a mid-dark green doing a
# structural job. Neutralised to #333a2f.
#
# `danger` was #ff9a92 and it LOST to `caution` on emphasis -- 7.86 against
# 9.11 -- which is precisely the bug from 2026-10-19 reappearing by itself.
# On a dark ground "heavier" means lighter, so the deadliest colour has to
# be the palest thing on the screen. #ffb3ab wins the ordering at 9.39. It
# is a pale pink, and a pale pink as the lethal warning is the cost of the
# inversion rather than a drawing I would defend.
D_DARK_FOREST = {
    "background": "#121a10", "surface": "#1a2417", "surfaceRaised": "#243020",
    "border": "#333a2f", "text": "#eef2e6", "textMuted": "#b3bda9",
    "textFaint": "#8a9480", "danger": "#ffb3ab", "dangerSurface": "#3a1512",
    "caution": "#e8bd6a", "cautionSurface": "#33280f", "confident": "#9ccbe8",
    "accent": "#d9ad5e", "onAccent": "#121a10", "onDisabled": "#8a9480",
    "canopy": "#9fbf92", "lichen": "#6f8862", "canopySurface": "#1d2a1a",
}

# Which variants paint the header with solid `canopy` rather than the tint.
SOLID_HEADER = {"B", "D"}

# Where each one stands, decided 2026-10-27. Martin liked A and B and chose
# to change nothing for now, so this file is a shortlist rather than a
# proposal. Nothing here touches `app/src/lib/theme.ts`; A *is* theme.ts.
STATUS = {
    "A": "SHIPPING -- this is app/src/lib/theme.ts today",
    "B": "APPROVED ALTERNATIVE -- liked, not applied. Reach for this one.",
    "C": "considered, not chosen",
    "D": "considered, not chosen; see the warning in its blurb",
}

VARIANTS = [
    ("A", "Current", A_CURRENT,
     "Warm bone paper, woodland green as a pale header tint. What ships today."),
    ("B", "Deep chrome", B_DEEP_CHROME,
     "The same paper, with the greens taken much darker. The header becomes a "
     "solid forest band with cream on it rather than a mint wash. The smallest "
     "change that answers 'darker greens'."),
    ("C", "Sage paper", C_SAGE_PAPER,
     "The paper itself cools from bone toward sage, and the ink greens with "
     "it. Green throughout without green ever stating anything -- it stays a "
     "tint rather than a hue."),
    ("D", "Dark forest", D_DARK_FOREST,
     "The inversion: deep forest grounds, light text. Every hazard colour has "
     "to be re-derived, because a red chosen for paper is unreadable here. "
     "Passes only after two fixes, both of which say something: a green "
     "border had to be neutralised, and the deadly colour had to become the "
     "PALEST thing on screen to outweigh the toxic one."),
]


# --- the checks -------------------------------------------------------------

def check(p: dict[str, str]) -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        out.append((name, ok, detail))

    worst = min(contrast(p["danger"], p[g])
                for g in ("dangerSurface", "background", "surface"))
    add("danger AAA (7:1) on every ground", worst >= 7, f"worst {worst:.2f}:1")

    c_worst = min(contrast(p["caution"], p[g])
                  for g in ("cautionSurface", "surface"))
    add("caution AA (4.5:1)", c_worst >= 4.5, f"worst {c_worst:.2f}:1")

    t = contrast(p["text"], p["background"])
    add("body text 12:1 on the ground", t >= 12, f"{t:.2f}:1")

    m = contrast(p["textMuted"], p["background"])
    add("muted text 4.5:1", m >= 4.5, f"{m:.2f}:1")

    oa = min(contrast(p["onAccent"], p[g])
             for g in ("accent", "danger", "canopy", "confident"))
    add("onAccent on every filled control", oa >= 4.5, f"worst {oa:.2f}:1")

    greens = [n for n, h in p.items() if n not in CHROME and is_green(h)]
    add("nothing semantic is green", not greens,
        "clean" if not greens else ", ".join(f"{n} {p[n]}" for n in greens))

    b, r = rgb(p["confident"])[2], rgb(p["confident"])[0]
    add("confident reads as information, not hazard", b > r + 20,
        f"blue-red {b - r}")

    d = contrast(p["danger"], p["surface"])
    c = contrast(p["caution"], p["surface"])
    n = contrast(p["border"], p["surface"])
    add("hazard emphasis ordered", d > c > n,
        f"deadly {d:.2f} > toxic {c:.2f} > none {n:.2f}")
    add("a no-hazard row barely marks the page", n < 1.6, f"{n:.2f}")

    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(ROOT / "docs" / "palettes"))
    args = ap.parse_args()
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    report = []
    for key, name, pal, blurb in VARIANTS:
        results = check(pal)
        failed = [r for r in results if not r[1]]
        print(f"\n  {key}. {name}  --  "
              f"{'PASSES' if not failed else f'{len(failed)} FAILURE(S)'}")
        print(f"  {STATUS[key]}")
        print("  " + "-" * 68)
        for label, ok, detail in results:
            print(f"   {'PASS' if ok else 'FAIL'}  {label:<42} {detail}")
        report.append({"key": key, "name": name, "blurb": blurb,
                       "status": STATUS[key],
                       "palette": pal,
                       "solid_header": key in SOLID_HEADER,
                       "results": [{"check": c, "ok": o, "detail": d}
                                   for c, o, d in results]})

    (out / "variants.json").write_text(json.dumps(report, indent=2))
    print(f"\n  wrote {out / 'variants.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
