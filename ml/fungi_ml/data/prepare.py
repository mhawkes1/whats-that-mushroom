"""Turn a raw manifest into a training-ready split.

Two rules here carry most of the weight:

1. Splitting happens on `observation_id`, never on image. A single fruiting
   body is often photographed five times from four angles. Splitting on
   image leaks near-duplicates into validation and inflates accuracy by a
   wide margin -- the kind of number that makes a launch claim and then
   collapses in the field.

2. Rare classes are dropped, not padded. A species with eleven images cannot
   be learned, and a model that emits it confidently is worse than one that
   never emits it at all.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


def filter_classes(
    manifest: pd.DataFrame, min_images: int, max_images: int, seed: int = 1337
) -> pd.DataFrame:
    """Drop under-represented species and cap over-represented ones."""
    counts = manifest.groupby("species_key").size()
    keep = counts[counts >= min_images].index
    dropped = sorted(set(counts.index) - set(keep))
    if dropped:
        log.warning(
            "Dropping %d species below %d images: %s",
            len(dropped),
            min_images,
            ", ".join(dropped[:10]) + (" ..." if len(dropped) > 10 else ""),
        )

    frame = manifest[manifest["species_key"].isin(keep)].copy()

    rng = np.random.default_rng(seed)
    capped = []
    for key, group in frame.groupby("species_key"):
        if len(group) > max_images:
            # Sample whole observations, not whole images, so the cap does
            # not slice a single fruiting body's photo set in half.
            obs = np.asarray(group["observation_id"].unique(), dtype=object)
            rng.shuffle(obs)
            chosen: list[str] = []
            running = 0
            for o in obs:
                n = int((group["observation_id"] == o).sum())
                if running + n > max_images:
                    continue
                chosen.append(o)
                running += n
            group = group[group["observation_id"].isin(chosen)]
        capped.append(group)

    out = pd.concat(capped).reset_index(drop=True)
    log.info("Kept %d images across %d species", len(out), out["species_key"].nunique())
    return out


def split_by_observation(
    manifest: pd.DataFrame,
    val_fraction: float,
    test_fraction: float,
    seed: int = 1337,
) -> pd.DataFrame:
    """Assign each row a `split`, keeping observations intact and stratified."""
    rng = np.random.default_rng(seed)
    assignments: dict[str, str] = {}

    for species_key, group in manifest.groupby("species_key"):
        obs = np.asarray(group["observation_id"].unique(), dtype=object)
        rng.shuffle(obs)
        n = len(obs)
        n_val = max(1, int(round(n * val_fraction))) if n > 2 else 0
        n_test = max(1, int(round(n * test_fraction))) if n > 3 else 0

        for i, o in enumerate(obs):
            if i < n_val:
                assignments[o] = "val"
            elif i < n_val + n_test:
                assignments[o] = "test"
            else:
                assignments[o] = "train"

    out = manifest.copy()
    out["split"] = out["observation_id"].map(assignments)

    leaked = (
        out.groupby("observation_id")["split"].nunique().pipe(lambda s: s[s > 1]).index.tolist()
    )
    if leaked:
        raise AssertionError(f"Observation leak across splits: {leaked[:5]}")

    log.info("Split sizes: %s", out["split"].value_counts().to_dict())
    return out


def build_label_map(manifest: pd.DataFrame) -> dict[str, int]:
    keys = sorted(manifest["species_key"].unique())
    return {k: i for i, k in enumerate(keys)}


def encode_metadata(manifest: pd.DataFrame) -> pd.DataFrame:
    """Derive the auxiliary features the model conditions on.

    Season and coarse location narrow the candidate space more than any
    incremental gain in the vision backbone does -- a point the consumer
    apps miss entirely, because they treat these as display metadata rather
    than model inputs.
    """
    out = manifest.copy()

    month = out["month"].fillna(0).astype(int)
    # Cyclical encoding so December and January sit next to each other.
    radians = 2 * np.pi * (month.clip(1, 12) - 1) / 12
    out["month_sin"] = np.where(month == 0, 0.0, np.sin(radians))
    out["month_cos"] = np.where(month == 0, 0.0, np.cos(radians))
    out["month_known"] = (month > 0).astype(float)

    lat = out["latitude"].astype(float)
    lon = out["longitude"].astype(float)
    known = lat.notna() & lon.notna()
    lat_r = np.radians(lat.fillna(0.0))
    lon_r = np.radians(lon.fillna(0.0))
    # Unit-sphere coordinates avoid the wraparound discontinuity at ±180°.
    out["geo_x"] = np.where(known, np.cos(lat_r) * np.cos(lon_r), 0.0)
    out["geo_y"] = np.where(known, np.cos(lat_r) * np.sin(lon_r), 0.0)
    out["geo_z"] = np.where(known, np.sin(lat_r), 0.0)
    out["geo_known"] = known.astype(float)

    return out


METADATA_COLUMNS = [
    "month_sin",
    "month_cos",
    "month_known",
    "geo_x",
    "geo_y",
    "geo_z",
    "geo_known",
]


def prepare(
    raw_manifest: str | Path,
    out_dir: str | Path,
    min_images: int = 40,
    max_images: int = 1200,
    val_fraction: float = 0.10,
    test_fraction: float = 0.10,
    seed: int = 1337,
) -> tuple[pd.DataFrame, dict[str, int]]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = pd.read_parquet(raw_manifest)
    manifest = manifest[manifest["path"].notna()].reset_index(drop=True)

    manifest = filter_classes(manifest, min_images, max_images, seed=seed)
    manifest = split_by_observation(manifest, val_fraction, test_fraction, seed=seed)
    manifest = encode_metadata(manifest)

    label_map = build_label_map(manifest)
    manifest["label"] = manifest["species_key"].map(label_map)

    manifest.to_parquet(out_dir / "manifest.parquet", index=False)
    (out_dir / "labels.json").write_text(
        json.dumps({"label_map": label_map, "classes": list(label_map)}, indent=2),
        encoding="utf-8",
    )
    log.info("Prepared %d images, %d classes -> %s", len(manifest), len(label_map), out_dir)
    return manifest, label_map


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Prepare the training split.")
    ap.add_argument("--raw-manifest", required=True)
    ap.add_argument("--out-dir", default="data/processed")
    ap.add_argument("--min-images", type=int, default=40)
    ap.add_argument("--max-images", type=int, default=1200)
    ap.add_argument("--val-fraction", type=float, default=0.10)
    ap.add_argument("--test-fraction", type=float, default=0.10)
    ap.add_argument("--seed", type=int, default=1337)
    args = ap.parse_args()

    prepare(
        args.raw_manifest,
        args.out_dir,
        min_images=args.min_images,
        max_images=args.max_images,
        val_fraction=args.val_fraction,
        test_fraction=args.test_fraction,
        seed=args.seed,
    )
