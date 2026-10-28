"""Training entry point.

    python -m fungi_ml.train --config configs/default.yaml

Assumes `fungi_ml.data.prepare` has already produced a manifest. Checkpoints,
the label map and the training config are written together into the run
directory so a checkpoint is always reproducible and always self-describing.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import shutil
import time
from copy import deepcopy
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import yaml
from torch.utils.data import DataLoader

from .data.dataset import FungiDataset, build_balanced_sampler, load_manifest
from .losses import (RiskWeightedCrossEntropy, SoftTargetRiskLoss,
                     build_risk_matrix)
from .mixup import Mixer
from .taxonomy import Taxonomy

log = logging.getLogger(__name__)


class ModelEMA:
    """Exponential moving average of weights.

    Consistently worth ~1 point of top-1 on fine-grained tasks and, more
    usefully here, produces noticeably better-calibrated probabilities.
    """

    def __init__(self, model: nn.Module, decay: float = 0.9998):
        self.module = deepcopy(model).eval()
        self.decay = decay
        for p in self.module.parameters():
            p.requires_grad_(False)

    @torch.no_grad()
    def update(self, model: nn.Module, step: int) -> None:
        # Ramp the decay in so early steps are not dominated by the random init.
        decay = min(self.decay, (1 + step) / (10 + step))
        for ema_p, model_p in zip(self.module.state_dict().values(),
                                  model.state_dict().values()):
            if ema_p.dtype.is_floating_point:
                ema_p.mul_(decay).add_(model_p.detach(), alpha=1 - decay)
            else:
                ema_p.copy_(model_p)


def cosine_schedule(step: int, total: int, warmup: int, min_ratio: float = 0.01) -> float:
    if step < warmup:
        return (step + 1) / max(1, warmup)
    progress = (step - warmup) / max(1, total - warmup)
    return min_ratio + (1 - min_ratio) * 0.5 * (1 + math.cos(math.pi * progress))


@torch.no_grad()
def evaluate_epoch(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    risk_matrix: np.ndarray,
) -> dict[str, float]:
    model.eval()
    correct1 = correct5 = total = 0
    risk_total = 0.0

    risk_t = torch.from_numpy(risk_matrix).to(device)

    for images, metadata, labels in loader:
        images = images.to(device, non_blocking=True)
        metadata = metadata.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)

        logits = model(images, metadata)
        topk = logits.topk(min(5, logits.shape[1]), dim=1).indices

        correct1 += (topk[:, 0] == labels).sum().item()
        correct5 += (topk == labels.unsqueeze(1)).any(dim=1).sum().item()
        risk_total += risk_t[labels, topk[:, 0]].sum().item()
        total += labels.numel()

    return {
        "top1": correct1 / max(1, total),
        "top5": correct5 / max(1, total),
        # The headline safety metric: mean real-world cost of the model's
        # first choice. Driving this down matters more than top-1.
        "risk": risk_total / max(1, total),
    }


# `ml/fungi_ml/train.py` -> `ml/fungi_ml` -> `ml` -> the repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]


def _data_path(value: str | Path) -> Path:
    """Resolve a `data:` path against the repo root, not the shell's cwd.

    The config shipped two paths that wanted *different* working
    directories and could not both be satisfied:

        manifest: data/processed/manifest.parquet   # wants the repo root
        taxonomy: ../data/taxonomy.seed.json        # wants ml/

    `build_dataset.py` writes to `<root>/data/processed` and then prints
    "Next: python -m fungi_ml.train --config configs/default.yaml", which
    only finds its config from `ml/` -- where the manifest path resolves to
    `ml/data/processed/...` and does not exist. So the documented next
    command failed from every directory, and failed *after* a two-hour
    dataset build rather than before it. Found on the first real run,
    2026-10-27.

    Anchoring to the repo root makes every `data:` entry mean the same
    thing wherever it is run from. `output.dir` is deliberately NOT
    anchored: it stays cwd-relative so `runs/baseline` keeps landing in
    `ml/runs/baseline`, which is where the run-book's later steps and every
    documented path expect it.
    """
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def train(config_path: str | Path) -> Path:
    config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    torch.manual_seed(config["train"]["seed"])
    np.random.seed(config["train"]["seed"])

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type == "cpu":
        log.warning("No GPU detected. Training on CPU is not practical at this scale.")

    out_dir = Path(config["output"]["dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(config_path, out_dir / "config.yaml")

    manifest_path = _data_path(config["data"]["manifest"])
    label_map_path = _data_path(config["data"]["label_map"])
    manifest = load_manifest(manifest_path)
    labels_blob = json.loads(label_map_path.read_text(encoding="utf-8"))
    classes: list[str] = labels_blob["classes"]
    num_classes = len(classes)
    shutil.copy(label_map_path, out_dir / "labels.json")

    taxonomy = Taxonomy.load(
        _data_path(config["data"].get("taxonomy", "data/taxonomy.seed.json"))
    )
    risk_matrix = build_risk_matrix(taxonomy, classes)
    np.save(out_dir / "risk_matrix.npy", risk_matrix)

    image_size = config["data"]["image_size"]
    train_ds = FungiDataset(manifest, "train", image_size)
    val_ds = FungiDataset(manifest, "val", image_size)
    log.info("train=%d val=%d classes=%d", len(train_ds), len(val_ds), num_classes)

    sampler = build_balanced_sampler(train_ds) if config["train"]["balanced_sampling"] else None
    train_loader = DataLoader(
        train_ds,
        batch_size=config["train"]["batch_size"],
        sampler=sampler,
        shuffle=sampler is None,
        num_workers=config["data"]["num_workers"],
        pin_memory=device.type == "cuda",
        drop_last=True,
        persistent_workers=config["data"]["num_workers"] > 0,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=config["train"]["batch_size"] * 2,
        shuffle=False,
        num_workers=config["data"]["num_workers"],
        pin_memory=device.type == "cuda",
    )

    # Imported late so the module parses without timm installed.
    from .models.build import build_model

    model = build_model(config, num_classes).to(device)
    ema = ModelEMA(model, config["train"]["ema_decay"]) if config["train"]["ema_decay"] else None

    # Mixup/CutMix if either alpha is set. The soft-target loss is used
    # ONLY when they are, so a run with both at 0 trains byte-identically
    # to how it did before this existed -- the regulariser is a decision
    # someone makes in the config, not a silent change of objective.
    mixer = Mixer(
        num_classes,
        mixup_alpha=config["train"].get("mixup_alpha", 0.0),
        cutmix_alpha=config["train"].get("cutmix_alpha", 0.0),
        prob=config["train"].get("mix_prob", 0.5),
        label_smoothing=config["train"]["label_smoothing"],
        seed=config["train"]["seed"],
    )
    risk_strength = config["train"].get("risk_strength", 1.0)
    if mixer.enabled:
        criterion = SoftTargetRiskLoss(
            risk_matrix, risk_strength=risk_strength
        ).to(device)
        log.info(
            "Mixing ON: mixup_alpha=%.2f cutmix_alpha=%.2f p=%.2f -- "
            "SoftTargetRiskLoss, smoothing applied in the mixer",
            mixer.mixup_alpha, mixer.cutmix_alpha, mixer.prob,
        )
    else:
        criterion = RiskWeightedCrossEntropy(
            risk_matrix,
            label_smoothing=config["train"]["label_smoothing"],
            risk_strength=risk_strength,
        ).to(device)

    optimizer = torch.optim.AdamW(
        model.parameter_groups(config["train"]["lr"], config["train"]["backbone_lr_mult"]),
        weight_decay=config["train"]["weight_decay"],
    )
    scaler = torch.amp.GradScaler("cuda", enabled=config["train"]["amp"] and device.type == "cuda")

    accum = config["train"]["grad_accum_steps"]
    steps_per_epoch = max(1, len(train_loader) // accum)
    total_steps = steps_per_epoch * config["train"]["epochs"]
    warmup_steps = steps_per_epoch * config["train"]["warmup_epochs"]
    base_lrs = [g["lr"] for g in optimizer.param_groups]

    best_risk = float("inf")
    global_step = 0
    history = []

    for epoch in range(config["train"]["epochs"]):
        model.train()
        epoch_loss = 0.0
        seen = 0
        started = time.time()

        for i, (images, metadata, labels) in enumerate(train_loader):
            images = images.to(device, non_blocking=True)
            metadata = metadata.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)

            # Mixing happens on the batch, before the forward pass. When
            # it is off, `targets` is `labels` and the branch is the one
            # that has always run.
            if mixer.enabled:
                images, targets = mixer(images, labels)
            else:
                targets = labels

            with torch.amp.autocast("cuda", enabled=scaler.is_enabled()):
                logits = model(images, metadata)
                loss = criterion(logits, targets) / accum

            scaler.scale(loss).backward()

            if (i + 1) % accum == 0:
                if config["train"]["clip_grad_norm"]:
                    scaler.unscale_(optimizer)
                    nn.utils.clip_grad_norm_(
                        model.parameters(), config["train"]["clip_grad_norm"]
                    )
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)

                factor = cosine_schedule(global_step, total_steps, warmup_steps)
                for group, base in zip(optimizer.param_groups, base_lrs):
                    group["lr"] = base * factor

                if ema:
                    ema.update(model, global_step)
                global_step += 1

            epoch_loss += loss.item() * accum * labels.size(0)
            seen += labels.size(0)

        eval_model = ema.module if ema else model
        metrics = evaluate_epoch(eval_model, val_loader, device, risk_matrix)
        metrics["train_loss"] = epoch_loss / max(1, seen)
        metrics["epoch"] = epoch
        metrics["seconds"] = round(time.time() - started, 1)
        history.append(metrics)

        log.info(
            "epoch %d | loss %.4f | top1 %.4f | top5 %.4f | risk %.3f | %.0fs",
            epoch, metrics["train_loss"], metrics["top1"], metrics["top5"],
            metrics["risk"], metrics["seconds"],
        )

        # Selection is on risk, not accuracy. A checkpoint that is one point
        # more accurate but confuses a death cap more often is a worse model
        # for this application.
        if metrics["risk"] < best_risk:
            best_risk = metrics["risk"]
            torch.save(
                {
                    "model": eval_model.state_dict(),
                    "classes": classes,
                    "config": config,
                    "metrics": metrics,
                    "epoch": epoch,
                },
                out_dir / "best.pt",
            )
            log.info("  new best (risk %.3f) -> %s", best_risk, out_dir / "best.pt")

        (out_dir / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")

    log.info("Done. Best validation risk: %.4f", best_risk)
    return out_dir / "best.pt"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Train the fungi classifier.")
    ap.add_argument("--config", default="configs/default.yaml")
    args = ap.parse_args()
    train(args.config)
