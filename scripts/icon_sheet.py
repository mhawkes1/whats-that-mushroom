"""Put the real app icon into `docs/screenshots/`.

    python scripts/icon_sheet.py

The masthead shows the mark as a cream silhouette floating on a
photograph, with no ground under it. That is **not the logo** -- the logo
is a cream mushroom on a moss plate -- so a screenshot set that contained
only app screens never once showed the brand mark as anybody actually
meets it. Martin's point, 2026-11-08.

Composed from `app/assets/` rather than drawn here, for the same reason
`build_icons.py` derives those from one SVG: a copy kept by hand drifts,
and this one would drift into showing a logo the phone does not.

Both masks are the real ones.

**iOS** rounds the square itself, so the asset is a plain square and the
corner radius belongs to the platform. 22.37% approximates the squircle
closely enough at this size; it is not a value to copy into anything that
ships.

**Android** composites `adaptive-icon.png` over `adaptiveIcon
.backgroundColor` and then lets the *launcher* choose the mask. The circle
is the worst case and so the one worth looking at.

The mark fills more of the Android tile than the iOS one -- 87% against
62% -- and that is the composition working rather than a mistake: a circle
has less area than the square it is cut from, so content has to be larger
inside it to carry the same visual weight. `ANDROID_FILL` 0.58 of a 108dp
canvas is 62.6dp of ink, inside both the 72dp viewport and the 66dp safe
circle.
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "app" / "assets"
OUT = ROOT / "docs" / "screenshots" / "00-app-icon.png"

WIDTH = 780                 # the width every other screenshot in the set is
TILE = 300
PAPER = (255, 255, 255)     # theme.colour.background
INK = (27, 31, 23)          # theme.colour.text
MUTED = (74, 85, 68)        # theme.colour.textMuted

# Android: the layers are 108dp, the system reserves the outer 18dp a side
# for parallax, and the mask is inscribed in the central **72dp** -- so 72
# is what the crop has to be. 66dp is the *safe zone*, the circle whose
# contents survive every mask shape a launcher might pick; it is a design
# constraint on the artwork, not the viewport, and cropping to it here
# showed the mark bigger than any phone does.
ANDROID_VISIBLE = 72 / 108


def rounded(img: Image.Image, radius_fraction: float) -> Image.Image:
    img = img.convert("RGBA")
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, img.width - 1, img.height - 1),
        radius=round(img.width * radius_fraction), fill=255,
    )
    img.putalpha(mask)
    return img


def circled(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, img.width - 1, img.height - 1), fill=255)
    img.putalpha(mask)
    return img


def main() -> int:
    app = json.loads((ROOT / "app" / "app.json").read_text())["expo"]
    ground = app["android"]["adaptiveIcon"]["backgroundColor"]

    ios = rounded(Image.open(ASSETS / "icon.png").resize((TILE, TILE), Image.LANCZOS), 0.2237)

    # The launcher's own compositing: foreground over the declared colour,
    # then the mask. Doing it any other way shows an icon nobody has.
    fg = Image.open(ASSETS / "adaptive-icon.png").convert("RGBA")
    plate = Image.new("RGBA", fg.size, ground)
    plate.alpha_composite(fg)
    keep = round(fg.width * ANDROID_VISIBLE)
    off = (fg.width - keep) // 2
    android = circled(
        plate.crop((off, off, off + keep, off + keep)).resize((TILE, TILE), Image.LANCZOS)
    )

    gap, pad, cap = 60, 48, 46
    sheet = Image.new("RGB", (WIDTH, pad * 2 + TILE + cap), PAPER)
    x = (WIDTH - (TILE * 2 + gap)) // 2
    sheet.paste(ios, (x, pad), ios)
    sheet.paste(android, (x + TILE + gap, pad), android)

    d = ImageDraw.Draw(sheet)
    for label, left in (("iOS", x), ("Android, circular mask", x + TILE + gap)):
        d.text((left, pad + TILE + 14), label, fill=INK)
    d.text((x, pad + TILE + 32), f"cream #f6f3ea on moss {ground}", fill=MUTED)

    sheet.save(OUT)
    print(f"  {OUT.relative_to(ROOT)}  {sheet.width}x{sheet.height}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
