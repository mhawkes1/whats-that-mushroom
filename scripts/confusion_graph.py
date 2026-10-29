#!/usr/bin/env python3
"""Build the empirical confusion graph from a run's own predictions.

    python scripts/confusion_graph.py \
        --predictions ml/runs/baseline/predictions.npz \
        --out data/model-confusions.json

**Why this is a second graph and not more edges in the taxonomy.**

`lookalikes` in `data/taxonomy.seed.json` records what people confuse in the
field. It comes from field guides, it is what the interrogation engine asks
about, the companion book prints from it, and a mycologist is going to read
it. It is a claim about mushrooms.

A classifier confuses different things. Checked against run one on
2026-10-28: **seven of its eight dangerous confusions were not registered
pairs**, including its worst -- *Galerina marginata* called *Crepidotus
cesatii* at 0.850. Nobody picks a *Crepidotus* thinking it is a funeral
bell; a network looking at a small brown thing on wood does. So
`straddles_dangerous_pair` was blind on almost every mistake the model
actually made, and the only protection there was the 2% deadly-mass rule.

Writing those edges into `lookalikes` would fix the safety layer by making
the mycology wrong, in the one file that exists to be right about mushrooms.
This writes them somewhere else instead.

**What the file is, and what it is not.**

It is a property of ONE checkpoint, measured on ITS held-out split. It
carries the checkpoint it came from, and the server refuses a graph that
does not match the model it is serving -- a confusion the last model made is
not evidence about this one. It is never shown to a user as a resemblance,
because it is not one.

**Why there is a threshold, and why SILENT confusions ignore it.** A single
misclassification out of nine thousand should not make the app refuse to
name a species forever, so `--min-count` and `--min-mass` set a bar.

But a **silent** confusion -- one where the deadly species held under 2% of
the mass -- is precisely the case `safety.py`'s mass rule does NOT catch,
and this graph is the only thing that can: its pair rule fires on *rank*,
not mass. The first version kept a single confusion only if its deadly mass
cleared `--min-mass`, which meant it kept the ones the mass rule already
handles and dropped the ones nothing handles. Measured on run four: all
three pairs it kept were x1 with high mass, and **both silent confusions
were filtered out**.

So a silent confusion is kept regardless of count. That is rule 3 applied
to this file -- a one-in-nine-thousand chance that a user is shown a
harmless name for a deadly mushroom, with no warning and no hazard line, is
not noise to be thresholded away. The cost of the resulting false refusal is
a wasted foraging trip; the cost of the miss is the reason this project
exists.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--predictions", default=str(
        ROOT / "ml" / "runs" / "baseline" / "predictions.npz"))
    ap.add_argument("--taxonomy", default=str(ROOT / "data" / "taxonomy.seed.json"))
    ap.add_argument("--out", default=str(ROOT / "data" / "model-confusions.json"))
    ap.add_argument("--min-count", type=int, default=2,
                    help="confusions seen at least this often are recorded")
    ap.add_argument("--min-mass", type=float, default=0.10,
                    help="or once, if the deadly species held this much mass")
    args = ap.parse_args()

    import numpy as np
    from fungi_ml.evaluate import DEADLY_MASS_THRESHOLD
    from fungi_ml.taxonomy import Taxonomy, Toxicity

    # `SafetyLayer.straddles_dangerous_pair` inspects `ranked[:5]`. A pair
    # in this file is only consulted if BOTH halves are in that window, so
    # a deadly species at rank 21 is recorded here and never reached. Same
    # duplication as DEADLY_MASS_THRESHOLD and for the same reason: `ml/`
    # and `server/` are separate packages with no import path between
    # them. A test greps safety.py for the real default.
    PAIR_RULE_TOP_N = 5

    path = Path(args.predictions)
    if not path.exists():
        print(f"No predictions at {path}.\n"
              f"Run make_model_card.py with --probs-out first; without it a "
              f"run cannot be re-interrogated at all.", file=sys.stderr)
        return 2

    blob = np.load(path, allow_pickle=False)
    probs = blob["probs"].astype(np.float32)
    labels = blob["labels"]
    classes = [str(c) for c in blob["classes"]]
    checkpoint = str(blob["checkpoint"]) if "checkpoint" in blob else "unknown"
    split = str(blob["split"]) if "split" in blob else "unknown"

    taxonomy = Taxonomy.load(args.taxonomy)
    deadly_cols = [i for i, key in enumerate(classes)
                   if (sp := taxonomy.get(key)) is not None
                   and sp.toxicity is Toxicity.DEADLY]
    deadly_mass = (probs[:, deadly_cols].sum(axis=1) if deadly_cols
                   else np.zeros(len(probs)))
    predictions = probs.argmax(axis=1)

    tally: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"count": 0, "max_deadly_mass": 0.0, "max_confidence": 0.0,
                 "silent": 0, "silent_in_reach": 0, "best_silent_rank": None})
    for row, (true_idx, pred_idx, mass, conf) in enumerate(zip(
        labels, predictions, deadly_mass, probs.max(axis=1)
    )):
        true_key, pred_key = classes[true_idx], classes[pred_idx]
        if true_key == pred_key:
            continue
        true_sp, pred_sp = taxonomy.get(true_key), taxonomy.get(pred_key)
        if true_sp is None or pred_sp is None:
            continue
        if true_sp.toxicity is not Toxicity.DEADLY:
            continue
        if pred_sp.toxicity >= Toxicity.TOXIC:
            continue  # the user is warned about the prediction anyway
        entry = tally[(true_key, pred_key)]
        entry["count"] += 1
        entry["max_deadly_mass"] = max(entry["max_deadly_mass"], float(mass))
        entry["max_confidence"] = max(entry["max_confidence"], float(conf))
        if mass < DEADLY_MASS_THRESHOLD:
            entry["silent"] += 1
            # Where the deadly species actually sat. The pair rule reads
            # the top five, so this decides whether recording the pair
            # protects anybody or only looks like it does.
            rank = int((probs[row] > probs[row, true_idx]).sum()) + 1
            if rank <= PAIR_RULE_TOP_N:
                entry["silent_in_reach"] += 1
            best = entry["best_silent_rank"]
            entry["best_silent_rank"] = rank if best is None else min(best, rank)

    known = taxonomy.dangerous_pairs()
    pairs = []
    for (true_key, pred_key), stats in sorted(
        tally.items(), key=lambda kv: (-kv[1]["count"], -kv[1]["max_confidence"])
    ):
        # `silent` first: a confusion the safety layer's mass rule cannot
        # see is kept however rare, because this graph is its only cover.
        silent = stats["silent"] > 0
        kept = (silent
                or stats["count"] >= args.min_count
                or stats["max_deadly_mass"] >= args.min_mass)
        if not kept:
            continue
        pairs.append({
            "deadly": true_key,
            "mistaken_for": pred_key,
            "count": stats["count"],
            "max_confidence": round(stats["max_confidence"], 4),
            "max_deadly_mass": round(stats["max_deadly_mass"], 4),
            # Whether the taxonomy already knew. A pair that is in both is
            # not new information; the ones that are not are the point.
            "also_a_field_lookalike": tuple(sorted((true_key, pred_key))) in known,
            # How many the safety layer's 2% mass rule would NOT have
            # warned about. These are why the pair belongs here at all.
            "silent": stats["silent"],
            # Of those, how many had the deadly species inside the window
            # the pair rule reads. `silent` minus this is the number this
            # file records and does NOT cover.
            "silent_in_reach": stats["silent_in_reach"],
            "best_silent_rank": stats["best_silent_rank"],
        })

    blob_out = {
        "generated": date.today().isoformat(),
        "checkpoint": checkpoint,
        "split": split,
        "n_samples": int(len(labels)),
        "min_count": args.min_count,
        "min_mass": args.min_mass,
        "note": (
            "Empirical confusions of ONE checkpoint, measured on its own "
            "held-out split. These are not field lookalikes and must never "
            "be shown to a user as resemblances. Regenerate for every model; "
            "the server refuses a graph whose checkpoint does not match."
        ),
        "pairs": pairs,
    }
    Path(args.out).write_text(json.dumps(blob_out, indent=2) + "\n", encoding="utf-8")

    novel = [p for p in pairs if not p["also_a_field_lookalike"]]
    print()
    print(f"  {len(tally)} dangerous confusions, {len(pairs)} above the bar")
    print(f"  {len(novel)} of them are NOT field lookalikes -- the ones the")
    print(f"  taxonomy's own graph could never have caught")
    print()
    # Recording a silent confusion is not the same as covering it, and
    # this summary used to say it was. The pair rule reads the top five;
    # a deadly species below that is written into this file and never
    # looked at. Report the two separately or the file reads as cover it
    # does not provide -- the same shape of error as a spreadsheet that
    # reassures past the warning printed above it.
    n_silent = sum(p["silent"] for p in pairs)
    n_reached = sum(p["silent_in_reach"] for p in pairs)
    if n_silent:
        print(f"  {n_silent} silent confusion(s) recorded -- the mass rule "
              f"cannot see these")
        print(f"  {n_reached} of them are COVERED: the deadly species is "
              f"inside the top {PAIR_RULE_TOP_N},")
        print(f"  which is the window the pair rule reads")
        if n_silent - n_reached:
            print()
            n_missed = n_silent - n_reached
            print(f"  *** {n_missed} silent confusion(s): "
                  f"NOT COVERED BY ANYTHING. ***")
            for p_ in pairs:
                missed = p_["silent"] - p_["silent_in_reach"]
                if missed:
                    print(f"      {p_['deadly']} -> {p_['mistaken_for']}: "
                          f"deadly species best rank "
                          f"{p_['best_silent_rank']}, outside the top "
                          f"{PAIR_RULE_TOP_N}")
    print()
    for p in pairs[:15]:
        mark = "    " if p["also_a_field_lookalike"] else "NEW "
        flag = "  SILENT" if p["silent"] else ""
        print(f"  {mark}{p['deadly']:<28} -> {p['mistaken_for']:<24} "
              f"x{p['count']:<3} conf {p['max_confidence']:.3f}{flag}")
    print()
    print(f"  Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
