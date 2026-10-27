#!/usr/bin/env python3
"""Round seven: the round-five outline, measured, and a correction.

Martin picked `round5/m4-outline` specifically, after round six existed --
so this is not "the outline direction" but *that drawing*. Measuring the
two showed he was right that they differ:

| | round 5 (picked) | round 6 |
| --- | --- | --- |
| cap half-width | 195 | 182 |
| cap underside | bulges 24 *below* the rim | tucks 16 *above* it |
| stem | barrels outward | waists inward |
| stem foot | rounded | closed flat |
| stem length | to 439 | to 404 |

Which is why round five reads as generous and round six as narrow. The
bulging underside is most of it: the cap is visibly *thick*, so it reads
as a cap with gills under it rather than a dome balanced on a stick.

**The correction.** Round five's sheet said that drawing clogged at 29 px
and this round set out to rescue it. Rendered at one device pixel per CSS
pixel -- see `docs/logo/truepx.py` -- it does not clog. The sheets are
screenshotted at deviceScaleFactor 2 or 3, so a tile labelled "29" was
really 58 or 87 device pixels; the thing I was reading as a flaw was an
artefact of looking at it wrong. The original holds at 29 and at 16.

Worse, the rescue was a regression. `x1-faithful` merges the cap and stem
into one path to remove the buried stroke, and that removes the cap's
full-width underside with it: the cap becomes a shoulder, the mushroom
starts reading as a tree, and at true 29 px the junction smears into a
grey mass. It is the worst of the four, and it was my idea.

`x7-split` is what the change should have been -- cap closed across its
full width, stem drawn as an open U beneath it, so the only stroke
removed is the one nobody could see. It matches the original and carries
one less path's worth of ink. Take it as the production file if you like;
it is housekeeping, not a rescue.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import re

HERE = pathlib.Path(__file__).parent
ROUND6 = HERE.parent / "round6" / "build.py"
INK, PAPER = "#231e17", "#f6f3ea"

_spec = importlib.util.spec_from_file_location("r6", ROUND6)
r6 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r6)
outline = r6.outline

# Round five's numbers, read off `round5/m4-outline.svg` rather than guessed.
PICKED = dict(
    cap_half=195,
    cap_top=136,
    cap_bottom=252,
    brim=-24,      # the underside bulges *below* the rim
    stem_half=56,
    waist=9,       # barrels outward
    stem_bottom=416,
    base_round=24,
)


def original() -> str:
    """The round-five file itself, for an honest side-by-side.

    Included so the comparison is against the real thing rather than my
    description of it. It is the one with a stroke hidden inside it.
    """
    return (HERE.parent / "round5" / "m4-outline.svg").read_text()


MARKS = [
    ("x0-original", "Round five, as picked",
     "The drawing itself, unchanged. It has a stroke inside it, where the "
     "stem's top edge crosses under the cap -- but at true device pixels "
     "that costs nothing visible. My round-five note that this clogs at "
     "29 px was wrong, and wrong because the sheet was rendered at 3x."),
    ("x1-faithful", "Merged into one path  ·  a regression",
     "The same geometry built as a single continuous path. It removes the "
     "buried stroke and the cap's full-width underside along with it, so "
     "the cap becomes a shoulder and the thing starts reading as a tree. "
     "At true 29 px the junction smears. Kept on the sheet because a "
     "failed idea is worth being able to see."),
    ("x2-light", "Light",
     "The same at stroke 24. The broad cap carries a lighter line better "
     "than round six's narrow one did, so this is more usable than its "
     "equivalent there."),
    ("x3-bold", "Bold",
     "Stroke 38. Confident on a dark ground; watch the gap between cap and "
     "stem start to close at 16."),
    ("x4-small", "Drawn for small",
     "Stroke 25, stem widened to 64 and the underside bulge eased to 14, so "
     "the counters survive. Still unmistakably the same mushroom, which is "
     "the whole trick -- a small-size drawing that reads as a different "
     "logo has failed."),
    ("x7-split", "Split construction  ·  the answer",
     "Cap closed across its full width, stem drawn as an open U hanging "
     "beneath it. The silhouette is your original exactly -- full "
     "underside, cap sitting ON the stem -- and the one stroke that caused "
     "the blotting, the stem's buried top edge, is simply not drawn. "
     "Merging everything into one path had fixed the blot by removing the "
     "underside, which cost the shape: a cap without a full underside is a "
     "shoulder, and the mushroom starts reading as a tree."),
    ("x6-junction", "Rebuild + junction line",
     "The rebuild with the cap/stem junction drawn back in. That line "
     "existed in your original by accident -- it was the stem's top edge "
     "showing through the cap -- and it may be part of what you liked: it "
     "is the difference between a cap *sitting on* a stem and one "
     "continuous shape. Kept separate from the outline so the small-size "
     "cut can drop it, which is the only place it costs anything."),
    ("x5-ringed", "Ringed",
     "One line for the annulus. The feature that says Amanita, and the "
     "first thing lost when it shrinks."),
]

BUILDERS = {
    "x0-original": original,
    "x1-faithful": lambda: outline(**PICKED),
    "x2-light": lambda: outline(**{**PICKED, "stroke": 24}),
    "x3-bold": lambda: outline(**{**PICKED, "stroke": 38}),
    "x4-small": lambda: outline(**{**PICKED, "stroke": 25, "stem_half": 64,
                                   "brim": -14, "cap_half": 190}),
    "x7-split": lambda: outline(**{**PICKED, "split": True}),
    "x6-junction": lambda: outline(**{**PICKED, "junction": True}),
    "x5-ringed": lambda: outline(**{**PICKED, "ring": True}),
}


def main() -> int:
    for key, _, _ in MARKS:
        (HERE / f"{key}.svg").write_text(BUILDERS[key]())
        print(f"  {key}.svg")
    (HERE / "_meta.json").write_text(json.dumps(MARKS, indent=2))

    # The rebuild must be one path; the original must not be. If that ever
    # stops being true the whole point of this round has quietly gone.
    faithful = (HERE / "x1-faithful.svg").read_text()
    assert len(re.findall(r"<path", faithful)) == 1, "rebuild is not one path"
    assert len(re.findall(r"<path", (HERE / "x0-original.svg").read_text())) == 2
    split = (HERE / "x7-split.svg").read_text()
    assert len(re.findall(r"<path", split)) == 2, "split build shape"
    print(f"\n  {len(MARKS)} marks; rebuild verified as a single path")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
