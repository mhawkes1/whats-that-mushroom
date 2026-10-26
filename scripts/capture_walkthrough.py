#!/usr/bin/env python3
"""Record what the real server says, so it can be replayed somewhere else.

    python scripts/capture_walkthrough.py --out docs/walkthrough.json

Hits a running API and writes down every response verbatim: the disclaimer,
the field form, several identifications, and what happens when a question is
answered. Nothing here is composed -- every verdict, warning, candidate list
and follow-up question is whatever `server/app/safety.py` and
`server/app/interrogation.py` actually returned.

The point is to be able to show the app's behaviour to somebody who cannot
run it -- a mycologist, a reviewer, Martin on a phone -- without rewriting
the safety layer in JavaScript. A second copy of that logic would drift from
the first, and the drift would be silent and in the one place this project
cannot afford it. A recording cannot drift. It can only go stale, and it
stamps itself so you can tell.

The species names come from the stub classifier and are meaningless. The
decisions taken about them are not.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def synth_cap(brightness: float, seed: int = 7) -> bytes:
    """A plausible cap on grass. Deterministic, so a capture is repeatable."""
    import random

    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

    random.seed(seed)
    w = h = 900
    img = Image.new("RGB", (w, h), (62, 78, 44))
    d = ImageDraw.Draw(img)
    for _ in range(5000):
        x, y = random.randint(0, w), random.randint(0, h)
        g = random.randint(-18, 18)
        d.ellipse([x, y, x + random.randint(3, 14), y + random.randint(8, 26)],
                  fill=(62 + g, 92 + g, 46 + g))
    cx, cy, r = 450, 470, 250
    for i in range(r, 0, -1):
        t = i / r
        shade = int(196 - 70 * (1 - t) ** 0.6)
        d.ellipse([cx - i, cy - int(i * 0.82), cx + i, cy + int(i * 0.82)],
                  fill=(shade, int(shade * 0.78), int(shade * 0.58)))
    for _ in range(260):
        a = random.random() * math.tau
        rr = random.random() ** 0.5 * r * 0.95
        x, y = cx + math.cos(a) * rr, cy + math.sin(a) * rr * 0.82
        s = random.randint(4, 13)
        d.ellipse([x - s, y - s * 0.8, x + s, y + s * 0.8], fill=(150, 112, 78))
    img = ImageEnhance.Brightness(img.filter(ImageFilter.GaussianBlur(1.1)))
    buf = io.BytesIO()
    img.enhance(brightness).save(buf, "JPEG", quality=88)
    return buf.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--out", default=str(ROOT / "docs" / "walkthrough.json"))
    args = ap.parse_args()

    import requests

    def get(path: str) -> dict:
        r = requests.get(f"{args.api}{path}", timeout=30)
        r.raise_for_status()
        return r.json()

    health = get("/health")
    print(f"  API reports {health['n_classes']} species, "
          f"model_loaded={health['model_loaded']}")

    captured: dict = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "health": health,
        "disclaimer": get("/disclaimer"),
        "field_form": get("/field-form"),
        "scenes": [],
    }

    # Hunt for one example of each verdict the safety layer can return, by
    # varying the photograph. The stub keys its output off image content, so
    # different brightness means a different (meaningless) ranking -- and
    # therefore a different (meaningful) decision about that ranking.
    wanted = ["dangerous_group", "species", "uncertain", "out_of_scope", "group"]
    found: dict[str, dict] = {}

    for i in range(900):
        if not wanted:
            break
        image = synth_cap(0.55 + i * 0.0012)
        r = requests.post(
            f"{args.api}/identify",
            files={"image": ("cap.jpg", image, "image/jpeg")},
            data={"month": 10, "latitude": 52.56, "longitude": -2.75},
            timeout=60,
        )
        r.raise_for_status()
        result = r.json()
        verdict = result["verdict"]
        if verdict in wanted:
            wanted.remove(verdict)
            found[verdict] = result
            print(f"  captured {verdict:<18} {result['headline']}")

    # The interrogation flow, on the refusal: answer its own top question and
    # record what the engine does with the answer.
    follow_ups = []
    refusal = found.get("dangerous_group")
    if refusal and refusal["questions"]:
        question = refusal["questions"][0]
        for option in question["options"][:4]:
            r = requests.post(
                f"{args.api}/answer",
                json={
                    "observation_id": refusal["observation_id"],
                    "character_key": question["key"],
                    "answer": option,
                },
                timeout=60,
            )
            if r.status_code == 200:
                follow_ups.append({"answered": option, "result": r.json()})
                print(f"  answered {question['key']}={option!r} "
                      f"-> {r.json()['verdict']}")

    for verdict, result in found.items():
        captured["scenes"].append({"verdict": verdict, "result": result})
    captured["follow_ups"] = follow_ups

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(captured, indent=2))
    print(f"\n  Wrote {out} -- {len(captured['scenes'])} scenes, "
          f"{len(follow_ups)} follow-ups")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
