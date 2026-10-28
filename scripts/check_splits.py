#!/usr/bin/env python3
"""Check a prepared manifest for the leak that makes accuracy look good.

    python scripts/check_splits.py

Run it after `build_dataset.py` and before paying for a full training run.

`CLAUDE.md` says "splits are on `observation_id`, never on image -- if
accuracy looks too good, check this before believing it." This is that
check, made executable, because the first real run came back at 65% top-1
after a single epoch when the documented expectation was 50-70% after
thirty, and the only honest response to that was to look.

Three leaks, in increasing order of sneakiness:

**An observation in two splits.** The same fruiting body photographed five
times, four shots in train and one in val. The model learns that mushroom
rather than the species. `prepare.py` already asserts against this; the
check is repeated here because a guard you never see run is a guard you are
trusting rather than using.

**The same image URL in two splits.** Slips past the first check entirely,
because two observation ids can carry one photograph -- a record duplicated
upstream, or the same person uploading one image twice.

**The same file on disk in two splits.** The last line of defence: two URLs
can resolve to identical bytes.

It also reports the thin end of the distribution. A species clearing the
40-image floor on six fruiting bodies has a validation score that means
almost nothing, and that is worth knowing before a model card quotes it.

Exit code is 1 if any leak is found, so it can gate a run.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest",
                    default=str(ROOT / "data" / "processed" / "manifest.parquet"),
                    help="manifest.parquet, or the committed splits.csv.gz")
    ap.add_argument("--thin", type=int, default=20,
                    help="flag species with fewer observations than this")
    args = ap.parse_args()

    import pandas as pd

    path = pathlib.Path(args.manifest)
    if not path.exists():
        # The parquet lives on whichever machine prepared the dataset and is
        # gitignored; the split record is committed. Fall back to it so this
        # check still runs from a fresh clone, months later, against the run
        # the numbers were actually reported from.
        fallback = ROOT / "data" / "processed" / "splits.csv.gz"
        if path == pathlib.Path(ap.get_default("manifest")) and fallback.exists():
            print(f"no manifest at {path}\n  reading the split record instead: "
                  f"{fallback}", file=sys.stderr)
            path = fallback
        else:
            print(f"no manifest at {path}", file=sys.stderr)
            return 2
    # Both inputs carry the five columns every check below reads. The parquet
    # also carries forty it does not.
    m = (pd.read_csv(path) if "".join(path.suffixes).endswith((".csv", ".csv.gz"))
         else pd.read_parquet(path))

    print(f"\n  {len(m):,} images   {m.species_key.nunique()} species   "
          f"{m.observation_id.nunique():,} observations")
    print(f"  splits: {dict(m.split.value_counts())}\n")

    def straddles(column: str) -> int:
        counts = m.groupby(column)["split"].nunique()
        return int((counts > 1).sum())

    leaks = [
        ("observations in more than one split", straddles("observation_id")),
        ("image URLs in more than one split", straddles("image_url")),
        ("files in more than one split", straddles("path")),
    ]
    print("  LEAK CHECKS (every one must be zero)")
    print("  " + "-" * 58)
    for label, n in leaks:
        print(f"   {'FAIL' if n else 'pass'}  {label:<44} {n}")

    dupes = int(m.image_url.duplicated().sum())
    print(f"\n  duplicate image URLs anywhere: {dupes}"
          f"{'  (not a leak on its own)' if dupes else ''}")

    obs = m.groupby("species_key").observation_id.nunique().sort_values()
    img = m.groupby("species_key").size()
    print(f"\n  THINNEST SPECIES, by distinct fruiting bodies")
    print("  " + "-" * 58)
    for key in obs.index[:12]:
        print(f"   {key:<36} {obs[key]:>4} obs   {img[key]:>5} images")
    thin = int((obs < args.thin).sum())
    print(f"\n  under {args.thin} observations: {thin}    "
          f"under 10: {int((obs < 10).sum())}")
    if thin:
        print("  Their validation scores say very little. Worth naming in the")
        print("  model card rather than averaging into one headline number.")

    failed = sum(n for _, n in leaks)
    if failed:
        print(f"\n  {failed} leak(s) found. Do not trust an accuracy figure "
              f"from this manifest.\n")
        return 1
    print("\n  No leak found. An accuracy figure from this manifest is "
          "worth believing.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
