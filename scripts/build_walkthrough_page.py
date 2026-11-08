#!/usr/bin/env python3
"""Put the recording into the page, so the two cannot drift.

    python scripts/capture_walkthrough.py          # record the server
    python scripts/build_walkthrough_page.py       # fill the page from it

`docs/walkthrough.html` carries one empty JSON block and reads everything it
displays out of it. This script fills that block from `docs/walkthrough.json`
and nothing else, for the same reason `build_ebook.py` fills the book from the
taxonomy: two hand-kept copies of the same claims drift, and the drift is
silent.

It also *slims* the recording on the way in -- the capture is 56 KB of full
API responses and the page needs a fifth of it. Trimming here rather than in
the capture keeps the capture a faithful record of what the server said,
which is the thing a reviewer may want to check.

Nothing is composed. If a verdict, warning or question looks wrong on the
page, it was wrong in the server's response.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THEME = ROOT / "app" / "src" / "lib" / "theme.ts"

# The page's copy of the app's palette, DERIVED rather than kept by hand.
#
# It was kept by hand until 2026-11-08 and it had drifted: the page was
# still painting the app in October's paper cream with a gold accent, three
# palette changes after `theme.ts` went moss-on-white. Nobody noticed
# because the page renders perfectly either way -- it just shows an app
# that no longer exists, on the most shareable surface the project has.
#
# Same argument as the ebook's field data being generated: two hand-kept
# copies of one fact drift, and the drift is silent. The left-hand side is
# the CSS variable the page's own rules use; the right is the key in
# `theme.colour`. A key that disappears from the theme now fails the build.
PALETTE = {
    "bg": "background",
    "surface": "surface",
    "raised": "surfaceRaised",
    "border": "border",
    "text": "text",
    "muted": "textMuted",
    "faint": "textFaint",
    "danger": "danger",
    "danger-surface": "dangerSurface",
    "caution": "caution",
    "caution-surface": "cautionSurface",
    "confident": "confident",
    "accent": "accent",
    "canopy": "canopy",
    "canopy-surface": "canopySurface",
    "on-accent": "onAccent",
    "on-disabled": "onDisabled",
}

ROOT_BLOCK = re.compile(
    r"(/\* The app's own palette[^*]*\*/\n)(?:  --app-[a-z-]+: [^;]+;\n)+",
)


def theme_colours() -> dict[str, str]:
    """Read `colour` out of theme.ts.

    A brace counter rather than a flat regex, because `theme.ts` carries
    several objects of `name: 'value'` pairs -- `cover` among them, which is
    where the gold this page used to use still lives -- and a flat scan
    would mix them.
    """
    src = THEME.read_text()
    start = src.index("colour: {") + len("colour: {")
    depth, end = 1, start
    while depth:
        ch = src[end]
        depth += (ch == "{") - (ch == "}")
        end += 1
    body = src[start:end - 1]
    return dict(re.findall(r"^\s*(\w+): '([^']+)',", body, re.M))


def repaint(html: str) -> tuple[str, int]:
    """Rewrite the --app-* block from theme.ts, or refuse."""
    colours = theme_colours()
    missing = [k for k in PALETTE.values() if k not in colours]
    if missing:
        raise SystemExit(
            "  REFUSING: theme.colour no longer has "
            + ", ".join(missing)
            + "\n  The page cannot be painted from a palette that moved under"
              " it.\n  Fix PALETTE in this script against app/src/lib/theme.ts."
        )
    block = "".join(
        f"  --app-{var}: {colours[key]};\n" for var, key in PALETTE.items()
    )
    html, n = ROOT_BLOCK.subn(lambda m: m.group(1) + block, html, count=1)
    if not n:
        raise SystemExit("  REFUSING: no --app-* block found in the page.")

    # The other direction: a variable the CSS still uses that nothing emits
    # any more. `--app-gold` was exactly this -- the palette dropped gold and
    # two rules went on referring to it, which CSS resolves to nothing rather
    # than to an error.
    used = set(re.findall(r"var\(--app-([a-z-]+)\)", html))
    orphans = sorted(used - set(PALETTE))
    if orphans:
        raise SystemExit(
            "  REFUSING: the page uses --app-"
            + ", --app-".join(orphans)
            + " and nothing defines them.\n  A var() with no value silently"
              " renders as nothing at all."
        )
    return html, len(PALETTE)

# Confident first, then progressively less willing to answer. The capture
# finds the verdicts in whatever order the stub happens to produce them, and
# the page tells a story.
SCENE_ORDER = ["species", "group", "uncertain", "dangerous_group", "out_of_scope"]

BLOCK = re.compile(
    r'(<script id="walkthrough" type="application/json">)(.*?)(</script>)',
    re.DOTALL,
)


def slim_candidate(c: dict) -> dict:
    """Short keys, because this ships in the page body.

    `toxicity` comes across as the enum *name*, never its value -- an
    IntEnum's number is an unlabelled 1-4 scale whose dangerous end reads
    like the good one.
    """
    common = c.get("common_names") or []
    return {
        "n": c["scientific_name"],
        "c": common[0] if common else "",
        "p": round(c["confidence"], 4),
        "t": c["toxicity"],
    }


def slim_question(q: dict) -> dict:
    return {
        "label": q["label"],
        "prompt": q["prompt"],
        "how": q.get("how") or "",
        "effort": q.get("effort") or "",
        "options": q.get("options") or [],
        "rationale": q.get("rationale") or "",
        "safety_note": q.get("safety_note") or "",
    }


def slim_result(r: dict, n_candidates: int, n_questions: int) -> dict:
    questions = r.get("questions") or []
    return {
        "verdict": r["verdict"],
        "headline": r["headline"],
        "detail": r.get("detail") or "",
        "deadly_in_play": r["deadly_in_play"],
        "warnings": r.get("warnings") or [],
        "calibrated": r["calibrated"],
        "model_version": r["model_version"],
        "candidates": [slim_candidate(c) for c in r["candidates"][:n_candidates]],
        "questions": [slim_question(q) for q in questions[:n_questions]],
        # How many the engine actually offered, which is not how many are
        # shown. A page that silently truncated to one would misreport the
        # interrogation flow as thinner than it is.
        "n_questions": len(questions),
    }


def slim(captured: dict, n_candidates: int, n_questions: int) -> dict:
    scenes = [
        slim_result(s["result"], n_candidates, n_questions)
        for s in captured["scenes"]
    ]
    scenes.sort(key=lambda s: SCENE_ORDER.index(s["verdict"]))

    return {
        "captured_at": captured["captured_at"],
        "health": captured["health"],
        "disclaimer": {
            "heading": captured["disclaimer"]["heading"],
            "body": captured["disclaimer"]["body"],
            "version": captured["disclaimer"]["version"],
            "acks": [
                {"s": a["statement"], "b": a["because"]}
                for a in captured["disclaimer"]["acknowledgements"]
            ],
        },
        "scenes": scenes,
        "follow_ups": [
            {
                "answered": f["answered"],
                "result": slim_result(f["result"], n_candidates, n_questions),
            }
            for f in captured["follow_ups"]
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--capture", default=str(ROOT / "docs" / "walkthrough.json"))
    ap.add_argument("--page", default=str(ROOT / "docs" / "walkthrough.html"))
    ap.add_argument("--candidates", type=int, default=8,
                    help="candidate rows to show per verdict")
    ap.add_argument("--questions", type=int, default=1,
                    help="questions to show per verdict")
    args = ap.parse_args()

    captured = json.loads(Path(args.capture).read_text())
    data = slim(captured, args.candidates, args.questions)
    payload = json.dumps(data, separators=(",", ":"))

    page = Path(args.page)
    html = page.read_text()
    if not BLOCK.search(html):
        raise SystemExit(
            f"{page} has no <script id=\"walkthrough\"> block to fill."
        )
    # A literal </script> inside the payload would end the block early. None
    # of the taxonomy's prose contains one, but a slash-escape costs nothing
    # and the alternative is a page that silently stops rendering.
    payload = payload.replace("</", "<\\/")
    html = BLOCK.sub(lambda m: m.group(1) + payload + m.group(3), html, count=1)
    html, n_colours = repaint(html)
    page.write_text(html)

    verdicts = ", ".join(s["verdict"] for s in data["scenes"])
    print(f"  {page.relative_to(ROOT)}  <-  {len(payload):,} bytes of recording")
    print(f"  captured   {data['captured_at']}")
    print(f"  health     n_classes={data['health']['n_classes']} "
          f"model_loaded={data['health']['model_loaded']} "
          f"calibrated={data['health']['calibrated']} "
          f"taxonomy_reviewed={data['health']['taxonomy_reviewed']}")
    print(f"  verdicts   {verdicts}")
    print(f"  follow-ups {len(data['follow_ups'])}")
    print(f"  palette    {n_colours} colours from app/src/lib/theme.ts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
