"""Tests for the split and metadata logic.

The observation-leak test is the important one. If it ever fails, every
accuracy number the project reports becomes meaningless.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fungi_ml.data.prepare import (  # noqa: E402
    METADATA_COLUMNS,
    build_label_map,
    encode_metadata,
    filter_classes,
    split_by_observation,
)


def make_manifest(n_species: int = 6, obs_per_species: int = 20, imgs_per_obs: int = 4):
    rows = []
    rng = np.random.default_rng(0)
    for s in range(n_species):
        for o in range(obs_per_species):
            obs_id = f"sp{s}-obs{o}"
            for i in range(imgs_per_obs):
                rows.append(
                    {
                        "species_key": f"species-{s}",
                        "observation_id": obs_id,
                        "image_url": f"http://example.invalid/{obs_id}-{i}.jpg",
                        "path": f"/data/{obs_id}-{i}.jpg",
                        "latitude": float(rng.uniform(50, 59)),
                        "longitude": float(rng.uniform(-6, 2)),
                        "month": int(rng.integers(1, 13)),
                    }
                )
    return pd.DataFrame(rows)


def test_no_observation_leaks_across_splits():
    manifest = make_manifest()
    out = split_by_observation(manifest, val_fraction=0.1, test_fraction=0.1, seed=7)
    per_obs = out.groupby("observation_id")["split"].nunique()
    assert (per_obs == 1).all(), "an observation appeared in more than one split"


def test_every_split_is_populated_and_stratified():
    manifest = make_manifest()
    out = split_by_observation(manifest, val_fraction=0.1, test_fraction=0.1, seed=7)
    assert set(out["split"]) == {"train", "val", "test"}
    # Every species must appear in train and val, or per-class metrics break.
    for split in ("train", "val"):
        present = set(out[out["split"] == split]["species_key"])
        assert present == set(manifest["species_key"]), f"{split} is missing species"


def test_split_is_deterministic_for_a_seed():
    manifest = make_manifest()
    a = split_by_observation(manifest, 0.1, 0.1, seed=42)
    b = split_by_observation(manifest, 0.1, 0.1, seed=42)
    pd.testing.assert_series_equal(a["split"], b["split"])


def test_filter_drops_rare_and_caps_common():
    rows = []
    for i in range(5):  # rare: 5 images, one per observation
        rows.append(
            {"species_key": "rare", "observation_id": f"r{i}", "image_url": f"r{i}", "path": "p"}
        )
    for i in range(300):
        rows.append(
            {"species_key": "common", "observation_id": f"c{i}", "image_url": f"c{i}", "path": "p"}
        )
    frame = pd.DataFrame(rows)

    out = filter_classes(frame, min_images=40, max_images=100, seed=1)
    assert "rare" not in set(out["species_key"]), "under-represented class was not dropped"
    assert (out["species_key"] == "common").sum() <= 100, "cap was not applied"


def test_cap_keeps_observations_whole():
    rows = []
    for o in range(60):
        for i in range(5):  # 5 images per observation, 300 total
            rows.append(
                {
                    "species_key": "common",
                    "observation_id": f"o{o}",
                    "image_url": f"o{o}-{i}",
                    "path": "p",
                }
            )
    frame = pd.DataFrame(rows)
    out = filter_classes(frame, min_images=10, max_images=100, seed=3)
    # Whichever observations survived must have all 5 of their images.
    sizes = out.groupby("observation_id").size()
    assert set(sizes.unique()) == {5}, f"cap sliced an observation: {sizes.unique()}"


def test_metadata_encoding_is_cyclical_and_bounded():
    manifest = make_manifest()
    out = encode_metadata(manifest)
    for col in METADATA_COLUMNS:
        assert col in out.columns
        assert out[col].between(-1.0, 1.0).all(), f"{col} out of range"

    # December and January must be adjacent in the encoding.
    dec = encode_metadata(pd.DataFrame([{"month": 12, "latitude": 51.5, "longitude": -0.1}]))
    jan = encode_metadata(pd.DataFrame([{"month": 1, "latitude": 51.5, "longitude": -0.1}]))
    jul = encode_metadata(pd.DataFrame([{"month": 7, "latitude": 51.5, "longitude": -0.1}]))

    def dist(a, b):
        return float(
            np.hypot(
                a["month_sin"].iloc[0] - b["month_sin"].iloc[0],
                a["month_cos"].iloc[0] - b["month_cos"].iloc[0],
            )
        )

    assert dist(dec, jan) < dist(jan, jul), "month encoding is not cyclical"


def test_missing_metadata_is_flagged_not_imputed():
    frame = pd.DataFrame([{"month": None, "latitude": None, "longitude": None}])
    out = encode_metadata(frame)
    assert out["month_known"].iloc[0] == 0.0
    assert out["geo_known"].iloc[0] == 0.0
    # Unknown values must be neutral zeros, never a silently plausible guess.
    assert out["month_sin"].iloc[0] == 0.0
    assert out["geo_x"].iloc[0] == 0.0


def test_label_map_is_stable_and_contiguous():
    manifest = make_manifest(n_species=4)
    label_map = build_label_map(manifest)
    assert sorted(label_map.values()) == list(range(4))
    assert build_label_map(manifest) == label_map, "label map is not stable across calls"


def test_shuffle_does_not_duplicate_arrow_backed_ids():
    """Regression: pandas returns Arrow-backed strings from .unique(), and
    numpy's shuffle can corrupt those in place. A duplicated observation id
    would silently place the same fruiting body in two splits."""
    manifest = make_manifest(n_species=3, obs_per_species=40)
    manifest["observation_id"] = manifest["observation_id"].astype("string")
    out = split_by_observation(manifest, 0.1, 0.1, seed=11)
    assert out["observation_id"].nunique() == manifest["observation_id"].nunique()
    assert len(out) == len(manifest), "rows were lost or duplicated during splitting"

    capped = filter_classes(manifest, min_images=10, max_images=10_000, seed=11)
    assert capped["observation_id"].nunique() == manifest["observation_id"].nunique()
