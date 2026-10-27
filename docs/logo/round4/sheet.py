#!/usr/bin/env python3
"""Lay the six marks out for judging, with the wordmark beside them.

Rebuilt from the SVGs on disk every run. Round one shipped a stale picture
because the sheet inlined the marks and only the marks were regenerated;
this reads them fresh so that cannot happen twice.

Three things it shows that a single large rendering hides:

**29 px.** The Settings icon, and the smallest iOS asks for. A mark that
only works at 512 is a drawing, not a logo.

**A dark ground.** Home screens have wallpaper. A mark tested only on its
own paper square has been tested on the one background it will rarely sit on.

**The lockup.** New this round: the name is five characters, so mark and
wordmark can sit together. "What's That Mushroom?" never could.
"""

from __future__ import annotations

import json
import pathlib
import re

HERE = pathlib.Path(__file__).parent
INK, PAPER = "#231e17", "#f6f3ea"
GOLD = "#9a7612"

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600&family=Inter:wght@400;600&display=swap');
body { margin:0; padding:46px; background:#f7f6f3; font-family:Inter,system-ui,sans-serif;
       width:1240px; color:#231e17; }
h1 { font-family:Fraunces,Georgia,serif; font-size:40px; margin:0 0 8px; }
.sub { color:#5c5447; font-size:16px; margin:0 0 34px; max-width:860px; line-height:1.6; }
.card { display:flex; gap:34px; align-items:flex-start; background:#fffdf7;
        border:1px solid #ddd6c6; border-radius:18px; padding:24px 28px; margin-bottom:16px; }
.marks { display:flex; gap:22px; align-items:flex-end; flex:0 0 auto; }
.cap { font-size:10.5px; color:#8a8173; text-align:center; margin-top:7px; letter-spacing:.05em; }
h2 { font-family:Fraunces,Georgia,serif; font-size:25px; margin:0 0 8px; }
p { margin:0; color:#5c5447; font-size:15px; line-height:1.6; max-width:330px; }
.lock { display:flex; align-items:center; gap:14px; }
.word { font-family:Fraunces,Georgia,serif; font-weight:600; font-size:34px;
        letter-spacing:-0.005em; line-height:1; }
.rule { height:2px; width:40px; background:#9a7612; margin:7px 0 5px; }
.tag { font-family:Inter,sans-serif; font-size:9.5px; color:#5c5447; letter-spacing:.01em; }
"""


def inner(key: str) -> str:
    """The mark's contents, with its own paper rect stripped."""
    body = (HERE / f"{key}.svg").read_text().split(">", 1)[1].rsplit("</svg>", 1)[0]
    return re.sub(r'<rect width="512" height="512" fill="[^"]*"/>', "", body, count=1)


def tile(key: str, px: int, label: str | None = None,
         ground: str = PAPER, radius: str = "22%") -> str:
    """One mark at one size.

    On a dark ground the *mark* is inverted too, not just the rect behind
    it. The first version of this sheet recoloured only the ground and
    produced six identical black squares -- a test that cannot fail is not
    a test, and it looked like a result.
    """
    art = inner(key)
    if ground != PAPER:
        art = art.replace(INK, PAPER)
    cap = f'<div class="cap">{label}</div>' if label else ""
    return (
        f'<div><svg viewBox="0 0 512 512" width="{px}" height="{px}" '
        f'style="border-radius:{radius};display:block">'
        f'<rect width="512" height="512" fill="{ground}"/>{art}</svg>{cap}</div>'
    )


def lockup(key: str) -> str:
    """Mark plus wordmark, the thing that was impossible under the old name."""
    return (
        '<div class="lock">'
        + tile(key, 60)
        + '<div><div class="word">Funga</div><div class="rule"></div>'
          '<div class="tag">I&rsquo;ll tell you when I can&rsquo;t tell.</div></div>'
        + '</div>'
    )


def main() -> int:
    marks = json.loads((HERE / "_meta.json").read_text())
    cards = []
    for key, title, blurb in marks:
        cards.append(
            '<div class="card"><div class="marks">'
            + tile(key, 128, "128")
            + tile(key, 60, "60")
            + tile(key, 29, "29")
            + tile(key, 29, "29 on ink", ground=INK)
            + '</div><div><h2>' + title + '</h2><p>' + blurb + '</p>'
            + '<div style="margin-top:16px">' + lockup(key) + '</div>'
            + '</div></div>'
        )

    html = (
        '<!doctype html><html><head><meta charset="utf-8">'
        f'<style>{CSS}</style></head><body>'
        '<h1>Funga &mdash; logo, round four</h1>'
        '<p class="sub">Six marks built on the Half Known idea you picked, '
        'redrawn for the new name. Each is shown at 128, 60 and 29&nbsp;px, '
        'once on a dark ground because home screens have wallpaper, and once '
        'locked up with the wordmark &mdash; which is new, because a '
        'five-letter name can sit beside a mark and a twenty-character one '
        'could not. Nothing here uses a smooth gradient: every fade is a '
        'countable number of dots, bars or zones, which is what round one got '
        'wrong and what scaling punishes.</p>'
        + "".join(cards) +
        '</body></html>'
    )
    (HERE / "sheet.html").write_text(html)
    print(f"  sheet.html  ({len(marks)} marks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
