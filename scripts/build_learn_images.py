"""Derive the Learn card photographs from Martin's committed frames.

Generated, never hand-cropped -- the same argument as `build_icons.py` and
the ebook's field data. A set kept by hand drifts, and here the drift would
show up as one card framed differently from the other three.

    python scripts/build_learn_images.py
    python scripts/build_learn_images.py --ingest <name>=<file.jpg> ...

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

from PIL import Image, ImageOps

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
    "why-i-refuse": ("elfcups", 0.48),
    "photographing-a-mushroom": ("amanita", 0.53),
    "spore-prints": ("waxcaps", 0.50),
    "answers-that-mislead-me": ("bonnets", 0.50),
    # The home screen's single card: the troop of bonnets on haircap moss,
    # Martin's pick. Its own crop rather than a shared file, so the home
    # card and an article card can diverge without one going wrong.
    "home": ("mycena-cluster", 0.50),
}


#: Longest edge of a committed source. The originals are 24 MP.
SOURCE_EDGE = 2000


def upright(path: pathlib.Path) -> Image.Image:
    """Open a photograph the way a person sees it.

    **`ImageOps.exif_transpose` is not optional, and leaving it out shipped
    a sideways card for a day.** Two of the six frames Martin sent carry
    EXIF `Orientation: 8` -- stored 6000x4000 landscape, meant to be
    displayed 4000x6000 portrait. `Image.open().size` reports what is
    STORED, so an ingest that only downscales and strips metadata throws
    the tag away and bakes the wrong rotation in for good.
    The scarlet elf cups went out rotated 90 degrees on 2026-11-21 and
    nothing caught it -- not the build, not the tests, not me looking
    straight at the rendered card -- because **leaf litter has no
    horizon**. A cap-and-stem mushroom would have been obvious at a
    glance; a cup fungus on fallen beech leaves is plausible from any
    angle. Apply the tag first, then strip.
    """
    return ImageOps.exif_transpose(Image.open(path)).convert("RGB")


def ingest(pairs: list[str]) -> int:
    """Turn original photographs into committed sources.

    This step used to be a few lines typed into a shell, which is exactly
    why the orientation bug had nowhere to be fixed: the originals are not
    in the repository, so a fault baked in here is permanent unless the
    person who holds them runs the step again.
    """
    SRC.mkdir(parents=True, exist_ok=True)
    for pair in pairs:
        if "=" not in pair:
            print(f"REFUSING: expected <name>=<file>, got {pair!r}", file=sys.stderr)
            return 1
        name, original = pair.split("=", 1)
        path = pathlib.Path(original)
        if not path.exists():
            print(f"REFUSING: no such file {path}", file=sys.stderr)
            return 1
        im = upright(path)
        scale = SOURCE_EDGE / max(im.size)
        if scale < 1:
            im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
        clean = Image.new("RGB", im.size)   # a fresh image carries no EXIF at all
        clean.paste(im)
        out = SRC / f"{name}.jpg"
        clean.save(out, "JPEG", quality=90, optimize=True)
        print(f"  {name:16} {im.size[0]}x{im.size[1]}  {out.stat().st_size // 1024:>4} KB")
    return 0


def crop(src: Image.Image, focus_y: float) -> Image.Image:
    """Fill WIDTHxHEIGHT, cropping the long axis around `focus_y`."""
    scale = max(WIDTH / src.width, HEIGHT / src.height)
    im = src.resize((round(src.width * scale), round(src.height * scale)), Image.LANCZOS)
    left = (im.width - WIDTH) // 2
    top = round(im.height * focus_y - HEIGHT / 2)
    top = max(0, min(top, im.height - HEIGHT))
    return im.crop((left, top, left + WIDTH, top + HEIGHT))


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--ingest":
        return ingest(sys.argv[2:])

    OUT.mkdir(parents=True, exist_ok=True)
    missing = [s for s, _ in CARDS.values() if not (SRC / f"{s}.jpg").exists()]
    if missing:
        print(f"REFUSING: no source for {sorted(set(missing))} in {SRC}", file=sys.stderr)
        return 1

    for name, (source, focus_y) in CARDS.items():
        # `upright` rather than `Image.open`: the committed sources are
        # already rotated correctly, and a source added by hand may not be.
        card = crop(upright(SRC / f"{source}.jpg"), focus_y)
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
