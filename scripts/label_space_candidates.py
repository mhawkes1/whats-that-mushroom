#!/usr/bin/env python3
"""What it would actually cost to add the species the label space is missing.

    python scripts/label_space_candidates.py --top 250

`scripts/frdbi_gap.py` says *which* common British macrofungi are not in the
label space. It cannot say whether any of them could be learned, and that is
the question that decides the work: a label with no photographs behind it is
not a smaller dataset, it is a class the model will guess at.

The *Lepiota* lesson, 2026-10-28, is the whole argument for this script.
*L. brunneoincarnata* came back at 47% recall and the obvious reading was a
quota to raise. Measured, iNaturalist held **74** occurrences with images for
it -- the entire supply, against a target of 400. Raising the target would
have done nothing and the measurement took a minute.

So for every missing species this resolves the name against GBIF, through
the same `judge_match` the dataset builder uses, and counts the photographs
two ways: inside iNaturalist, whose export is research-grade by publication
policy, and across every dataset. The gap between those two columns is
exactly the `image_source` decision in the taxonomy.

Nothing here writes to the taxonomy. It produces a sheet for a person to
decide from, and the decisions it is meant to make easy are:

  * resolved as SPECIES, hundreds of iNat images  -> ordinary addition
  * zero iNat images, thousands elsewhere         -> iNat carries it as a
                                                     complex; needs a named
                                                     second source, not `any`
  * a few dozen images anywhere                   -> a weak label whichever
                                                     way it is sourced
  * refused by judge_match                        -> a key somebody has to
                                                     check and pin by hand,
                                                     the *Helvella crispa*
                                                     case
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "server"))

import requests  # noqa: E402

from app.taxonomy_service import TaxonomyService  # noqa: E402
from fungi_ml.data.sources import (  # noqa: E402
    GBIF_API,
    INATURALIST_DATASET_KEY,
    judge_match,
)

OUT = ROOT / "docs" / "label-space-candidates.csv"

#: Below this, a label is thin enough that its validation score says very
#: little -- the same reasoning as `--min-images` in the dataset builder,
#: which defaults to 40 and which several of these would not clear.
THIN = 150


def _gap_module():
    spec = importlib.util.spec_from_file_location(
        "frdbi_gap", ROOT / "scripts" / "frdbi_gap.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _missing(top: int) -> list[tuple[str, int]]:
    gap = _gap_module()
    known = {
        s.scientific_name
        for s in TaxonomyService.load(ROOT / "data" / "taxonomy.seed.json")
        .species.values()
    }
    genera = gap.load_genera()
    fungi = [
        (name, count)
        for name, count in gap.load_records()
        if genera.get(name.split()[0]) == "fungus"
    ]
    return [
        (name, count)
        for name, count in fungi[:top]
        if name not in known and gap.SYNONYMS.get(name, "") not in known
    ]


def _count(session, key: int, dataset: str | None) -> int:
    params = {
        "taxonKey": key, "mediaType": "StillImage", "hasCoordinate": "true",
        "occurrenceStatus": "PRESENT", "limit": 0,
    }
    if dataset:
        params["datasetKey"] = dataset
    resp = session.get(f"{GBIF_API}/occurrence/search", params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()["count"]


def verdict(match, inat: int | None, anywhere: int | None) -> str:
    if match is None or not match.accepted:
        return "needs a key by hand"
    if anywhere is not None and anywhere < THIN:
        return "thin everywhere"
    if inat == 0:
        return "none on iNaturalist -- needs a named second source"
    if inat is not None and inat < THIN:
        return "thin on iNaturalist"
    return "ordinary addition"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top", type=int, default=250)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    gap = _gap_module()
    known = {
        s.scientific_name: s
        for s in TaxonomyService.load(ROOT / "data" / "taxonomy.seed.json")
        .species.values()
    }
    missing = _missing(args.top)
    session = requests.Session()
    session.headers["User-Agent"] = "whats-that-mushroom/0.1 (label space review)"

    rows = []
    for name, records in missing:
        payload = session.get(
            f"{GBIF_API}/species/match",
            params={"name": name, "kingdom": "Fungi", "strict": "true"},
            timeout=60,
        ).json()
        match = judge_match(name, payload)
        inat = anywhere = None
        if match.accepted:
            inat = _count(session, match.usage_key, INATURALIST_DATASET_KEY)
            anywhere = _count(session, match.usage_key, None)
        genus = name.split()[0]
        dangerous = sorted(
            s.scientific_name for s in known.values()
            if s.genus == genus and s.toxicity.name in ("DEADLY", "SERIOUS")
        )
        rows.append({
            "scientific_name": name,
            "frdbi_records": records,
            "gbif_key": match.usage_key if match.accepted else "",
            "gbif_rank": payload.get("rank") or "",
            "gbif_status": payload.get("status") or "",
            "resolution": "accepted" if match.accepted else match.reason,
            "inaturalist_images": "" if inat is None else inat,
            "images_any_source": "" if anywhere is None else anywhere,
            "dangerous_in_genus": "; ".join(dangerous),
            "possible_renaming_of": gap.possible_renaming(name, known) or "",
            "verdict": verdict(match, inat, anywhere),
        })
        time.sleep(0.1)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    tally: dict[str, int] = {}
    for row in rows:
        tally[row["verdict"]] = tally.get(row["verdict"], 0) + 1
    print(f"\n  {len(rows)} species missing from FRDBI's top {args.top}\n")
    for name, count in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"    {count:>3}  {name}")
    flagged = [r for r in rows if r["possible_renaming_of"]]
    if flagged:
        print(f"\n  {len(flagged)} share an epithet with a species already in "
              f"the label space.")
        print("  Check each before adding it -- a renaming added as a new "
              "species puts the\n  same fungus in twice and merges its "
              "photographs under both labels.")
        for row in flagged:
            print(f"      {row['scientific_name']}  <->  "
                  f"{row['possible_renaming_of']}")
    print(f"\n  Wrote {out.relative_to(ROOT)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
