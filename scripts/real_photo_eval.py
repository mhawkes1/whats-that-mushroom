#!/usr/bin/env python3
"""Run photographs a person actually took through the running app.

    python scripts/try_it.py          # in another window, first
    python scripts/real_photo_eval.py

**Why this exists.** Every number in a model card -- 87.1% top-1, 1.0820
risk-weighted error, 85.0% coverage -- is measured on held-out *iNaturalist*
images. They were never trained on, which makes them a fair test of the
model. They are not a fair test of the **product**, because they share a
distribution with the training set: good light, the mushroom filling the
frame, photographed by someone who went out to photograph mushrooms and
knew which features to show.

A user's photograph is none of those things. It is taken on a phone, often
of something already picked and lying down, half the frame vegetation, the
gills not visible because nobody told them gills matter. The gap between
those two populations is the gap between a benchmark and an experience, and
until this script there was no measurement of it anywhere in the project.

**It measures the app, not the model.** It reads what `/identify` actually
returned -- the verdict, the headline, the hazard line, whether a warning
appeared -- rather than an argmax. A photograph the model gets wrong and the
safety layer refuses on is a different event from one it gets wrong and
names confidently, and only the second is a failure of the product.

**It refuses to run against the stub.** On 2026-10-29 a browser-renamed
`model (2).onnx` left the server serving deterministic fakes, and an hour
went into analysing an identification that a random number generator had
produced. A measurement taken against the stub is not a weak measurement,
it is a fabricated one, so this checks `/health` and stops.

The run is written to `eval/results/<date>.json` in full. A summary can
only be read; a record can be re-interrogated, which is the same argument
that put `predictions.npz` in git.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

# Verdicts in which the app asserts a species. Everything else is some form
# of declining, which is the product working rather than failing.
NAMING_VERDICTS = {"species"}


def _health(base: str) -> dict:
    import requests

    r = requests.get(f"{base}/health", timeout=10)
    r.raise_for_status()
    return r.json()


def _identify(base: str, photo: Path) -> dict:
    import requests

    with photo.open("rb") as fh:
        r = requests.post(
            f"{base}/identify",
            files={"image": (photo.name, fh, "image/jpeg")},
            timeout=120,
        )
    r.raise_for_status()
    return r.json()


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--manifest", default=str(ROOT / "eval" / "real-photos.csv"))
    ap.add_argument("--photos", default=str(ROOT / "eval" / "photos"))
    ap.add_argument("--out", default=None)
    ap.add_argument(
        "--allow-stub",
        action="store_true",
        help="run anyway with no model loaded. Produces fabricated numbers; "
             "exists only so the script itself can be tested.",
    )
    args = ap.parse_args()

    from fungi_ml.taxonomy import Taxonomy, Toxicity

    taxonomy = Taxonomy.load(ROOT / "data" / "taxonomy.seed.json")

    try:
        health = _health(args.api)
    except Exception as exc:  # noqa: BLE001 -- any failure means no API
        print(f"No API at {args.api}: {exc}\n"
              f"Start it first:  python scripts/try_it.py", file=sys.stderr)
        return 2

    if not health.get("model_loaded") and not args.allow_stub:
        print("\n  The API is serving the STUB BACKEND -- deterministic fakes.\n"
              "  Nothing measured against it means anything. Check that\n"
              "  model.onnx is in the run directory and named exactly that;\n"
              "  a browser that downloaded it twice will have called it\n"
              "  'model (2).onnx'.\n", file=sys.stderr)
        return 3

    rows = list(csv.DictReader(Path(args.manifest).open(encoding="utf-8")))
    if not rows:
        print(f"No photographs listed in {args.manifest}.", file=sys.stderr)
        return 2

    results, missing = [], []
    for row in rows:
        photo = Path(args.photos) / row["filename"]
        if not photo.exists():
            missing.append(row["filename"])
            continue

        truth_key = row["species_key"]
        truth = taxonomy.get(truth_key)
        if truth is None:
            print(f"  {row['filename']}: {truth_key!r} is not in the label "
                  f"space -- skipped", file=sys.stderr)
            continue

        body = _identify(args.api, photo)
        candidates = body["candidates"]
        named = body["verdict"] in NAMING_VERDICTS
        top = candidates[0] if candidates else None

        # Where the truth sat, and how much mass it held. Rank matters
        # because the pair rule reads the top five; mass matters because
        # the warning rule reads all of it.
        rank, mass = None, 0.0
        for i, c in enumerate(candidates, start=1):
            if c["species_key"] == truth_key:
                rank, mass = i, c["confidence"]
                break

        # The question the product cares about: was a hazardous mushroom
        # presented as something the app says nothing about? Rule 1 renders
        # nothing for NO_RECORDED_TOXICITY, so that is a bare name.
        shown_hazard = bool(body.get("deadly_in_play")) or (
            top is not None and top["toxicity"] in {"DEADLY", "SERIOUS", "TOXIC"}
        )
        misleading = (
            named
            and truth.toxicity >= Toxicity.TOXIC
            and top is not None
            and top["species_key"] != truth_key
            and not shown_hazard
        )

        results.append({
            "filename": row["filename"],
            "truth": truth_key,
            "truth_toxicity": truth.toxicity.name,
            "visible": row.get("visible", ""),
            "verdict": body["verdict"],
            "headline": body["headline"],
            "named": named,
            "top": top["species_key"] if top else None,
            "top_confidence": round(top["confidence"], 4) if top else None,
            "top_toxicity": top["toxicity"] if top else None,
            "correct": bool(top and top["species_key"] == truth_key),
            "genus_correct": bool(
                top and taxonomy.get(top["species_key"])
                and taxonomy.get(top["species_key"]).genus == truth.genus
            ),
            "truth_rank": rank,
            "truth_mass": round(mass, 4),
            "deadly_in_play": bool(body.get("deadly_in_play")),
            "showed_a_hazard": shown_hazard,
            "misleading": misleading,
            "calibrated": bool(body.get("calibrated")),
        })

    if missing:
        print(f"\n  {len(missing)} listed photograph(s) not found in "
              f"{args.photos}:")
        for m in missing[:10]:
            print(f"      {m}")

    if not results:
        print("\n  Nothing to measure.\n")
        return 2

    n = len(results)
    named = [r for r in results if r["named"]]
    correct_named = [r for r in named if r["correct"]]
    misleading = [r for r in results if r["misleading"]]

    print(f"\n  {n} photograph(s), model {health.get('model_version')}, "
          f"calibrated={health.get('calibrated')}\n")
    print(f"  named a species         {len(named):>3}/{n}  "
          f"({100*len(named)/n:.0f}% coverage)")
    if named:
        print(f"  correct when named      {len(correct_named):>3}/{len(named)}  "
              f"({100*len(correct_named)/len(named):.0f}%)")
    print(f"  genus right (top-1)     "
          f"{sum(r['genus_correct'] for r in results):>3}/{n}")
    print(f"  truth in top 5          "
          f"{sum(1 for r in results if r['truth_rank'] and r['truth_rank'] <= 5):>3}/{n}")

    print()
    if misleading:
        print(f"  *** {len(misleading)} HAZARDOUS SPECIES SHOWN WITH NO "
              f"HAZARD AT ALL ***")
        for r in misleading:
            print(f"      {r['filename']}: {r['truth']} ({r['truth_toxicity']}) "
                  f"shown as {r['top']} at {r['top_confidence']:.2f}")
    else:
        print("  no hazardous species was shown without a hazard line")

    print("\n  per photograph:")
    for r in results:
        mark = "ok " if r["correct"] else ("   " if not r["named"] else "XX ")
        print(f"   {mark}{r['filename']:<38} {r['verdict']:<16} "
              f"-> {str(r['top']):<30} "
              f"{r['top_confidence'] if r['top_confidence'] else 0:.2f}  "
              f"(truth rank {r['truth_rank']})")

    out = Path(args.out) if args.out else (
        ROOT / "eval" / "results" / f"{date.today().isoformat()}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "date": date.today().isoformat(),
        "api_health": health,
        "n": n,
        "coverage": len(named) / n,
        "correct_when_named": len(correct_named) / len(named) if named else None,
        "misleading_count": len(misleading),
        "results": results,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"\n  Wrote {out.relative_to(ROOT)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
