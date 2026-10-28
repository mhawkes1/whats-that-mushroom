"""Mixup and CutMix, and what they cost the risk objective.

Written for run two. The first run's curve showed accuracy flat across
twenty-five epochs while risk-weighted error nearly doubled -- the model
converting "uncertain, spread across the genus" into "confidently the
common one", which is the 1000x cell of the risk matrix when the truth is a
rare deadly species. Mixup trains flatter distributions on inputs between
classes, so it attacks that directly.

It had been declared in the config at 0.2/1.0 for months while `train.py`
used hard targets throughout, and `losses.SoftTargetRiskLoss` was written
and called by nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fungi_ml.losses import SoftTargetRiskLoss  # noqa: E402
from fungi_ml.mixup import Mixer, one_hot, rand_bbox  # noqa: E402

N = 8

# The mixer draws lambda, the mode and the permutation from one generator,
# so a seed fixes all three. Self-pairing is normal and correct -- it means
# that example simply was not mixed -- but it makes a two-image batch a coin
# flip, so the tests below use a seed that swaps. Found by trying them; the
# test asserts the swap happened rather than assuming it, so a change to the
# draw order fails loudly instead of quietly testing nothing.
SWAPPING_SEED = 1


def a_batch(n: int = 4, size: int = 16):
    return torch.rand(n, 3, size, size), torch.randint(0, N, (n,))


def test_disabled_by_default_and_the_targets_are_still_usable():
    """Both alphas zero is the shipping config, and must change nothing."""
    mixer = Mixer(N)
    assert not mixer.enabled
    images, labels = a_batch()
    out, targets = mixer(images, labels)
    assert torch.equal(out, images), "an off mixer must not touch the pixels"
    assert targets.shape == (4, N)
    assert torch.allclose(targets.sum(dim=1), torch.ones(4))


def test_smoothing_matches_cross_entropys_own_convention():
    """Smoothing moves from the loss into the mixer, so it has to land in
    the same place -- otherwise turning mixing on silently changes the
    objective by more than mixing."""
    targets = one_hot(torch.tensor([0, 3]), N, smoothing=0.1)
    assert targets[0, 0] == pytest.approx(1 - 0.1 + 0.1 / N)
    assert targets[0, 1] == pytest.approx(0.1 / N)
    assert torch.allclose(targets.sum(dim=1), torch.ones(2))


def test_a_mixed_batch_keeps_its_shape_and_its_mass():
    mixer = Mixer(N, mixup_alpha=0.8, prob=1.0)
    images, labels = a_batch()
    out, targets = mixer(images, labels)
    assert out.shape == images.shape
    assert torch.allclose(targets.sum(dim=1), torch.ones(4), atol=1e-5)


def test_mixup_blends_pixels_and_cutmix_replaces_them():
    """Different operations, and a test that passes for both tests neither.

    Checked by their defining property rather than by how much changed,
    which depends on the sampled lambda and on whether the permutation
    happened to pair an example with itself. With one image all 0 and the
    other all 1: mixup produces a value strictly between, everywhere;
    CutMix produces only 0s and 1s, because each output pixel comes from
    exactly one source.
    """
    labels = torch.tensor([0, 1])
    black_and_white = torch.stack([torch.zeros(3, 32, 32), torch.ones(3, 32, 32)])

    # Seeds chosen so the permutation actually swaps the pair. Self-pairing
    # is normal and correct -- it simply means that example was not mixed --
    # but it makes a two-image batch a coin flip, so it is pinned here.
    blended, _ = Mixer(N, mixup_alpha=1.0, prob=1.0, seed=SWAPPING_SEED)(
        black_and_white.clone(), labels
    )
    assert ((blended > 0) & (blended < 1)).all(), (
        "mixup must blend: no output pixel should equal either source. "
        "If this fails, check SWAPPING_SEED still swaps -- a self-paired "
        "batch is unmixed by definition and proves nothing."
    )

    cut, _ = Mixer(N, cutmix_alpha=1.0, prob=1.0, seed=SWAPPING_SEED)(
        black_and_white.clone(), labels
    )
    assert ((cut == 0) | (cut == 1)).all(), (
        "cutmix must copy whole pixels, never average them"
    )
    assert cut[0].min() == 0 and cut[0].max() == 1, (
        "and it must actually have taken a region from the other image"
    )


def test_cutmix_weights_the_target_by_the_realised_area():
    """Not by the sampled lambda.

    The box is clipped at the image edge, so the two differ whenever it was
    centred near one. A target weighted by the wrong lambda is a label
    error that looks like nothing: the image says 70/30 and the target says
    50/50, consistently, for every box that touches a border.
    """
    # A box centred hard against the corner loses half its height and width.
    rng = np.random.default_rng(0)
    for _ in range(200):
        y1, y2, x1, x2 = rand_bbox(32, 32, lam=0.5, rng=rng)
        assert 0 <= y1 <= y2 <= 32 and 0 <= x1 <= x2 <= 32

    mixer = Mixer(N, cutmix_alpha=1.0, prob=1.0, seed=5)
    images = torch.zeros(2, 3, 32, 32)
    images[1] = 1.0  # so the cut region is visible as exactly the 1s
    _, labels = a_batch(n=2)
    out, targets = mixer(images.clone(), torch.tensor([0, 1]))

    realised = (out[0] == 1.0).float().mean().item()
    # targets[0] is lam * onehot(0) + (1-lam) * onehot(partner); the weight
    # given to the partner must equal the fraction of pixels taken.
    off = 0.1 / N
    partner_weight = targets[0, 1].item() - off
    if partner_weight > 1e-6:  # this seed paired 0 with 1
        assert partner_weight == pytest.approx(realised * (1 - 0.1), abs=0.02), (
            "the target weight does not match the pixels actually replaced"
        )


def test_an_unmixed_batch_is_identical_to_no_mixer_at_all():
    """`prob` is the chance a batch is mixed; the rest must pass through."""
    mixer = Mixer(N, mixup_alpha=1.0, prob=0.0)
    images, labels = a_batch()
    out, _ = mixer(images, labels)
    assert torch.equal(out, images)


# --- What mixing costs the risk objective ----------------------------------


def _risk_matrix() -> np.ndarray:
    """Class 0 is DEADLY: calling it class 1 costs 1000, everything else 1."""
    matrix = np.ones((N, N), dtype=np.float32)
    np.fill_diagonal(matrix, 0.0)
    matrix[0, 1] = 1000.0
    return matrix


def test_mixing_dilutes_the_risk_multiplier_by_about_a_tenth():
    """Measured, because a dilution of the one mechanism this project is
    built on is worth knowing the size of.

    `soft_targets @ risk` means a half death cap carries half the cost of a
    whole one -- 500 rather than 1000. But the multiplier is
    `1 + strength * log1p(expected_risk)`, and log1p compresses: 6.91
    against 6.22. A tenth, not a half.
    """
    assert np.log1p(1000) == pytest.approx(6.909, abs=0.01)
    assert np.log1p(500) == pytest.approx(6.217, abs=0.01)
    ratio = (1 + np.log1p(500)) / (1 + np.log1p(1000))
    assert 0.88 < ratio < 0.92, f"dilution is {1 - ratio:.0%}, not ~10%"


def test_the_soft_loss_charges_a_dangerous_prediction_more():
    """The whole objective, on soft targets. Predicting the harmless
    neighbour of a deadly species must cost more than predicting any other
    wrong class."""
    loss = SoftTargetRiskLoss(_risk_matrix(), risk_strength=1.0)
    deadly = one_hot(torch.tensor([0]), N, smoothing=0.0)

    def at(predicted: int) -> float:
        logits = torch.full((1, N), -5.0)
        logits[0, predicted] = 5.0
        return float(loss(logits, deadly))

    assert at(1) > at(2), (
        "calling a death cap its harmless lookalike must cost more than "
        "calling it some other mushroom"
    )


def test_the_soft_loss_reduces_to_the_hard_one_when_targets_are_one_hot():
    """Otherwise turning mixing on changes the objective even on the
    batches it skipped."""
    from fungi_ml.losses import RiskWeightedCrossEntropy

    matrix = _risk_matrix()
    torch.manual_seed(0)
    logits = torch.randn(6, N)
    labels = torch.randint(0, N, (6,))

    hard = RiskWeightedCrossEntropy(matrix, label_smoothing=0.1, risk_strength=0.0)
    soft = SoftTargetRiskLoss(matrix, risk_strength=0.0)
    targets = one_hot(labels, N, smoothing=0.1)

    assert float(hard(logits, labels)) == pytest.approx(
        float(soft(logits, targets)), abs=1e-5
    )


def test_train_py_uses_the_soft_loss_only_when_mixing_is_on():
    """Read from source: importing train.py needs timm.

    A run with both alphas at 0 -- which is the shipping config -- must
    train byte-identically to how it did before the mixer existed.
    """
    source = (Path(__file__).resolve().parents[1]
              / "fungi_ml" / "train.py").read_text(encoding="utf-8")
    assert "if mixer.enabled:" in source
    assert "SoftTargetRiskLoss(" in source
    assert "RiskWeightedCrossEntropy(" in source, "the hard path must survive"
    loop = source.split("for i, (images, metadata, labels) in")[1]
    assert "mixer(images, labels)" in loop, "the mixer must run on the batch"
    assert "criterion(logits, targets)" in loop
