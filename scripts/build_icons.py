#!/usr/bin/env python3
"""Build the app icon set from the chosen mark, and nothing by hand.

    python scripts/build_icons.py

Source of truth is `docs/logo/funga-mark.svg`, written by
`docs/logo/mark.py`. That is Martin's round-five outline with one stroke
removed -- the stem's own top edge, which a closed path drew straight across
the stem and hid under the cap. He spotted it in the rendered icons. The
geometry is otherwise untouched.

One source, every size derived from it, because an icon set kept by hand
drifts the same way two copies of a species list drift, and the drift shows
up as a slightly different mushroom in the one place a user looks every day.

Four things it gets right that are easy to get wrong:

**The iOS icon carries no alpha channel.** App Store submission rejects an
icon with transparency, and it rejects it late -- at upload, after a build.
The file is flattened onto paper and converted to RGB, and there is a check
at the end that asserts it.

**iOS applies its own corner mask**, so the artwork is a full-bleed square
with margin built in rather than pre-rounded. A pre-rounded icon gets
rounded twice and shows pale corners.

**Android's adaptive icon is mostly off-screen.** The foreground is 108dp
of which the central 72dp is visible and only a 66dp circle is guaranteed,
because the launcher picks the mask. Content therefore sits inside about
60% of the canvas -- noticeably smaller than the iOS composition, which
looks wrong in a file browser and correct on a phone.

**The mark is not centred in its own viewBox.** Its bounding box sits about
32 units low, so composing it by dropping the 512 square into a 1024 square
would hang everything slightly below centre on every platform at once. The
box is measured in a browser and recentred. `getBBox` ignores stroke, so
half a stroke is added on each side: icon margins are measured from the ink,
not from the maths.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "docs" / "logo" / "funga-mark.svg"
ASSETS = ROOT / "app" / "assets"

# The ground every icon is composited onto. Moss since 2026-10-31; it was
# paper, and a white plate behind the mark used to show as a ring of the
# wrong cream once a launcher masked to a circle. The same argument holds
# with the new colour, which is why this is a constant and not a literal in
# four places: `app.json`'s two backgroundColor values have to match it, and
# `app/test/icons.test.ts` pins that they do.
MOSS = "#4e6e3f"

# Fraction of the canvas the mark's longest side fills.
IOS_FILL = 0.62
# Smaller, because a launcher may mask away everything outside the central
# circle. 108dp canvas, 72dp visible, 66dp guaranteed.
ANDROID_FILL = 0.58

MEASURE_JS = r"""
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage();
  await p.setContent(process.argv[2]);
  const box = await p.evaluate(() => {
    const g = document.getElementById('mark');
    const b = g.getBBox();
    // getBBox ignores stroke, and a stroked outline's ink extends half a
    // stroke beyond the geometry on every side. Icon margins are measured
    // from the ink, not from the maths.
    const sw = parseFloat(getComputedStyle(g.querySelector('path')).strokeWidth) || 0;
    return { x: b.x - sw / 2, y: b.y - sw / 2,
             width: b.width + sw, height: b.height + sw };
  });
  console.log(JSON.stringify(box));
  await b.close();
})();
"""

RENDER_JS = r"""
const { chromium } = require('playwright');
const jobs = JSON.parse(process.argv[2]);
(async () => {
  const b = await chromium.launch();
  for (const j of jobs) {
    const p = await b.newPage({ viewport: { width: j.size, height: j.size },
                                deviceScaleFactor: 1 });
    await p.setContent(
      `<body style="margin:0">${j.svg}</body>`,
      { waitUntil: 'load' });
    await p.waitForTimeout(80);
    await p.screenshot({ path: j.out, omitBackground: !!j.transparent });
    await p.close();
  }
  await b.close();
})();
"""


def art(svg: pathlib.Path) -> str:
    s = svg.read_text()
    s = re.sub(r"^<svg[^>]*>", "", s)
    s = re.sub(r"</svg>\s*$", "", s)
    return re.sub(r'<rect width="512" height="512" fill="[^"]*"/>', "", s, count=1)


def node(script: str, payload: str, cwd: pathlib.Path) -> str:
    f = cwd / "run.js"
    f.write_text(script)
    r = subprocess.run([sys.executable and "node", str(f), payload],
                       capture_output=True, text=True, cwd=str(cwd))
    if r.returncode:
        raise SystemExit(f"node failed:\n{r.stderr}")
    return r.stdout.strip()


def compose(inner: str, box: dict, size: int, fill: float,
            ground: str | None) -> str:
    """Centre the mark's *ink* in a square and scale it to `fill`."""
    scale = (size * fill) / max(box["width"], box["height"])
    cx = box["x"] + box["width"] / 2
    cy = box["y"] + box["height"] / 2
    tx = size / 2 - cx * scale
    ty = size / 2 - cy * scale
    bg = f'<rect width="{size}" height="{size}" fill="{ground}"/>' if ground else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" '
        f'height="{size}" viewBox="0 0 {size} {size}" '
        f'style="display:block">{bg}'
        f'<g transform="translate({tx:.3f},{ty:.3f}) scale({scale:.5f})">'
        f'{inner}</g></svg>'
    )


def main() -> int:
    from PIL import Image

    if not SOURCE.exists():
        raise SystemExit(f"source mark missing: {SOURCE}")
    inner = art(SOURCE)
    ASSETS.mkdir(parents=True, exist_ok=True)
    tmp = pathlib.Path(tempfile.mkdtemp())

    measured = node(
        MEASURE_JS,
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" '
        f'width="512" height="512"><g id="mark">{inner}</g></svg>',
        tmp,
    )
    box = json.loads(measured)
    print(f"  ink box  x={box['x']:.0f} y={box['y']:.0f} "
          f"w={box['width']:.0f} h={box['height']:.0f}  "
          f"(centre {box['x'] + box['width'] / 2:.0f},"
          f"{box['y'] + box['height'] / 2:.0f} vs canvas 256,256)")

    targets = [
        # name,              size, fill,          ground, transparent
        ("icon.png",         1024, IOS_FILL,      MOSS,   False),
        ("adaptive-icon.png", 1024, ANDROID_FILL, None,   True),
        ("splash-icon.png",   512, 0.70,          None,   True),
        ("favicon.png",        48, 0.74,          MOSS,   False),
    ]

    jobs = []
    for name, size, fill, ground, transparent in targets:
        jobs.append({
            "svg": compose(inner, box, size, fill, ground),
            "size": size,
            "out": str(ASSETS / name),
            "transparent": transparent,
        })
    node(RENDER_JS, json.dumps(jobs), tmp)

    print()
    for name, size, _, _, transparent in targets:
        p = ASSETS / name
        im = Image.open(p)
        if not transparent:
            # Apple rejects an icon with an alpha channel, and rejects it at
            # upload, after a build has been paid for.
            im = im.convert("RGB")
            im.save(p)
            im = Image.open(p)
        assert im.size == (size, size), f"{name} is {im.size}, wanted {size}"
        print(f"  {name:<20} {im.size[0]}x{im.size[1]}  {im.mode}"
              f"{'  (alpha)' if transparent else '  (no alpha)'}")

    ios = Image.open(ASSETS / "icon.png")
    assert ios.mode == "RGB", "the iOS icon must not carry an alpha channel"
    assert "A" not in ios.getbands(), "alpha band present in icon.png"
    print("\n  checked: icon.png has no alpha channel")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
