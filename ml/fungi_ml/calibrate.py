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


# A fitted temperature outside this range is not a calibration, it is a
# failed optimisation wearing one. The bounds are deliberately wide: run
# one fitted 0.8177, and anything an order of magnitude either side of 1
# means the NLL surface had no interior optimum on the data it was given.
MIN_TEMPERATURE = 0.05
MAX_TEMPERATURE = 10.0


class DegenerateTemperature(ValueError):
    """The fit ran off to a bound instead of converging.

    Raised rather than returned, because every caller that wrote the value
    anyway would be writing a `calibration.json` that reads as fitted. Rule
    4 is about not showing uncalibrated confidence AS confidence, and a
    temperature of 0 is the purest form of that failure: `logits / 0` is
    infinite, softmax collapses to one-hot, and the app reports **p=1.000**
    -- on anything, including noise.
    """


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

        # A validation set the model gets entirely right carries NO
        # calibration signal. NLL is then monotone decreasing in
        # sharpening -- every reduction in temperature improves it, there
        # is no interior optimum, and the optimiser walks toward zero
        # because that is genuinely where the objective leads. The result
        # is not a temperature the model needs; it is the absence of a
        # question. Checked before the fit, because the fit cannot tell.
        accuracy = float((logits.argmax(dim=1) == labels).float().mean())
        if accuracy >= 1.0:
            raise DegenerateTemperature(
                f"The model is {accuracy:.1%} accurate on this set, so there "
                f"is nothing to calibrate: with no errors, lowering the "
                f"temperature improves NLL without limit and the fit runs "
                f"to zero. Calibrate on a held-out split the model has not "
                f"memorised."
            )

        optimizer.step(closure)
        fitted = self.temperature

        # Log-space stops LBFGS making the temperature negative. It does
        # NOT stop it walking to zero or to infinity, and until 2026-10-28
        # nothing checked: the fit logged whatever it reached and the
        # caller wrote it to calibration.json.
        #
        # Found by the end-to-end rehearsal once mixup was wired up. Soft
        # targets on synthetic noise gave a model with no confidence to
        # scale, the optimiser drove the temperature to 0.0000, and the
        # served prediction came back at **p=1.000** on random pixels.
        # The data was noise but the failure is not: a mixup-trained model
        # is more under-confident than run one's, so run two's fit moves
        # in exactly this direction, and a degenerate result is silent.
        if not np.isfinite(fitted) or not (MIN_TEMPERATURE <= fitted <= MAX_TEMPERATURE):
            raise DegenerateTemperature(
                f"Temperature fit returned {fitted:.6g}, outside "
                f"[{MIN_TEMPERATURE}, {MAX_TEMPERATURE}]. The optimiser ran "
                f"to a bound rather than converging, which means this "
                f"validation set carries no confidence signal to scale -- "
                f"not that the model needs this temperature. Writing it "
                f"would produce a calibration.json that reads as fitted and "
                f"serves p=1.000 on anything."
            )

        log.info("Fitted temperature: %.4f", fitted)
        return fitted


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


def fit_energy_threshold(
    logits: torch.Tensor, false_unknown_rate: float = 0.05
) -> dict:
    """Fit the out-of-distribution energy threshold on in-distribution data.

    The free energy -logsumexp(logits) is low when the network strongly
    activated some class and high when it activated nothing. Softmax throws
    that magnitude away -- it always sums to one -- which is why a top-1
    probability threshold cannot tell a photograph of a slug from a genuine
    but ambiguous mushroom.

    Fitted from known species alone, at the quantile that leaves
    `false_unknown_rate` of them above the line. That fixes the rate at which
    the app disowns something it does know; the alternative, fitting against
    collected negatives, would tune the threshold to whichever negatives
    someone happened to gather, and the inputs that matter are the ones nobody
    thought to collect.

    The direction of error is deliberate. Wrongly saying "I don't recognise
    this" costs an answer. Failing to say it lets the app name a species for a
    mushroom outside its sixty, and the species missing from a label space
    that small are the uncommon ones -- which does not exclude the lethal.
    """
    energies = (-torch.logsumexp(logits.float(), dim=1)).numpy()
    ordered = np.sort(energies)
    threshold = float(np.quantile(ordered, 1.0 - false_unknown_rate))

    return {
        "energy_threshold": threshold,
        "energy_temperature": 1.0,
        "energy_false_unknown_rate": false_unknown_rate,
        # Reported so the model card can state what the check costs on data
        # the model does know, rather than only what it is meant to catch.
        "energy_median_in_distribution": float(np.median(ordered)),
        "energy_flagged_in_distribution": float((energies > threshold).mean()),
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
    from .models.build import load_checkpoint_model
    from torch.utils.data import DataLoader

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)
    classes = ckpt["classes"]
    config = ckpt["config"]

    model = load_checkpoint_model(ckpt).to(device)

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
    # Fitted on the uncalibrated logits on purpose: temperature scaling
    # rescales them, and the energy check wants the magnitude as the network
    # produced it.
    energy = fit_energy_threshold(logits)

    result = {
        "temperature": temperature,
        **energy,
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
    log.info(
        "Out-of-scope: energy threshold %.3f, flagging %.1f%% of known species",
        energy["energy_threshold"], energy["energy_flagged_in_distribution"] * 100,
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
