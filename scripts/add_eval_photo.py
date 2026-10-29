#!/usr/bin/env python3
"""Put a photograph into the evaluation set with its metadata removed.

    python scripts/add_eval_photo.py ~/Pictures/IMG_4821.jpg --as 09.jpg

**Why this is a script and not a copy.** Every one of the first eight real
photographs carried GPS. They were never committed -- `eval/photos/` is
ignored and git has never held an image -- but "the photographs are safe
because the gitignore is right" is one mistake away from false, and the
mistake is somebody attaching one to an email, a bug report or a chat.
Martin asked for them deleted on 2026-10-29 for exactly this reason, and
deleting them is a fix that has to be remembered every time. Stripping on
the way in does not.

**Orientation is applied, not dropped.** A phone usually stores a portrait
photograph as landscape pixels plus an EXIF orientation flag. Discarding
the metadata without first rotating the pixels hands the model a sideways
mushroom, which would show up later as a mysteriously bad score on real
photographs and be blamed on distribution shift. `ImageOps.exif_transpose`
bakes the rotation in; everything else goes.

What is removed: GPS, camera make and model, serial numbers, the capture
timestamp, software, and any maker note. What survives is the picture.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PHOTOS = ROOT / "eval" / "photos"


def strip(src: Path, dest: Path) -> dict:
    from PIL import Image, ImageOps

    with Image.open(src) as im:
        before = len(im.getexif())
        had_gps = 34853 in im.getexif()
        # Rotate the pixels to match the orientation flag BEFORE the flag
        # is thrown away, or a portrait photograph is served sideways.
        upright = ImageOps.exif_transpose(im)
        # A fresh image pasted into, rather than a save of `upright`:
        # that object still carries `info` from the original, and PIL
        # writes `info["exif"]` back out when it is there.
        clean = Image.new(upright.mode, upright.size)
        clean.paste(upright)
        dest.parent.mkdir(parents=True, exist_ok=True)
        clean.save(dest, format="JPEG", quality=92)

    with Image.open(dest) as check:
        after = len(check.getexif())
    return {"before": before, "after": after, "had_gps": had_gps,
            "kb": dest.stat().st_size // 1024}


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("photo", nargs="+", help="the file(s) to add")
    ap.add_argument("--as", dest="name", default=None,
                    help="filename in eval/photos (one input only)")
    args = ap.parse_args()

    if args.name and len(args.photo) > 1:
        print("--as takes one photograph at a time.", file=sys.stderr)
        return 2

    for i, raw in enumerate(args.photo):
        src = Path(raw)
        if not src.exists():
            print(f"  No such file: {src}", file=sys.stderr)
            return 2
        if args.name:
            dest = PHOTOS / args.name
        else:
            # Next free two-digit name, so the manifest keys stay short
            # and a re-added photograph never silently replaces another.
            taken = {p.stem for p in PHOTOS.glob("*.jpg")}
            n = 1
            while f"{n:02d}" in taken:
                n += 1
            dest = PHOTOS / f"{n:02d}.jpg"
        if dest.exists():
            print(f"  {dest.name} already exists; refusing to overwrite.",
                  file=sys.stderr)
            return 2

        info = strip(src, dest)
        gps = "GPS REMOVED" if info["had_gps"] else "no GPS"
        print(f"  {src.name}  ->  eval/photos/{dest.name}   "
              f"{info['before']} tags -> {info['after']}, {gps}, "
              f"{info['kb']} KB")

    print("\n  Add a row to eval/real-photos.csv for each, and fill in "
          "`confirmed_by`.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
