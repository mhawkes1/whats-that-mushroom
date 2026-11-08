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
mushroom and -- unlike the frames this replaced -- no conifer needles and no
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

# The masthead's own shape, which MUST match `AppHeader`'s `header` height
# or the asset is cropped on the way in.
#
# It did not match for several days: the band was generated at 306/132 while
# the container was 306x150, so `resizeMode="cover"` scaled to fill and threw
# about 12% off the sides -- the shipped masthead was more zoomed than
# anything measured here, and silently. `app/test/masthead.test.ts` now reads
# both numbers and refuses a mismatch.
#
# 132pt, which is the band Martin has been pointing at in every comparison
# sheet since 31 October.
#
# This is the whole of the confusion, and it was an aspect bug rather than a
# matter of taste. Every sheet rendered the band at the shape the generator
# produced, 306/132 = 2.32:1. The app's header was 306x150 = 2.04:1, so
# `cover` filled the height and threw roughly 12% off the sides. The sheets
# were therefore showing a WIDER, less zoomed band than the app had ever
# displayed -- so "too close up" and "the crop in the sheet is better" were
# the same complaint, and a taller band was the wrong answer to it.
#
# 180pt was that wrong answer: it does show more of the frame, but it does
# so by reaching further up into the shadowed middle of the photograph and
# by taking 30pt more of the screen.
# 390, which is the band's REAL width: it is full-bleed, so it spans the
# whole screen, not the content column.
#
# This was 306 -- the content width, 390 minus two 24pt gutters -- from the
# moment the band was first cut, and `masthead.test.ts` asserted it. Both
# were wrong together, which is why neither caught it. Measured in the
# running client on 2026-11-08: the band is 360x132, 390x132 and 430x132 on
# the three phone widths, never 306. An asset cut at 2.318:1 inside a
# 2.955:1 box means `resizeMode="cover"` matches the width and throws
# **22%** off the top and bottom -- so every masthead this project has
# shipped has been a tighter crop than the one anybody measured. Third time
# this exact fault has appeared; the first two were caught by looking at the
# app, and so was this one.
#
# **There is no single correct value, and that is the part to understand.**
# The container's aspect is the device's width over 132, so it runs 2.73
# (360pt) to 3.26 (430pt). Whichever aspect the asset is cut at, `cover`
# crops the other way on some phones: cut wider than the box and it trims
# the sides, narrower and it trims top and bottom. 390 is the reference
# device and splits the difference -- about 13% either way at the extremes.
# What follows from that is a composition rule, not a constant: **keep the
# subject out of the outer eighth, on every side.** A frame whose interest
# is at the left and right edges loses it on a small phone.
HEADER_WIDTH_PT = 390
HEADER_HEIGHT_PT = 132
BAND_ASPECT = HEADER_WIDTH_PT / HEADER_HEIGHT_PT
# Rendered well above 3x of 306pt, with width in hand.
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
CROP_FLUSH_BOTTOM = True          # the bottom third. See below.

# **Bottom third of the frame, sharp, dimmed to 0.92.** Martin's call on
# 2026-10-31, having seen both running in the client.
#
# It went to the top third for a few hours, because he said this band read
# as too much of a close-up -- which it does. The top is focused past the
# moss and reads as a woodland floor at walking distance rather than a macro
# of one cushion. Shown side by side in the app he preferred this one: the
# top band's softness is depth of field, not distance, and a blurred
# masthead loses the moss texture that made the photograph worth using.
#
# Two things from that detour are worth keeping.
#
# **The crop cannot fix a close-up.** The band is already the frame's full
# width, so at a fixed 2.32:1 there is no zooming out left -- more vertical
# scene means cropping the sides, which zooms further IN. If a future
# masthead reads too close, it needs a different photograph, not a different
# crop. His other two frames were checked and both have their mushroom
# sitting in exactly the receding-moss zone that would otherwise have solved
# it.
#
# **Measure the frame; do not inherit the last frame's numbers.** An earlier
# frame was baked against a mock-up's gradient rather than the real token,
# arrived double-darkened at 11.64:1, and the moss went black.
#
# **1.00 is not "no decision", it is Martin's decision of 2026-11-03.** The
# band was dimmed to 0.92 and laid under a 0.62 scrim, for 8.3:1 and moss
# that read as dark woodland rather than as the sphagnum in his frame. He
# was shown the same crop at four depths with the worst case against each,
# and chose the brightest: no dimming here, and `theme.colour.mastheadScrim`
# at 0.30 in the client.
#
# The cost is stated where it is paid, in `theme.ts`: **2.7:1** on the
# brightest tuft a letter can land on, which is under AA and under the 3:1
# large text gets. `textHalo` carries the lettering instead. If this ever
# needs undoing, the lever is the scrim token, not this constant -- the
# asset is now simply the photograph.
BRIGHTNESS = 1.00
SATURATION = 1.02

MARK_PX = 168                      # 56pt at 3x


def _mark_geometry():
    """The launcher icon's own paths, imported rather than copied.

    These were duplicated here for one commit, which is exactly how the
    masthead's mushroom and the launcher's would quietly stop being the same
    drawing -- the ebook's field data is generated from the taxonomy for the
    same reason, and two hand-kept copies of anything in this project have
    drifted every time. `docs/logo/mark.py` is the source of truth; this
    reads it.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_funga_mark", ROOT / "docs" / "logo" / "mark.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.CAP, m.STEM_OPEN, m.DY, m.CREAM


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
    cap, stem, dy, cream = _mark_geometry()
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" '
        f'width="{MARK_PX}" height="{MARK_PX}">'
        f'<g fill="{cream}" stroke="{cream}" stroke-width="30" '
        f'stroke-linejoin="round" stroke-linecap="round" '
        f'transform="translate(0,{dy})">'
        f'<path d="{cap}"/><path d="{stem}" stroke-linecap="butt"/></g></svg>'
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
