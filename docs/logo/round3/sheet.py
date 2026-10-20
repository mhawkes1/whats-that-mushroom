#!/usr/bin/env python3
"""Lay the eight dissolve variants out for comparison.

Rebuilds from the SVGs on disk every time. Round one shipped a stale
picture because the sheet inlined the marks and only the marks were
regenerated; this reads them fresh so that cannot happen again.
"""

from __future__ import annotations

import json
import pathlib
import re

HERE = pathlib.Path(__file__).parent
INK, PAPER = "#231e17", "#f6f3ea"

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600&family=Inter:wght@400&display=swap');
body { margin:0; padding:44px; background:#f7f6f3; font-family:Inter,system-ui,sans-serif; width:1180px; }
h1 { font-family:Fraunces,Georgia,serif; font-size:38px; margin:0 0 6px; color:#231e17; }
.sub { color:#5c5447; font-size:16px; margin:0 0 30px; max-width:800px; line-height:1.55; }
.card { display:flex; gap:32px; align-items:center; background:#fffdf7; border:1px solid #ddd6c6;
        border-radius:18px; padding:22px 28px; margin-bottom:16px; }
.marks { display:flex; gap:24px; align-items:flex-end; }
.smalls { display:flex; gap:15px; align-items:flex-end; }
.cap { font-size:11px; color:#8a8173; text-align:center; margin-top:6px; letter-spacing:.05em; }
h2 { font-family:Fraunces,Georgia,serif; font-size:25px; margin:0 0 7px; color:#231e17; }
p { margin:0; color:#5c5447; font-size:15.5px; line-height:1.55; max-width:410px; }
"""


def inner(key: str) -> str:
    """The mark's contents, with its own background rect stripped."""
    body = (HERE / f"{key}.svg").read_text().split(">", 1)[1].rsplit("</svg>", 1)[0]
    return re.sub(r'<rect width="512" height="512" fill="[^"]*"/>', "", body, count=1)


def tile(key: str, px: int, label: str | None = None, ground: str = PAPER) -> str:
    cap = f'<div class="cap">{label}</div>' if label else ""
    return (
        f'<div><svg viewBox="0 0 512 512" width="{px}" height="{px}" '
        f'style="border-radius:22%;display:block">'
        f'<rect width="512" height="512" fill="{ground}"/>{inner(key)}</svg>{cap}</div>'
    )


def main() -> int:
    variants = json.loads((HERE / "_meta.json").read_text())
    cards = []
    for key, name, why in variants:
        smalls = "".join(tile(key, p, str(p)) for p in (88, 48, 29))
        cards.append(
            f'<div class="card"><div class="marks">{tile(key, 220, "app icon")}'
            f'<div class="smalls">{smalls}</div></div>'
            f'<div class="text"><h2>{name}</h2><p>{why}</p></div></div>'
        )

    page = (
        f'<!doctype html><meta charset="utf-8"><style>{CSS}</style><body>'
        f'<h1>Half Known &mdash; eight dissolves</h1>'
        f'<p class="sub">Round one failed below 48&nbsp;px because the stipple was a '
        f'<em>smooth</em> gradient of tiny dots, and a smooth gradient is exactly what '
        f'scaling destroys. Every one of these is <strong>discrete</strong> &mdash; a '
        f'countable number of columns, blocks, bars or zones &mdash; so shrinking it loses '
        f'detail instead of turning to noise. The fade also starts at about 36% across '
        f'rather than 55%.</p>{"".join(cards)}</body>'
    )
    (HERE / "sheet.html").write_text(page)
    print(f"wrote sheet.html with {len(variants)} variants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
