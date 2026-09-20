"""Risk-weighted objective.

Cross-entropy treats every mistake as equally bad. For this application it
is not: confusing two brittlegills costs a user nothing, and confusing a
death cap for a field mushroom can kill them. `RiskWeightedCrossEntropy`
applies a per-example multiplier derived from the taxonomy's risk matrix,
so gradient magnitude tracks real-world consequence.

This is the single most defensible technical difference between this model
and the consumer apps it competes with, and it is measured directly by the
risk-weighted error rate in evaluate.py.
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from .taxonomy import Taxonomy


def build_risk_matrix(taxonomy: Taxonomy, classes: list[str]) -> np.ndarray:
    """Dense [n_classes, n_classes] matrix of misclassification costs."""
    n = len(classes)
    matrix = np.zeros((n, n), dtype=np.float32)
    for i, true_key in enumerate(classes):
        for j, pred_key in enumerate(classes):
            matrix[i, j] = taxonomy.risk_weight(true_key, pred_key)
    return matrix


class RiskWeightedCrossEntropy(nn.Module):
    """Cross-entropy scaled by the expected risk of the model's own beliefs.

    For each example we compute the risk the current prediction distribution
    carries -- sum_j p_j * cost(true, j) -- and use it to scale that
    example's loss. An example the model is getting dangerously wrong is
    amplified; one it is getting harmlessly wrong is not.

    `max_scale` caps the multiplier. Without it, a single death-cap example
    early in training produces a gradient large enough to destabilise the
    whole run.
    """

    def __init__(
        self,
        risk_matrix: np.ndarray,
        label_smoothing: float = 0.1,
        risk_strength: float = 1.0,
        max_scale: float = 20.0,
    ):
        super().__init__()
        self.register_buffer("risk", torch.from_numpy(risk_matrix))
        self.label_smoothing = label_smoothing
        self.risk_strength = risk_strength
        self.max_scale = max_scale

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        base = F.cross_entropy(
            logits, targets, label_smoothing=self.label_smoothing, reduction="none"
        )
        if self.risk_strength <= 0:
            return base.mean()

        with torch.no_grad():
            probs = logits.softmax(dim=1)
            costs = self.risk[targets]  # [B, C]
            expected_risk = (probs * costs).sum(dim=1)
            # log1p keeps the 1000x deadly weighting influential without
            # letting it dominate the batch outright.
            scale = 1.0 + self.risk_strength * torch.log1p(expected_risk)
            scale = scale.clamp(max=self.max_scale)

        return (base * scale).mean()


class SoftTargetRiskLoss(nn.Module):
    """Mixup/CutMix-compatible variant operating on soft targets."""

    def __init__(self, risk_matrix: np.ndarray, risk_strength: float = 1.0,
                 max_scale: float = 20.0):
        super().__init__()
        self.register_buffer("risk", torch.from_numpy(risk_matrix))
        self.risk_strength = risk_strength
        self.max_scale = max_scale

    def forward(self, logits: torch.Tensor, soft_targets: torch.Tensor) -> torch.Tensor:
        base = torch.sum(-soft_targets * F.log_softmax(logits, dim=1), dim=1)
        if self.risk_strength <= 0:
            return base.mean()
        with torch.no_grad():
            probs = logits.softmax(dim=1)
            # Expected cost under both the mixed target and the prediction.
            costs = soft_targets @ self.risk  # [B, C]
            expected_risk = (probs * costs).sum(dim=1)
            scale = (1.0 + self.risk_strength * torch.log1p(expected_risk)).clamp(
                max=self.max_scale
            )
        return (base * scale).mean()
