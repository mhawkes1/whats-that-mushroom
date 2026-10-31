#!/usr/bin/env python3
"""Derive the home screen's masthead assets from a photograph and the mark.

    python scripts/build_masthead.py

Writes two files, neither of which is ever edited by hand:

    app/assets/masthead.jpg     the woodland band behind the title
    app/assets/mark-cream.png   the Funga mark, cream, transparent

**Why the darkening is baked in rather than done with an overlay.** The band
carries cream text, and a scrim applied at render time is a second thing that
has to arrive. On a slow decode the photograph can paint before the gradient
does, and for that frame the title is cream on a sunlit moss bank -- which is
the one state this image must never be in. Shipping it dark means the worst
case is a dark band with no text yet, rather than text nobody can read.

**Which photograph.** Martin's, 31 October 2026: a red *Russula* on a
sphagnum bank. The crop is the bottom third, full width, which holds no
mushroom and -- unlike the frame this replaced -- no conifer needles and no
twigs. Two bands were shipped before it, both from a bolete-on-moss frame,
and both had debris lying across the moss just above the title; the eye goes
to a stick before it goes to the name.
That matters beyond composition -- the masthead this replaced was a choice
edible shown as a specimen portrait, which is the opening every foraging app
uses and an implication on an app whose whole claim is that it will not tell
you what is safe to eat. Woodland says what the screen should say.

The band is cut at the masthead's own aspect. A 2.32:1 band cannot be taken
from a 0.75:1 photograph by CSS or by `resizeMode` without throwing the sides
away, so the crop happens here, once, at full resolution.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "app" / "assets"

# The photograph, committed, so the masthead is regenerable rather than
# merely present. It is reduced from the 3,472px original to 2,000px, which
# is still ample for a 1,200px band, because the point is reproducibility
# and not archival. Martin has the full-resolution frame.
#
# This project has twice lost something it could have kept: run one's
# `calibration.json`, which cannot be reconstructed without the images and
# the checkpoint, and its `manifest.parquet`. A derived asset whose source
# lives only on somebody's phone is the same shape of mistake, cheaper to
# avoid.
DEFAULT_SOURCE = ROOT / "docs" / "design" / "masthead-source.jpg"

# The masthead is 132pt tall across a 306pt phone: 2.318:1. Rendered at 3x
# for a modern display, with a little width in hand.
BAND_ASPECT = 306 / 132
BAND_WIDTH = 1200

# The region of the source frame to take, as fractions of its width and
# height. Flush to the bottom edge, and in from the left.
#
# The first version took the full width from 65% down. That cleared the
# mushroom but kept two things Martin spotted on the rendered masthead: a
# conifer needle lying across the moss just above the title, and brown
# stems along the left edge. Neither is a flaw in the photograph; both are
# debris at the top of a band that is otherwise one even texture, and the
# eye goes to them before it goes to the name.
#
# Dropping below the needle means a shorter band, which means a narrower
# one at a fixed aspect -- so the window moves right as well as down. The
# source region is still 2,472px wide against a 1,200px output, so nothing
# is upscaled.
CROP_X_FRACTION = 0.0             # full width: this frame needs no trimming
CROP_FLUSH_BOTTOM = True          # the clean sheet of moss is the bottom third

# How dark to ship it, measured against the scrim it will actually sit
# under -- `theme.colour.photoScrim`, which is black at 0.62.
#
# **This frame needs almost no darkening.** Unmodified, its worst case over
# the real scrim is 7.50:1 -- already AAA on the brightest moss a letter can
# land on. The 8% below comes off for headroom, not for legibility, and
# takes it to 8.4:1.
#
# That is worth knowing because the two frames before it did need it, and
# the first of those was got wrong in an instructive way: it was baked
# against the gradient in a mock-up rather than against the token the app
# uses, arrived double-darkened at 11.64:1, and the moss Martin chose for
# being moss had gone almost black. A photograph of nothing. Found by
# launching the client and looking at it, which is the only way this class
# of fault has ever been found here.
#
# So: measure the frame, do not inherit the last frame's numbers.
BRIGHTNESS = 0.92
SATURATION = 1.02

MARK_PX = 168                      # 56pt at 3x
CAP = ("M 96 286 C 96 60 416 60 416 286 C 416 304 362 312 256 312 "
       "C 150 312 96 304 96 286 Z")
STEM = ("M 206 312 C 199 374 195 432 200 466 C 205 496 307 496 312 466 "
        "C 317 432 313 374 306 312")
CREAM = "#f6f3ea"


def build_band(source: Path, out: Path) -> tuple[int, int]:
    from PIL import Image, ImageEnhance

    im = Image.open(source)
    w, h = im.size
    x0 = round(w * CROP_X_FRACTION)
    band_w = w - x0
    band_h = round(band_w / BAND_ASPECT)
    y = (h - band_h) if CROP_FLUSH_BOTTOM else 0
    if y < 0:
        raise SystemExit(
            f"{source.name} is {w}x{h}; a {BAND_ASPECT:.2f}:1 band {band_w}px "
            f"wide needs {band_h}px of height and the frame has {h}."
        )
    if band_w < BAND_WIDTH:
        raise SystemExit(
            f"the crop is {band_w}px wide and the output is {BAND_WIDTH}px; "
            f"that would upscale the photograph."
        )
    band = im.crop((x0, y, w, y + band_h))
    band = band.resize((BAND_WIDTH, round(BAND_WIDTH / BAND_ASPECT)), Image.LANCZOS)
    band = ImageEnhance.Brightness(band).enhance(BRIGHTNESS)
    band = ImageEnhance.Color(band).enhance(SATURATION)
    band.convert("RGB").save(out, "JPEG", quality=84, optimize=True)
    return band.size


def build_mark(out: Path) -> None:
    """The mark as a transparent PNG, because the client has no SVG renderer.

    `expo-image-picker` is the only image dependency in the client; there is
    no react-native-svg, and adding one to draw two curves would be a
    dependency for a decoration. A PNG generated from the same path data the
    icons come from cannot drift from them.
    """
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" '
        f'width="{MARK_PX}" height="{MARK_PX}">'
        f'<g fill="{CREAM}" stroke="{CREAM}" stroke-width="33.3" '
        f'stroke-linejoin="round" stroke-linecap="round" '
        f'transform="translate(256,216) scale(0.90) translate(-256,-256)">'
        f'<path d="{CAP}"/><path d="{STEM}" stroke-linecap="butt"/></g></svg>'
    )
    js = r"""
