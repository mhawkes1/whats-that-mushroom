#!/usr/bin/env python3
"""Render marks at true device pixels and magnify, so small sizes can be judged.

    python docs/logo/truepx.py round7/x0-original round7/x7-split --out cmp.png

This exists because a comparison sheet lies about small sizes. The sheets in
every round so far are screenshotted at deviceScaleFactor 2 or 3, so a tile
labelled "29" is really 58 or 87 device pixels and is flattered by a factor
of four to nine in area. On that evidence I told Martin the round-five
outline clogged at 29 px and offered to fix it. Rendered at one device pixel
per CSS pixel, it does not clog, and the "fix" -- merging the cap and stem
into a single path -- was a regression: it smears the cap-stem junction into
a grey mass at exactly the sizes it was supposed to rescue.

So: one device pixel per CSS pixel, captured, then magnified with
nearest-neighbour so the actual pixel grid is visible. Anti-aliasing is the
thing being judged here and it must not be re-sampled away.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import tempfile

HERE = pathlib.Path(__file__).parent
PAPER = "#f6f3ea"

CAPTURE_JS = r"""
const { chromium } = require('playwright');
const fs = require('fs');
const jobs = JSON.parse(process.argv[2]);
(async () => {
  const b = await chromium.launch();
  // deviceScaleFactor: 1 is the whole point. Anything else is a lie about
  // what a 29 px icon looks like.
  const p = await b.newPage({ viewport: { width: 220, height: 90 },
                              deviceScaleFactor: 1 });
  for (const j of jobs) {
    await p.setContent(`<body style="margin:0;background:${j.ground}">` +
      `<svg viewBox="0 0 512 512" width="${j.px}" height="${j.px}" ` +
      `style="display:block"><rect width="512" height="512" ` +
      `fill="${j.ground}"/>${j.art}</svg></body>`);
    await p.waitForTimeout(60);
    await p.screenshot({ path: j.out,
                         clip: { x: 0, y: 0, width: j.px, height: j.px } });
  }
  await b.close();
})();
"""


def art(svg_path: pathlib.Path) -> str:
    """The mark's contents, with its own ground rect removed."""
    s = svg_path.read_text()
    s = re.sub(r"^<svg[^>]*>", "", s)
    s = re.sub(r"</svg>\s*$", "", s)
    return re.sub(r'<rect width="512" height="512" fill="[^"]*"/>', "", s, count=1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("marks", nargs="+",
                    help="paths relative to docs/logo, without .svg")
    ap.add_argument("--sizes", default="29,16")
    ap.add_argument("--zoom", type=int, default=11)
    ap.add_argument("--out", default=str(HERE / "truepx.png"))
    args = ap.parse_args()

    from PIL import Image, ImageDraw

    sizes = [int(x) for x in args.sizes.split(",")]
    tmp = pathlib.Path(tempfile.mkdtemp())
    jobs = []
    for key in args.marks:
        svg = HERE / f"{key}.svg"
        if not svg.exists():
            raise SystemExit(f"no such mark: {svg}")
        for px in sizes:
            jobs.append({
                "art": art(svg), "px": px, "ground": PAPER,
                "out": str(tmp / f"{key.replace('/', '_')}-{px}.png"),
            })

    script = tmp / "capture.js"
    script.write_text(CAPTURE_JS)
    subprocess.run(["node", str(script), json.dumps(jobs)], check=True,
                   cwd=str(tmp))

    Z, PAD, TOP, LAB = args.zoom, 26, 40, 160
    row_h = TOP + max(sizes) * Z + PAD
    width = LAB + sum(px * Z + PAD for px in sizes) + PAD
    sheet = Image.new("RGB", (width, row_h * len(args.marks)), (247, 246, 243))
    d = ImageDraw.Draw(sheet)
    d.text((PAD, 12), f"True device pixels, magnified {Z}x  -  "
                      + " and ".join(f"{p} px" for p in sizes),
           fill=(35, 30, 23))

    for i, key in enumerate(args.marks):
        y0 = i * row_h + TOP
        d.text((PAD, y0 + 40), key.split("/")[-1], fill=(35, 30, 23))
        x = LAB
        for px in sizes:
            im = Image.open(tmp / f"{key.replace('/', '_')}-{px}.png").convert("RGB")
            sheet.paste(im.resize((px * Z, px * Z), Image.NEAREST), (x, y0))
            d.rectangle([x - 1, y0 - 1, x + px * Z, y0 + px * Z],
                        outline=(200, 194, 180))
            x += px * Z + PAD

    sheet.save(args.out)
    print(f"  {args.out}  ({len(args.marks)} marks at {sizes})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
