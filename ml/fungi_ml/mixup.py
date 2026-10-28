"""Mixup and CutMix, as a single mixer that always emits soft targets.

The first real run showed the problem these are aimed at. Across epochs
4-29 top-1 moved 0.92 of a percentage point while risk-weighted error
nearly doubled, and the mechanism is specific: with accuracy flat, the same
~12% of errors were landing differently. What the extra epochs bought was
the conversion of "uncertain, spread across the genus" into "confidently
the common one" -- and when the truth is a rare deadly species and the
common neighbour is harmless, that is the 1000x cell of the risk matrix.

Mixup trains a network to produce *flatter* distributions on inputs between
classes, which is the opposite transformation. That is why it is the first
thing to reach for here, ahead of raising `risk_strength`: it attacks the
failure directly rather than pricing it higher after the fact.

Three decisions worth stating, because each could reasonably have gone the
other way.

**Everything gets mixed, including the deadly species.** Excluding them is
superficially attractive -- nobody wants a network learning that half a
death cap is a coherent thing -- but it would apply *less* regularisation
to exactly the classes whose overconfidence costs the most, and the
overconfidence is the problem. The risk weighting handles the consequence;
the mixer should not also be making policy.

**Mixing dilutes the risk signal, and measurably little.**
`SoftTargetRiskLoss` computes the cost row as `soft_targets @ risk`, so a
half death cap carries half the cost of a whole one: predicting the
harmless neighbour costs 500 rather than 1000. But the multiplier is
`1 + strength * log1p(expected_risk)`, and log1p compresses hard --
log1p(1000) is 6.91 against log1p(500) at 6.22, so the gradient scale falls
by about a tenth, not by half. A test pins that, because a dilution of the
one mechanism this project is built on is worth knowing the size of.

**The targets are soft even when nothing is mixed.** The loss then has one
path rather than two, and `label_smoothing` is applied here rather than in
`RiskWeightedCrossEntropy`, so a batch that skipped mixing is trained
identically to how it would have been without the mixer at all.
"""

from __future__ import annotations

import numpy as np
import torch


def one_hot(labels: torch.Tensor, num_classes: int, smoothing: float) -> torch.Tensor:
    """Smoothed one-hot targets, matching `F.cross_entropy`'s convention."""
    off = smoothing / num_classes
    targets = torch.full(
        (labels.size(0), num_classes), off, device=labels.device, dtype=torch.float32
    )
    targets.scatter_(1, labels.unsqueeze(1), 1.0 - smoothing + off)
    return targets


def rand_bbox(height: int, width: int, lam: float, rng: np.random.Generator):
    """A CutMix box covering `1 - lam` of the image, clipped to its edges."""
    ratio = np.sqrt(1.0 - lam)
    cut_h, cut_w = int(height * ratio), int(width * ratio)
    cy, cx = rng.integers(0, height), rng.integers(0, width)
    y1, y2 = np.clip(cy - cut_h // 2, 0, height), np.clip(cy + cut_h // 2, 0, height)
    x1, x2 = np.clip(cx - cut_w // 2, 0, width), np.clip(cx + cut_w // 2, 0, width)
    return int(y1), int(y2), int(x1), int(x2)


class Mixer:
    """Applies mixup or CutMix to a batch and returns soft targets.

    `prob` is the chance a given batch is mixed at all; an unmixed batch
    still comes back with smoothed one-hot targets so the caller has one
    code path.
    """

    def __init__(
        self,
        num_classes: int,
        mixup_alpha: float = 0.0,
        cutmix_alpha: float = 0.0,
        prob: float = 0.5,
        label_smoothing: float = 0.1,
        seed: int = 1337,
    ):
        self.num_classes = num_classes
        self.mixup_alpha = mixup_alpha
        self.cutmix_alpha = cutmix_alpha
        self.prob = prob
        self.label_smoothing = label_smoothing
        self.rng = np.random.default_rng(seed)

    @property
    def enabled(self) -> bool:
        return (self.mixup_alpha > 0 or self.cutmix_alpha > 0) and self.prob > 0

    def __call__(
        self, images: torch.Tensor, labels: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        targets = one_hot(labels, self.num_classes, self.label_smoothing)
        if not self.enabled or self.rng.random() >= self.prob:
            return images, targets

        modes = []
        if self.mixup_alpha > 0:
            modes.append("mixup")
        if self.cutmix_alpha > 0:
            modes.append("cutmix")
        mode = modes[self.rng.integers(0, len(modes))]
        alpha = self.mixup_alpha if mode == "mixup" else self.cutmix_alpha
        lam = float(self.rng.beta(alpha, alpha))

        # Mix each example with another drawn from the same batch, which is
        # the standard formulation and keeps the batch size fixed. The
        # permutation comes from this mixer's own generator rather than
        # `torch.randperm`, so `seed` reproduces the WHOLE of the mixing --
        # lambda, mode and pairing. Drawn from the global torch RNG it would
        # have moved with every unrelated change to how many random numbers
        # the rest of the loop consumed, which makes a seeded run
        # unreproducible in the one way nobody checks.
        order = torch.from_numpy(
            self.rng.permutation(images.size(0))
        ).to(images.device)

        if mode == "mixup":
            images = lam * images + (1.0 - lam) * images[order]
        else:
            y1, y2, x1, x2 = rand_bbox(images.size(2), images.size(3), lam, self.rng)
            images = images.clone()
            images[:, :, y1:y2, x1:x2] = images[order][:, :, y1:y2, x1:x2]
            # The REALISED area, not the sampled lambda. The box is clipped
            # at the image edge, so the two differ whenever it was centred
            # near one -- and a target weighted by the wrong lambda is a
            # label error that looks like nothing.
            area = (y2 - y1) * (x2 - x1)
            lam = 1.0 - area / float(images.size(2) * images.size(3))

        targets = lam * targets + (1.0 - lam) * targets[order]
        return images, targets
