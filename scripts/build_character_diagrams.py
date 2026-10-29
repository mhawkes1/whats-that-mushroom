#!/usr/bin/env python3
"""Draw the cap shapes, because the words do not survive a beginner.

    python scripts/build_character_diagrams.py

**Why these are drawings and not photographs.** A photograph of "a domed
cap" is a photograph of *a species*, and putting one beside an answer
option teaches a resemblance the taxonomy never claimed -- the same reason
the empirical confusion graph is never shown to a user as a lookalike. A
line drawing claims nothing except the shape it is named after.

**Why they matter more than they look.** In this engine a consistent answer
never boosts; it only contradicts. So a user who picks "Domed" when the cap
is conical does not merely fail to help, they push down every species that
lists Conical. The project already declined `Moderately spaced` as a
`gill_spacing` option for exactly this reason -- a bucket a non-expert
cannot judge reliably is a contradiction channel pointed at whatever
happens to be on the other side of it.

Martin asked for these on 2026-10-29, having found `cap_shape` offering six
options under the thinnest guidance in the whole catalogue: twenty-five
characters, "Photograph from the side."

**Generated, never drawn by hand**, for the same reason as the icons and
the ebook's field data: a set kept by hand drifts, and the drift shows up
as a diagram that no longer matches the option it is labelling.

The SVGs are the source and live in `docs/characters/`. The PNGs the client
loads are derived from them by the same chromium rasteriser the app icons
use, because the client has no SVG renderer and adding one for six
drawings is not a trade worth making.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

W, H = 160, 140
INK = "#2f2a24"      # theme.colour.text
STROKE = 5

# Each entry is the cap outline and the stem, drawn as a side profile. The
# stem is the same in all six so the eye compares the one thing that
# differs -- which is the whole job of a set like this.
STEM = "M 72 {y} L 72 124 M 88 {y} L 88 124"

SHAPES: dict[str, dict[str, str]] = {
    "domed": {
        "label": "Domed",
        "cap": "M 26 72 A 54 46 0 0 1 134 72 Z",
        "stem_y": 72,
        "note": "Curved like the back of a spoon. The commonest shape.",
    },
    "flat": {
        "label": "Flat",
        "cap": "M 24 70 Q 80 54 136 70 L 136 76 Q 80 66 24 76 Z",
        "stem_y": 72,
        "note": "Opened right out, the top more or less level.",
    },
    "funnel-shaped": {
        "label": "Funnel-shaped",
        "cap": "M 26 52 Q 80 94 134 52 L 134 62 Q 80 104 26 62 Z",
        "stem_y": 96,
        "note": "Dished in the middle, edges turned up. Holds rain.",
    },
    "cylindrical": {
        "label": "Cylindrical",
        # Open at the bottom. A closed path draws its own base across the
        # cap, which turns a shaggy inkcap into a capsule -- the same fault
        # the app icon's stem had, and the same fix.
        #
        # The sides are PARALLEL and stay that way. Flaring them into a
        # skirt made the stem read better and the shape read worse, which
        # is the wrong trade: "sides nearly parallel" is what the word
        # means, and a drawing that hedges it is not labelling the option.
        "cap": "M 62 92 L 62 44 A 18 22 0 0 1 98 44 L 98 92",
        "stem_y": 92,
        "note": "Taller than wide, sides nearly parallel. Shaggy inkcap.",
    },
    "conical": {
        "label": "Conical",
        "cap": "M 80 26 L 128 84 L 32 84 Z",
        "stem_y": 84,
        "note": "Pointed, like a little tent or a witch's hat.",
    },
    "irregular": {
        "label": "Irregular",
        "cap": "M 24 74 Q 44 48 64 66 Q 80 44 98 64 Q 118 46 136 74 "
               "Q 110 88 80 86 Q 48 88 24 74 Z",
        "stem_y": 86,
        "note": "Lumpy, wavy or lopsided -- no clean shape at all.",
    },
}


def svg_for(spec: dict) -> str:
    stem = STEM.format(y=spec["stem_y"])
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}">\n'
        f'  <g fill="none" stroke="{INK}" stroke-width="{STROKE}" '
        f'stroke-linecap="round" stroke-linejoin="round">\n'
        f'    <path d="{spec["cap"]}"/>\n'
        f'    <path d="{stem}"/>\n'
        f'  </g>\n'
        f'</svg>\n'
    )


def rasterise(jobs: list[dict]) -> bool:
    """Same chromium pass the app icons use. No new client dependency."""
    script = """
const { chromium } = require('playwright');
(async () => {
  const jobs = JSON.parse(process.argv[2]);
  const b = await chromium.launch({ args: ['--headless', '--no-sandbox'] });
  for (const j of jobs) {
    const p = await b.newPage({ viewport: { width: j.w, height: j.h },
                                deviceScaleFactor: 3 });
    await p.setContent(
      `<body style="margin:0">${require('fs').readFileSync(j.svg, 'utf8')}</body>`);
    await p.screenshot({ path: j.out, omitBackground: true });
    await p.close();
  }
  await b.close();
})();
"""
    # Written to a file and invoked as `node <file> <payload>`, matching
    # build_icons.py. `node -e` shifts process.argv by one, which is a
    # silent "undefined is not valid JSON" rather than a useful error.
    import tempfile

    try:
        with tempfile.TemporaryDirectory() as tmp:
            runner = Path(tmp) / "rasterise.js"
            runner.write_text(script, encoding="utf-8")
            subprocess.run(["node", str(runner), json.dumps(jobs)],
                           cwd=ROOT, check=True, capture_output=True, text=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        print(f"  Could not rasterise: {detail.strip()[:300]}", file=sys.stderr)
        return False


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--svg-only", action="store_true")
    args = ap.parse_args()

    svg_dir = ROOT / "docs" / "characters"
    png_dir = ROOT / "app" / "assets" / "characters"
    svg_dir.mkdir(parents=True, exist_ok=True)
    png_dir.mkdir(parents=True, exist_ok=True)

    jobs = []
    for slug, spec in SHAPES.items():
        svg_path = svg_dir / f"cap-{slug}.svg"
        svg_path.write_text(svg_for(spec), encoding="utf-8")
        jobs.append({"svg": str(svg_path), "w": W, "h": H,
                     "out": str(png_dir / f"cap-{slug}.png")})
        print(f"  {spec['label']:<16} {svg_path.relative_to(ROOT)}")

    if args.svg_only:
        print("\n  SVG only; PNGs not rebuilt.\n")
        return 0

    print()
    if not rasterise(jobs):
        print("  SVGs written; PNGs NOT rebuilt. The client loads the PNGs,\n"
              "  so it is still showing the previous set.\n", file=sys.stderr)
        return 1

    for job in jobs:
        out = Path(job["out"])
        print(f"  {out.relative_to(ROOT)}  {out.stat().st_size // 1024} KB")
    print(f"\n  {len(jobs)} diagrams.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
