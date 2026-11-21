"""Derive the Learn card photographs from Martin's committed frames.

Generated, never hand-cropped -- the same argument as `build_icons.py` and
the ebook's field data. A set kept by hand drifts, and here the drift would
show up as one card framed differently from the other three.

    python scripts/build_learn_images.py

Sources are in `docs/design/learn/` at 2000px on the long edge, committed,
so this runs from a fresh clone. The originals are 3-9 MB and stay off the
repository; `eval/photos/**` is gitignored for exactly that reason, which
is also why the Learn cards could not simply point at it.

All five are 6000x4000 Canon frames. The set they replaced was 3472x4624
off a phone, and the difference is not only pixel count: a 3:2 LANDSCAPE
original loses a third of its height to a 2:1 card, where a portrait one
loses two thirds. Four of the five are landscape, so the crop keeps far
more of what was composed.

**Every output is written through a fresh Image, so no EXIF survives.**
The four sources carry no GPS -- checked, the coordinates are NaN -- but a
photograph from a phone is the one asset class in this project that can
publish where somebody was standing, and a build step that strips
unconditionally cannot be caught out by the next frame somebody adds.
"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "design" / "learn"
OUT = ROOT / "app" / "assets" / "learn"

#: 4:3, at 2x for a 390pt card. A 430pt phone needs 764px, so 780 covers
#: the widest phone without paying for a third size.
#:
#: **It was 2:1 until 2026-11-21 and the shape was the whole problem.**
#: Martin asked for the Mycena troop, the Amanita and the waxcaps to be
#: re-cropped "so you can see the whole mushroom" -- all three were losing
#: their stems off the bottom edge. No nudge fixes that: a band keeps a
#: fixed fraction of its source, and the question is whether a mushroom
#: fits in it at all.
#:
#: Measured over the five sources. The four Canon LANDSCAPE frames are
#: 2000x1333, exactly 3:2, so at 2:1 a card threw away a quarter of their
#: height and at 3:2 or taller it uses them WHOLE, uncropped. The Amanita
#: is the one portrait source and decides the rest: 2:1 keeps 33% of its
#: height, 3:2 keeps 44%, and only 4:3 keeps the 50% that reaches the
#: bottom of the stem. 4:3 costs the landscape four 11% of their width,
#: centred, which none of them has anything in.
WIDTH, HEIGHT = 780, 585

#: published name -> (source, focus as a fraction of the source's height).
#: The focus now matters for ONE source. At 4:3 the landscape frames keep
#: 100% of their height, so `crop` clamps `top` to 0 whatever is asked for
#: and only the Amanita's value does anything -- it still loses half its
#: height, so a few hundredths move the cap top or the stem base out of
#: shot. The others are left at 0.5 to say "nothing to decide" rather than
#: deleted, because a source swapped for a portrait one would need them
#: back.
CARDS: dict[str, tuple[str, float]] = {
    "why-i-refuse": ("elfcups", 0.50),
    "photographing-a-mushroom": ("amanita", 0.57),
    "spore-prints": ("waxcaps", 0.50),
    "answers-that-mislead-me": ("bonnets", 0.50),
    # The home screen's single card: the troop of bonnets on haircap moss,
    # Martin's pick. Its own crop rather than a shared file, so the home
    # card and an article card can diverge without one going wrong.
    "home": ("mycena-cluster", 0.50),
}


def crop(src: Image.Image, focus_y: float) -> Image.Image:
    """Fill WIDTHxHEIGHT, cropping the long axis around `focus_y`."""
    scale = max(WIDTH / src.width, HEIGHT / src.height)
    im = src.resize((round(src.width * scale), round(src.height * scale)), Image.LANCZOS)
    left = (im.width - WIDTH) // 2
    top = round(im.height * focus_y - HEIGHT / 2)
    top = max(0, min(top, im.height - HEIGHT))
    return im.crop((left, top, left + WIDTH, top + HEIGHT))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    missing = [s for s, _ in CARDS.values() if not (SRC / f"{s}.jpg").exists()]
    if missing:
        print(f"REFUSING: no source for {sorted(set(missing))} in {SRC}", file=sys.stderr)
        return 1

    for name, (source, focus_y) in CARDS.items():
        with Image.open(SRC / f"{source}.jpg") as src:
            card = crop(src.convert("RGB"), focus_y)
        # A fresh image rather than card.save(exif=None): Pillow carries the
        # source's exif through a crop, and "no argument" is not "strip".
        clean = Image.new("RGB", card.size)
        clean.paste(card)
        path = OUT / f"{name}.jpg"
        clean.save(path, "JPEG", quality=82, optimize=True, progressive=True)
        kb = path.stat().st_size // 1024
        print(f"  {name:28} {source:12} {card.size[0]}x{card.size[1]}  {kb:>3} KB")

    total = sum(p.stat().st_size for p in OUT.glob("*.jpg")) // 1024
    print(f"\n{len(CARDS)} cards, {total} KB in app/assets/learn/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
