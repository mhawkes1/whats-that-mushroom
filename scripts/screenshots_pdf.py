"""Bind `docs/screenshots/` into one PDF, for somebody who wants the set.

    node scripts/screenshots.js      # the screens themselves
    python scripts/screenshots_pdf.py

One screen per page, scaled to fit with a margin, in the order a person
meets them rather than the order they are named: the front page first and
the emergency screen last, because that is the one you hope nobody reads.

It was `whats-that-mushroom-screens.pdf` until 2026-11-08, which is the
book's title rather than the app's -- the app has been Funga since
2026-10-27. Nothing referenced the old file, which is the only reason
renaming it was free.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "docs" / "screenshots"
OUT = SHOTS / "funga-screens.pdf"

# A4 at 150 dpi.
PAGE = (1240, 1754)
MARGIN = 60

ORDER = [
    "03-front-page",
    "02-consent-every-box-on-its-own",
    "05-field-notes",
    "07-result",
    "08-result-after-answering",
    "09-history",
    "sp-03-spore-print-guide",
    "10-emergency",
]


def main() -> int:
    missing = [n for n in ORDER if not (SHOTS / f"{n}.png").exists()]
    if missing:
        raise SystemExit(
            "  REFUSING: no screenshot for " + ", ".join(missing)
            + "\n  Run `node scripts/screenshots.js` first; it drives the real"
              " client\n  and these are its output, not files kept by hand."
        )

    pages = []
    for name in ORDER:
        shot = Image.open(SHOTS / f"{name}.png").convert("RGB")
        page = Image.new("RGB", PAGE, "white")
        scale = min((PAGE[0] - 2 * MARGIN) / shot.width,
                    (PAGE[1] - 2 * MARGIN) / shot.height)
        fitted = shot.resize(
            (int(shot.width * scale), int(shot.height * scale)), Image.LANCZOS
        )
        page.paste(fitted, ((PAGE[0] - fitted.width) // 2,
                            (PAGE[1] - fitted.height) // 2))
        pages.append(page)

    pages[0].save(OUT, save_all=True, append_images=pages[1:], resolution=150.0)
    print(f"  {OUT.relative_to(ROOT)}  {len(pages)} pages, "
          f"{OUT.stat().st_size / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
