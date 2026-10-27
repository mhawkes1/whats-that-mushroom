#!/usr/bin/env python3
"""Draw each candidate palette as the screen that matters most.

    python scripts/palette_variants.py && python scripts/palette_sheet.py

A palette cannot be judged as swatches. The question is not whether the
greens are nice, it is whether a lethal-ambiguity warning still shouts when
it is surrounded by them -- so every variant is drawn as the
`dangerous_group` result screen, which is the one carrying a DEADLY
candidate, a SERIOUS one, a TOXIC one, and a species the app has nothing to
say about, all at once.

The mark is monochrome, so it takes `text` in every variant. That is the
point of a black-and-white mark: it cannot clash, and the palette is free.

Content is copied from the real recording in `docs/walkthrough.json`, so
the words and percentages are the server's rather than invented.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
MARK = ROOT / "docs" / "logo" / "funga-mark-transparent.svg"

RENDER_JS = """
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: %d, height: 900 },
                              deviceScaleFactor: 2 });
  await p.goto('file://' + process.argv[2]);
  await p.waitForTimeout(1800);
  await p.screenshot({ path: process.argv[3], fullPage: true });
  await b.close();
})();
"""


def mark_inner() -> str:
    s = MARK.read_text()
    s = re.sub(r"^<svg[^>]*>", "", s)
    s = re.sub(r"</svg>\\s*$", "", s)
    return s.replace('stroke="#231e17"', 'stroke="currentColor"')


def scene() -> dict:
    data = json.loads((ROOT / "docs" / "walkthrough.json").read_text())
    for s in data["scenes"]:
        if s["verdict"] == "dangerous_group":
            return s["result"]
    raise SystemExit("no dangerous_group scene in the recording")


HAZARD = {"DEADLY": "Can kill", "SERIOUS": "Causes serious illness",
          "TOXIC": "Causes illness"}


def phone(key: str, name: str, pal: dict, blurb: str, r: dict,
          results: list, solid_header: bool = False) -> str:
    # A solid chrome-green band with cream on it, or the pale tint with ink.
    head_bg = pal["canopy"] if solid_header else pal["canopySurface"]
    head_ink = pal["onAccent"] if solid_header else pal["text"]
    def row(c: dict) -> str:
        tox = c["toxicity"]
        label = HAZARD.get(tox)
        stripe = (pal["danger"] if tox in ("DEADLY", "SERIOUS")
                  else pal["caution"] if tox == "TOXIC" else pal["border"])
        colour = pal["danger"] if tox in ("DEADLY", "SERIOUS") else pal["caution"]
        common = (c.get("common_names") or [""])[0]
        return f"""
        <div class="cand" style="background:{pal['surface']};
             border-color:{pal['danger'] if tox == 'DEADLY' else 'transparent'}">
          <div class="stripe" style="background:{stripe}"></div>
          <div class="cbody">
            <div class="csci" style="color:{pal['text']}">{c['scientific_name']}</div>
            <div class="ccom" style="color:{pal['textMuted']}">{common}</div>
            {f'<div class="chaz" style="color:{colour}">{label}</div>' if label else ''}
          </div>
          <div class="cpc" style="color:{pal['textFaint']}">
            {round(c['confidence'] * 100)}%</div>
        </div>"""

    # The meta block sits on the SHEET's background, not the variant's, so
    # it takes a fixed ink. The first draft used the palette's own muted
    # colour and rendered D's checklist in pale grey on near-white.
    checks = "".join(
        f'<li>{c["check"]}</li>' for c in results if c["ok"]
    )
    return f"""
    <div class="col">
      <div class="phone" style="background:{pal['background']};
           border-color:{pal['border']}">
        <div class="head" style="background:{head_bg};
             border-color:{pal['lichen']}">
          <div class="brand" style="color:{head_ink}">
            <svg viewBox="0 0 512 512" class="mk">{mark_inner()}</svg>
            <div>
              <div class="wm">Funga</div>
              <div class="gold" style="background:{pal['accent']}"></div>
            </div>
          </div>
          <div class="sos" style="background:{pal['danger']};
               color:{pal['onAccent']}">+</div>
        </div>
        <div class="body">
          <div class="kind" style="color:{pal['danger']}">dangerous_group</div>
          <div class="hl" style="color:{pal['text']}">{r['headline']}</div>
          <div class="warn" style="background:{pal['dangerSurface']};
               color:{pal['danger']}; border-color:{pal['danger']}">
            {r['warnings'][0]}
          </div>
          <div class="lab" style="color:{pal['textFaint']}">CANDIDATES</div>
          {''.join(row(c) for c in r['candidates'][:5])}
          <div class="btn" style="background:{pal['accent']};
               color:{pal['onAccent']}">Answer a question</div>
        </div>
      </div>
      <div class="meta">
        <div class="nm">{key}. {name}</div>
        <p class="bl">{blurb}</p>
        <div class="sw">{''.join(
            f'<span title="{n}" style="background:{v}"></span>'
            for n, v in pal.items())}</div>
        <ul class="ck">{checks}</ul>
      </div>
    </div>"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--variants",
                    default=str(ROOT / "docs" / "palettes" / "variants.json"))
    ap.add_argument("--out", default=str(ROOT / "docs" / "palettes" / "sheet.png"))
    args = ap.parse_args()

    variants = json.loads(pathlib.Path(args.variants).read_text())
    r = scene()
    width = 300 * len(variants) + 40 * (len(variants) + 1)

    cols = "".join(
        phone(v["key"], v["name"], v["palette"], v["blurb"], r, v["results"],
              v.get("solid_header", False))
        for v in variants
    )
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:wght@600&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
 body{{margin:0;padding:38px;background:#f2f1ee;font-family:Inter,sans-serif;
      width:{width}px;color:#231e17}}
 h1{{font-family:Fraunces,serif;font-size:30px;margin:0 0 8px}}
 .sub{{color:#5c5447;font-size:14.5px;margin:0 0 28px;max-width:820px;line-height:1.6}}
 .strip{{display:flex;gap:40px}}
 .col{{width:300px}}
 .phone{{border-radius:26px;border:1px solid;overflow:hidden;
        box-shadow:0 8px 26px rgba(35,30,23,.16)}}
 .head{{display:flex;justify-content:space-between;align-items:flex-start;
       padding:14px 15px;border-bottom:1px solid}}
 .brand{{display:flex;gap:10px;align-items:center}}
 .mk{{width:30px;height:30px;flex:0 0 auto}}
 .wm{{font-family:Fraunces,serif;font-size:19px;line-height:1}}
 .gold{{height:2px;width:36px;margin-top:5px;border-radius:1px}}
 .sos{{width:30px;height:30px;border-radius:15px;display:grid;place-items:center;
      font-weight:700;font-size:17px}}
 .body{{padding:15px}}
 .kind{{font-size:9.5px;font-weight:700;letter-spacing:.13em;
       font-family:ui-monospace,monospace;margin-bottom:7px}}
 .hl{{font-family:Fraunces,serif;font-size:19px;line-height:1.2;margin-bottom:11px}}
 .warn{{border:1px solid;border-radius:11px;padding:11px 12px;font-size:12px;
       font-weight:600;line-height:1.45;margin-bottom:15px}}
 .lab{{font-size:9.5px;font-weight:700;letter-spacing:.13em;margin-bottom:8px}}
 .cand{{display:flex;align-items:center;gap:10px;border-radius:11px;
       overflow:hidden;margin-bottom:6px;border:1px solid}}
 .stripe{{width:4px;align-self:stretch;min-height:44px}}
 .cbody{{flex:1;padding:8px 0;min-width:0}}
 .csci{{font-size:12.5px;font-style:italic;font-weight:600}}
 .ccom{{font-size:11px}}
 .chaz{{font-size:9.5px;font-weight:700;margin-top:2px}}
 .cpc{{font-size:12.5px;padding-right:11px;font-variant-numeric:tabular-nums}}
 .btn{{border-radius:11px;padding:11px;text-align:center;font-weight:700;
      font-size:13.5px;margin-top:13px}}
 .meta{{margin-top:16px}}
 .nm{{font-family:Fraunces,serif;font-size:19px;margin-bottom:5px}}
 .bl{{font-size:12.5px;color:#5c5447;line-height:1.55;margin:0 0 10px}}
 .sw{{display:flex;flex-wrap:wrap;gap:3px;margin-bottom:10px}}
 .sw span{{width:17px;height:17px;border-radius:4px;border:1px solid #0001}}
 .ck{{margin:0;padding-left:16px;font-size:10.5px;line-height:1.6;color:#5c5447}}
 .ck li{{margin-bottom:1px}}
</style></head><body>
<h1>Funga &mdash; palette variants</h1>
<p class="sub">Each drawn as the <code>dangerous_group</code> result, because that
is the one screen carrying a DEADLY candidate, a SERIOUS one, a TOXIC one and a
species the app has nothing to say about, all at once. Words and percentages are
from the real recording. All four pass every rule
<code>app/test/theme.test.ts</code> enforces &mdash; the ticked list under each is
what it clears, not a wish. The mark is monochrome so it takes the text colour in
every one; that is what a black-and-white mark buys you.</p>
<div class="strip">{cols}</div>
</body></html>"""

    tmp = pathlib.Path(tempfile.mkdtemp())
    (tmp / "sheet.html").write_text(html)
    (tmp / "r.js").write_text(RENDER_JS % width)
    subprocess.run(["node", str(tmp / "r.js"), str(tmp / "sheet.html"), args.out],
                   check=True, cwd=str(tmp))
    print(f"  {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
