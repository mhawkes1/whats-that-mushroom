#!/usr/bin/env python3
"""End-to-end pipeline rehearsal on synthetic data, on CPU, in about a minute.

    python scripts/smoke_e2e.py

Unit tests cover each stage in isolation. They do not cover the seams between
them, and the seams are where this pipeline will actually break: a tensor
shape that only bites at export time, a config key the trainer writes and the
calibrator reads under a different name, a class order that silently permutes
between the checkpoint and the served labels.

Finding those on a rented GPU costs money and a rebuild of the dataset.
Finding them here costs a minute. So this walks the whole chain --

    synthesise -> prepare -> train -> calibrate -> export -> serve

-- with a tiny backbone, tiny images and random data, and asserts only that
each stage hands the next one something it can use. It deliberately makes no
claim about accuracy: the data is noise, and a model trained on noise should
not be accurate. What it proves is that the pipeline runs.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "server"))

log = logging.getLogger("smoke")

# Six species chosen to include both halves of the deadliest confusion in the
# taxonomy, so the risk matrix built during training is not all ones.
SPECIES = [
    ("amanita-phalloides", "Amanita phalloides"),
    ("agaricus-campestris", "Agaricus campestris"),
    ("galerina-marginata", "Galerina marginata"),
    ("kuehneromyces-mutabilis", "Kuehneromyces mutabilis"),
    ("cantharellus-cibarius", "Cantharellus cibarius"),
    ("coprinopsis-atramentaria", "Coprinopsis atramentaria"),
]


def synthesise(work: Path, observations: int, per_observation: int, size: int) -> Path:
    """Write random images and a manifest shaped exactly like the GBIF one.

    Each species gets a distinct base hue so the run is not completely
    hopeless, but the signal is weak on purpose -- a smoke test that only
    passes when the model learns is a smoke test that fails for the wrong
    reasons.
    """
    rng = np.random.default_rng(1337)
    image_root = work / "images"
    rows: list[dict] = []

    for index, (key, scientific_name) in enumerate(SPECIES):
        hue = np.array([(index * 37) % 256, (index * 91) % 256, (index * 53) % 256])
        (image_root / key).mkdir(parents=True, exist_ok=True)

        for obs in range(observations):
            observation_id = f"{key}-obs{obs:03d}"
            for shot in range(per_observation):
                pixels = np.clip(
                    hue + rng.normal(0, 60, size=(size, size, 3)), 0, 255
                ).astype(np.uint8)
                path = image_root / key / f"{observation_id}-{shot}.jpg"
                Image.fromarray(pixels).save(path, "JPEG", quality=85)

                rows.append(
                    {
                        "species_key": key,
                        "scientific_name": scientific_name,
                        "gbif_key": 1000 + index,
                        "observation_id": observation_id,
                        "image_url": f"https://example.invalid/{observation_id}-{shot}.jpg",
                        "licence": "CC_BY_4_0",
                        "rights_holder": "synthetic",
                        "latitude": float(rng.uniform(50, 58)),
                        "longitude": float(rng.uniform(-5, 1)),
                        "month": int(rng.integers(1, 13)),
                        "year": 2024,
                        "country_code": "GB",
                        "substrate": None,
                        "identification_verified": "Research Grade",
                        "path": str(path),
                    }
                )

    frame = pd.DataFrame(rows)
    raw_path = work / "raw_manifest.parquet"
    frame.to_parquet(raw_path, index=False)
    log.info("synthesised %d images across %d species", len(frame), len(SPECIES))
    return raw_path


def write_config(work: Path, processed: Path, image_size: int, epochs: int) -> Path:
    """A miniature of configs/default.yaml.

    Same keys, same structure -- a smoke config that drifted from the real one
    would stop testing the thing it is meant to test.
    """
    config = {
        "data": {
            "root": str(processed),
            "manifest": str(processed / "manifest.parquet"),
            "label_map": str(processed / "labels.json"),
            "taxonomy": str(ROOT / "data" / "taxonomy.seed.json"),
            "image_size": image_size,
            "min_images_per_class": 20,
            "max_images_per_class": 1200,
            "val_fraction": 0.25,
            "test_fraction": 0.25,
            "split_on": "observation_id",
            "num_workers": 0,
        },
        "model": {
            # Small, and pretrained=False so the run needs no network.
            "backbone": "resnet18",
            "pretrained": False,
            "drop_rate": 0.1,
            "drop_path_rate": 0.0,
        },
        "train": {
            "epochs": epochs,
            "batch_size": 8,
            "grad_accum_steps": 1,
            "lr": 3.0e-4,
            "backbone_lr_mult": 0.1,
            "weight_decay": 0.05,
            "warmup_epochs": 1,
            "label_smoothing": 0.1,
            "mixup_alpha": 0.0,
            "cutmix_alpha": 0.0,
            "amp": False,
            "ema_decay": 0.9,
            "clip_grad_norm": 1.0,
            "balanced_sampling": True,
            "seed": 1337,
        },
        "eval": {
            "topk": [1, 3, 5],
            "report_genus_accuracy": True,
            "report_dangerous_confusions": True,
        },
        "output": {"dir": str(work / "run"), "save_top_k": 1, "tensorboard": False},
    }
    path = work / "smoke.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return path


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--work-dir", default=None, help="Defaults to a temp dir.")
    ap.add_argument("--keep", action="store_true", help="Keep the work dir.")
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--observations", type=int, default=12)
    ap.add_argument("--per-observation", type=int, default=4)
    ap.add_argument("--image-size", type=int, default=64)
    args = ap.parse_args()

    work = Path(args.work_dir) if args.work_dir else Path(tempfile.mkdtemp(prefix="wtm-smoke-"))
    work.mkdir(parents=True, exist_ok=True)
    log.info("work dir: %s", work)

    try:
        from fungi_ml.calibrate import calibrate_checkpoint
        from fungi_ml.data.prepare import prepare
        from fungi_ml.export import export_onnx
        from fungi_ml.train import train

        # 1. Synthesise a raw manifest in the GBIF shape.
        raw_manifest = synthesise(
            work, args.observations, args.per_observation, args.image_size * 2
        )

        # 2. Prepare: filter, split on observation, encode metadata.
        processed = work / "processed"
        prepared, label_map = prepare(
            raw_manifest,
            processed,
            min_images=20,
            val_fraction=0.25,
            test_fraction=0.25,
        )
        splits = prepared["split"].value_counts().to_dict()
        log.info("prepared %d images, %d classes, splits=%s",
                 len(prepared), len(label_map), splits)
        assert set(splits) == {"train", "val", "test"}, f"missing splits: {splits}"

        # The guarantee the whole evaluation rests on.
        leaked = prepared.groupby("observation_id")["split"].nunique()
        assert (leaked == 1).all(), "observation leaked across splits"

        # 3. Train.
        config_path = write_config(work, processed, args.image_size, args.epochs)
        checkpoint = train(config_path)
        assert checkpoint.exists(), "training produced no checkpoint"

        import torch

        blob = torch.load(checkpoint, map_location="cpu", weights_only=False)
        assert blob["classes"] == list(label_map), "checkpoint class order drifted"
        log.info("checkpoint ok: epoch %d, val risk %.3f",
                 blob["epoch"], blob["metrics"]["risk"])

        # 4. Calibrate on the held-out split.
        calibration = calibrate_checkpoint(
            checkpoint, processed / "manifest.parquet", split="test"
        )
        assert calibration["temperature"] > 0, "non-positive temperature"
        log.info("calibration ok: T=%.3f, threshold=%.2f, coverage=%.1f%%",
                 calibration["temperature"],
                 calibration["confidence_threshold"],
                 calibration["coverage"] * 100)

        # 5. Export to ONNX, with the numerical verification enabled.
        onnx_path = export_onnx(checkpoint, verify=True)
        assert onnx_path.exists(), "export produced no file"

        # 6. Serve it: the exported artefacts must load in the server's own
        #    classifier and produce a ranked, normalised distribution.
        from app.inference import Classifier

        classifier = Classifier.load(
            onnx_path,
            onnx_path.with_name("labels.json"),
            Path(checkpoint).parent / "calibration.json",
            image_size=args.image_size,
        )
        probe = Image.fromarray(
            np.random.default_rng(0).integers(0, 255, (256, 256, 3), dtype=np.uint8)
        )
        prediction = classifier.predict(probe, month=10, latitude=51.5, longitude=-0.1)
        ranked = prediction.ranked

        assert len(ranked) == len(label_map), "served class count mismatch"
        # The out-of-scope check needs the logit magnitude, which softmax
        # discards, so the served prediction has to carry it.
        import math as _math

        assert _math.isfinite(prediction.energy), "no usable free energy served"
        assert abs(sum(p for _, p in ranked) - 1.0) < 1e-4, "probabilities do not sum to 1"
        assert all(
            ranked[i][1] >= ranked[i + 1][1] for i in range(len(ranked) - 1)
        ), "predictions are not ranked"
        log.info("served ok: top prediction %s p=%.3f", ranked[0][0], ranked[0][1])

        print()
        print("  PIPELINE OK")
        print(f"  images     : {len(prepared)}")
        print(f"  classes    : {len(label_map)}")
        print(f"  temperature: {calibration['temperature']:.3f}")
        print(f"  onnx       : {onnx_path.name}")
        print()
        print("  The chain runs. Accuracy is meaningless here -- the data is noise.")
        print()
        return 0

    finally:
        if args.keep or args.work_dir:
            log.info("work dir kept at %s", work)
        else:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
