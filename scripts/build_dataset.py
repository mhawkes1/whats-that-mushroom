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
from fungi_ml.data.sources import build_manifest, fetch_images, load_quotas  # noqa: E402


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
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()

    raw_dir = Path(args.raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = raw_dir / "manifest.parquet"
    fetched_path = raw_dir / "manifest_fetched.parquet"

    if not manifest_path.exists():
        logging.info("Resolving GBIF taxon keys and building the manifest...")
        quotas = load_quotas(args.taxonomy, args.target)
        build_manifest(quotas, manifest_path, country=args.country)
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

    print()
    print(f"  images  : {len(prepared)}")
    print(f"  species : {len(label_map)}")
    print(f"  output  : {args.out_dir}")
    print()
    print("Next: python -m fungi_ml.train --config configs/default.yaml")


if __name__ == "__main__":
    main()
