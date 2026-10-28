#!/usr/bin/env python3
"""Evaluate a checkpoint on the held-out test split and write the model card.

    python scripts/make_model_card.py \
        --checkpoint ml/runs/baseline/best.pt \
        --manifest data/processed/manifest.parquet \
        --calibration ml/runs/baseline/calibration.json \
        --out ml/runs/baseline/MODEL_CARD.md

`fungi_ml.evaluate` had no command-line entry point: `evaluate()` and
`write_model_card()` were importable functions and nothing called them from
a shell. That meant the one release blocker that produces a *document*
required writing Python by hand -- and the place that would have happened
is a rented GPU box, by the hour, which is the worst place to be composing
anything.

Two things this deliberately does not do.

It does not pick the split. `--split test` is the default and the point:
calibration is fitted on `val`, so reporting on `val` would quote numbers
from data that chose the temperature. `docs/SAFETY.md` asks for the
held-out set and this reads the held-out set.

It does not decide whether the model is good enough. It prints the
dangerous-confusion count and exits non-zero when that count is above the
threshold passed in `--max-dangerous-confusions`, which defaults to 0 --
`docs/SAFETY.md` requires zero on the test set "or a documented, bounded
exception". A non-zero exit is the script declining to let a bad run pass
quietly in a pipeline; the model card is still written either way, because
the evidence for the decision has to exist before the decision.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

log = logging.getLogger("model_card")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--taxonomy", default=str(ROOT / "data" / "taxonomy.seed.json"))
    ap.add_argument("--calibration", help="calibration.json, if it has been fitted")
    ap.add_argument("--split", default="test", help="held-out by default, on purpose")
    ap.add_argument("--out", default="MODEL_CARD.md")
    ap.add_argument("--report-out", help="also write the raw metrics as JSON")
    ap.add_argument(
        "--probs-out",
        help="write the calibrated predictions as .npz. A few megabytes, and "
             "it makes every later question about this run answerable with "
             "no GPU, no dataset and no pod.",
    )
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument(
        "--max-dangerous-confusions",
        type=int,
        default=0,
        help="exit non-zero above this. 0 is what SAFETY.md asks for.",
    )
    ap.add_argument(
        "--max-silent-dangerous-confusions",
        type=int,
        default=0,
        help="exit non-zero above this. A SILENT confusion is one the safety "
             "layer would not have warned about, so it is the subset that "
             "reaches a person. Separate dial, because a documented exception "
             "on the total should not quietly cover these.",
    )
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    import numpy as np
    import torch
    from torch.utils.data import DataLoader

    from fungi_ml.calibrate import collect_logits
    from fungi_ml.data.dataset import FungiDataset, load_manifest
    from fungi_ml.evaluate import evaluate, write_model_card
    from fungi_ml.losses import build_risk_matrix
    from fungi_ml.models.build import load_checkpoint_model
    from fungi_ml.taxonomy import Taxonomy

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt = torch.load(args.checkpoint, map_location=device, weights_only=False)
    classes = ckpt["classes"]
    config = ckpt["config"]

    model = load_checkpoint_model(ckpt).to(device)
    manifest = load_manifest(args.manifest)
    dataset = FungiDataset(manifest, args.split, config["data"]["image_size"])
    if len(dataset) == 0:
        raise SystemExit(f"split {args.split!r} is empty in {args.manifest}")

    loader = DataLoader(
        dataset, batch_size=args.batch_size, shuffle=False, num_workers=4
    )
    log.info("Evaluating %d images from the %r split", len(dataset), args.split)
    logits, labels = collect_logits(model, loader, device)

    calibration = None
    if args.calibration and Path(args.calibration).exists():
        calibration = json.loads(Path(args.calibration).read_text())
        temperature = float(calibration.get("temperature", 1.0))
        log.info("Applying fitted temperature %.4f", temperature)
        probs = (logits / temperature).softmax(dim=1).numpy()
    else:
        # Rule 4: an uncalibrated number is not a confidence, and the card
        # has to say so rather than quietly printing softmax outputs.
        log.warning(
            "No calibration supplied -- the card will report UNCALIBRATED "
            "probabilities. This is a blocker for release, not a detail."
        )
        probs = logits.softmax(dim=1).numpy()

    taxonomy = Taxonomy.load(args.taxonomy)
    risk_matrix = build_risk_matrix(taxonomy, classes)
    report = evaluate(probs, labels.numpy(), classes, taxonomy, risk_matrix)
    report["split"] = args.split
    report["checkpoint"] = str(args.checkpoint)
    report["calibrated"] = calibration is not None

    out = write_model_card(report, calibration, args.out)
    log.info("Wrote %s", out)
    if args.report_out:
        Path(args.report_out).write_text(json.dumps(report, indent=2, default=float))
        log.info("Wrote %s", args.report_out)

    if args.probs_out:
        # The report is a summary and a summary cannot be re-interrogated.
        # On the first paid run the deadly probability mass behind every
        # dangerous confusion was computed here, used, and thrown away: when
        # we later asked what the app would actually have SHOWN for the worst
        # of them, nothing on disk could answer, and the pod was gone. Four
        # megabytes of float16 answers that question and every one like it,
        # for as long as the file exists.
        np.savez_compressed(
            args.probs_out,
            probs=probs.astype(np.float16),
            labels=labels.numpy(),
            classes=np.array(classes),
            split=args.split,
            checkpoint=str(args.checkpoint),
            calibrated=calibration is not None,
            temperature=float((calibration or {}).get("temperature", 1.0)),
        )
        size_mb = Path(args.probs_out).stat().st_size / 1e6
        log.info("Wrote %s (%.1f MB)", args.probs_out, size_mb)

    acc = report["accuracy"]
    n_dangerous = report["dangerous_confusion_count"]
    n_silent = report["silent_dangerous_confusion_count"]
    print()
    print(f"  top-1              {acc['top1']:.1%}")
    print(f"  top-5              {acc['top5']:.1%}")
    print(f"  genus              {report['genus_accuracy']:.1%}")
    print(f"  risk-weighted err  {report['risk_weighted_error']:.4f}   <- rule 6")
    print(f"  deadly recall      {report['deadly_recall']}")
    print(f"  dangerous confus.  {n_dangerous}")
    print(f"    of which SILENT  {n_silent}   <- the ones a user would see "
          f"unwarned")
    print()

    # Two refusals, in the order that matters. The silent count is checked
    # first because it is the one that reaches a person: the rest were caught
    # by the safety layer, which is bad and is not the same thing.
    failures = []
    if n_silent > args.max_silent_dangerous_confusions:
        failures.append(
            f"{n_silent} SILENT dangerous confusions, above the "
            f"{args.max_silent_dangerous_confusions} allowed. In each one the "
            f"deadly species held less than "
            f"{report['deadly_mass_threshold']:.0%} of the mass, so the app "
            f"shows a harmless name with no warning and no hazard line."
        )
    if n_dangerous > args.max_dangerous_confusions:
        failures.append(
            f"{n_dangerous} dangerous confusions on the held-out set, above "
            f"the {args.max_dangerous_confusions} allowed. SAFETY.md wants "
            f"zero, or a documented and bounded exception."
        )
    if failures:
        print("REFUSING:", file=sys.stderr)
        for line in failures:
            print(f"  - {line}", file=sys.stderr)
        print("The card is written -- read it.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