const { chromium } = require('playwright');
const fs = require('fs');
const [svgPath, outPath, size] = process.argv.slice(2);
(async () => {
  const b = await chromium.launch({ args: ['--no-sandbox'] });
  const p = await b.newPage({ viewport: { width: +size, height: +size },
                              deviceScaleFactor: 1 });
  await p.setContent(`<style>html,body{margin:0;background:transparent}</style>`
                     + fs.readFileSync(svgPath, 'utf8'));
  await p.screenshot({ path: outPath, omitBackground: true });
  await b.close();
})();
"""
    with tempfile.TemporaryDirectory() as tmp:
        sp = Path(tmp) / "mark.svg"
        jp = Path(tmp) / "shot.js"
        sp.write_text(svg)
        jp.write_text(js)
        subprocess.run([
            "node", str(jp), str(sp), str(out), str(MARK_PX)
        ], check=True, cwd=ROOT)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE,
                    help="the photograph to cut the band from "
                         "(default: docs/design/masthead-source.jpg)")
    ap.add_argument("--mark-only", action="store_true")
    args = ap.parse_args()

    ASSETS.mkdir(parents=True, exist_ok=True)
    build_mark(ASSETS / "mark-cream.png")
    print(f"  mark-cream.png   {MARK_PX}x{MARK_PX}, transparent")

    if args.mark_only:
        return 0
    if not args.source.exists():
        raise SystemExit(f"no such photograph: {args.source}")
    size = build_band(args.source, ASSETS / "masthead.jpg")
    kb = (ASSETS / "masthead.jpg").stat().st_size // 1024
    print(f"  masthead.jpg     {size[0]}x{size[1]}, {kb} KB, "
          f"brightness {BRIGHTNESS} saturation {SATURATION}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
