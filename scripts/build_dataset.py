#!/usr/bin/env python3
"""One-shot dataset build: resolve taxa, download images, prepare splits.

    python scripts/build_dataset.py --target 400 --country GB

Resumable. Re-running skips images already on disk, so an interrupted run
costs only the time already spent.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

from fungi_ml.data.prepare import prepare  # noqa: E402
from fungi_ml.data.sources import (  # noqa: E402
    build_manifest,
    fetch_images,
    load_quotas,
    resolve_label_space,
)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--taxonomy", default=str(ROOT / "data" / "taxonomy.seed.json"))
    ap.add_argument("--target", type=int, default=400, help="Images per species.")
    ap.add_argument("--country", default=None, help="ISO code, e.g. GB. Omit for global.")
    ap.add_argument("--raw-dir", default=str(ROOT / "data" / "raw"))
    ap.add_argument("--image-dir", default=str(ROOT / "data" / "images"))
    ap.add_argument("--out-dir", default=str(ROOT / "data" / "processed"))
    ap.add_argument("--min-images", type=int, default=40)
    ap.add_argument("--min-observations", type=int, default=10)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument(
        "--max-per-observation",
        type=int,
        default=4,
        help="Photographs to take from one fruiting body. The quota is counted "
        "in images but the split is counted in observations.",
    )
    ap.add_argument(
        "--resolve-only",
        action="store_true",
        help="Resolve GBIF taxon keys, write them for review, and stop. "
        "Do this first: it takes a minute and it is where a name silently "
        "becomes the wrong fungus.",
    )
    ap.add_argument(
        "--allow-unresolved-deadly",
        action="store_true",
        help="Continue even if a DEADLY species has no taxon key. The app "
        "cannot warn about a species the model cannot name.",
    )
    args = ap.parse_args()

    raw_dir = Path(args.raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = raw_dir / "manifest.parquet"
    fetched_path = raw_dir / "manifest_fetched.parquet"
    keys_path = ROOT / "data" / "gbif-keys.json"

    if args.resolve_only:
        matches = resolve_label_space(args.taxonomy, cache_path=keys_path)
        refused = [m for m in matches if not m.accepted]
        print()
        print(f"  resolved : {len(matches) - len(refused)} of {len(matches)}")
        print(f"  written  : {keys_path}")
        if refused:
            print()
            print(f"  {len(refused)} refused -- set gbif_key by hand after checking each:")
            for match in refused:
                print(f"    {match.scientific_name:<40} {match.reason}")
        return

    if not manifest_path.exists():
        logging.info("Resolving GBIF taxon keys and building the manifest...")
        quotas = load_quotas(
            args.taxonomy,
            args.target,
            cache_path=keys_path,
            allow_unresolved_deadly=args.allow_unresolved_deadly,
        )
        build_manifest(
            quotas,
            manifest_path,
            country=args.country,
            max_images_per_observation=args.max_per_observation,
        )
    else:
        logging.info("Reusing existing manifest at %s", manifest_path)

    import pandas as pd

    manifest = pd.read_parquet(manifest_path)
    logging.info("Downloading %d images...", len(manifest))
    fetched = fetch_images(manifest, args.image_dir, workers=args.workers)
    fetched.to_parquet(fetched_path, index=False)

    logging.info("Preparing splits...")
    prepared, label_map = prepare(
        fetched_path, args.out_dir, min_images=args.min_images
    )

    observations = prepared.groupby("species_key")["observation_id"].nunique()
    thin = observations[observations < args.min_observations]

    print()
    print(f"  images       : {len(prepared)}")
    print(f"  species      : {len(label_map)}")
    print(f"  observations : {prepared['observation_id'].nunique()}")
    print(f"  output       : {args.out_dir}")
    if len(thin):
        print()
        print(
            f"  {len(thin)} species have fewer than {args.min_observations} observations. "
            "They clear --min-images on photographs of the same few fruiting bodies, "
            "so their validation score says almost nothing:"
        )
        for key, count in thin.sort_values().items():
            print(f"    {key:<40} {count} observations")
    print()
    print("Next: python -m fungi_ml.train --config configs/default.yaml")


if __name__ == "__main__":
    main()
