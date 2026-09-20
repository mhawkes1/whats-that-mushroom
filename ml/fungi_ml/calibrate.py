"""Confidence calibration.

A neural network's raw softmax output is not a probability. Modern networks
are systematically overconfident: a model reporting 0.95 is typically right
far less than 95% of the time. Every consumer mushroom app ships this raw
number as "95% confident", which is the mechanism by which they mislead
users into eating things.

Temperature scaling (Guo et al., 2017) fits a single scalar on held-out data
to correct this. One parameter, no accuracy cost, and it converts the score
into something that can honestly be shown to a user -- and, more
importantly, something a safety threshold can be set against.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

log = logging.getLogger(__name__)


class TemperatureScaler(nn.Module):
    def __init__(self, initial: float = 1.5):
        super().__init__()
        self.log_temperature = nn.Parameter(torch.tensor(float(np.log(initial))))

    @property
    def temperature(self) -> float:
        return float(self.log_temperature.detach().exp())

    def forward(self, logits: torch.Tensor) -> torch.Tensor:
        return logits / self.log_temperature.exp()

    def fit(self, logits: torch.Tensor, labels: torch.Tensor, max_iter: int = 200) -> float:
        """Optimise temperature for NLL on a held-out set.

        Parameterised in log-space so the temperature cannot go negative,
        which LBFGS will otherwise cheerfully try.
        """
        logits = logits.detach()
        labels = labels.detach()
        optimizer = torch.optim.LBFGS([self.log_temperature], lr=0.05, max_iter=max_iter)

        def closure():
            optimizer.zero_grad()
            loss = F.cross_entropy(self(logits), labels)
            loss.backward()
            return loss

        optimizer.step(closure)
        log.info("Fitted temperature: %.4f", self.temperature)
        return self.temperature


def expected_calibration_error(
    probs: np.ndarray, labels: np.ndarray, n_bins: int = 15
) -> float:
    """Mean gap between stated confidence and observed accuracy.

    An ECE of 0.15 means that, averaged over the confidence range, the
    model's stated confidence is wrong by 15 percentage points. Publishing
    this number is something no competitor does.
    """
    confidences = probs.max(axis=1)
    predictions = probs.argmax(axis=1)
    accuracies = (predictions == labels).astype(np.float64)

    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (confidences > lo) & (confidences <= hi)
        if not mask.any():
            continue
        ece += mask.mean() * abs(accuracies[mask].mean() - confidences[mask].mean())
    return float(ece)


def reliability_table(
    probs: np.ndarray, labels: np.ndarray, n_bins: int = 10
) -> list[dict]:
    """Per-bin stated confidence versus observed accuracy, for the model card."""
    confidences = probs.max(axis=1)
    predictions = probs.argmax(axis=1)
    correct = (predictions == labels).astype(np.float64)

    bins = np.linspace(0.0, 1.0, n_bins + 1)
    rows = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (confidences > lo) & (confidences <= hi)
        rows.append(
            {
                "bin": f"{lo:.1f}-{hi:.1f}",
                "count": int(mask.sum()),
                "mean_confidence": float(confidences[mask].mean()) if mask.any() else None,
                "observed_accuracy": float(correct[mask].mean()) if mask.any() else None,
            }
        )
    return rows


def fit_confidence_thresholds(
    probs: np.ndarray,
    labels: np.ndarray,
    target_precision: float = 0.95,
) -> dict[str, float]:
    """Find the confidence floor at which the model is right `target_precision`
    of the time.

    This is what the product actually needs. Below this floor the app does
    not name a species -- it says it cannot tell and asks for more evidence.
    Choosing the threshold empirically, rather than picking a round number
    like 0.8 because it looks reassuring, is the whole point.
    """
    confidences = probs.max(axis=1)
    correct = (probs.argmax(axis=1) == labels)

    chosen = 1.0
    coverage_at_chosen = 0.0
    for threshold in np.arange(0.05, 1.0, 0.01):
        mask = confidences >= threshold
        if mask.sum() < 30:  # too few samples to trust the estimate
            continue
        precision = correct[mask].mean()
        if precision >= target_precision:
            chosen = float(threshold)
            coverage_at_chosen = float(mask.mean())
            break

    return {
        "target_precision": target_precision,
        "confidence_threshold": chosen,
        # Fraction of real queries the app will answer at species level.
        # Low coverage is honest, not broken.
        "coverage": coverage_at_chosen,
    }


@torch.no_grad()
def collect_logits(model, loader, device) -> tuple[torch.Tensor, torch.Tensor]:
    model.eval()
    all_logits, all_labels = [], []
    for images, metadata, labels in loader:
        logits = model(images.to(device), metadata.to(device))
        all_logits.append(logits.float().cpu())
        all_labels.append(labels.cpu())
    return torch.cat(all_logits), torch.cat(all_labels)


def calibrate_checkpoint(
    checkpoint_path: str | Path,
    manifest_path: str | Path,
    out_path: str | Path | None = None,
    split: str = "val",
    batch_size: int = 64,
) -> dict:
    """Fit temperature and thresholds on a held-out split, and write them out.

    Calibration MUST use a split the model never trained on, and ideally not
    the same one used for model selection. Fitting temperature on training
    data produces a temperature near 1.0 and a model that stays overconfident.
    """
    from .data.dataset import FungiDataset, load_manifest
    from .models.build import FungiClassifier
    from torch.utils.data import DataLoader

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)
    classes = ckpt["classes"]
    config = ckpt["config"]

    model = FungiClassifier(
        num_classes=len(classes),
        backbone=config["model"]["backbone"],
        pretrained=False,
    )
    model.load_state_dict(ckpt["model"])
    model.to(device).eval()

    manifest = load_manifest(manifest_path)
    dataset = FungiDataset(manifest, split, config["data"]["image_size"])
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=4)

    logits, labels = collect_logits(model, loader, device)

    uncalibrated = logits.softmax(dim=1).numpy()
    ece_before = expected_calibration_error(uncalibrated, labels.numpy())

    scaler = TemperatureScaler()
    temperature = scaler.fit(logits, labels)

    calibrated = (logits / temperature).softmax(dim=1).numpy()
    ece_after = expected_calibration_error(calibrated, labels.numpy())

    thresholds = fit_confidence_thresholds(calibrated, labels.numpy())

    result = {
        "temperature": temperature,
        "ece_before": ece_before,
        "ece_after": ece_after,
        "reliability": reliability_table(calibrated, labels.numpy()),
        **thresholds,
        "split": split,
        "n_samples": int(len(labels)),
    }

    log.info(
        "Calibration: T=%.3f  ECE %.4f -> %.4f  threshold=%.2f (coverage %.1f%%)",
        temperature, ece_before, ece_after,
        thresholds["confidence_threshold"], thresholds["coverage"] * 100,
    )

    out_path = Path(out_path or Path(checkpoint_path).parent / "calibration.json")
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Calibrate a trained checkpoint.")
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--split", default="val")
    ap.add_argument("--out")
    args = ap.parse_args()
    calibrate_checkpoint(args.checkpoint, args.manifest, args.out, args.split)
