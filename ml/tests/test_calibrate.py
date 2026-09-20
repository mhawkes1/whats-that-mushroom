"""Tests for calibration and the safety-facing evaluation metrics.

These use synthetic logits with known properties, so a regression shows up
as a failing assertion rather than as a subtly wrong number in a model card.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fungi_ml.calibrate import (  # noqa: E402
    TemperatureScaler,
    expected_calibration_error,
    fit_confidence_thresholds,
    reliability_table,
)
from fungi_ml.evaluate import (  # noqa: E402
    coverage_precision_curve,
    dangerous_confusions,
    deadly_recall,
    genus_accuracy,
    risk_weighted_error,
    topk_accuracy,
)
from fungi_ml.losses import RiskWeightedCrossEntropy, build_risk_matrix  # noqa: E402
from fungi_ml.taxonomy import Taxonomy  # noqa: E402

SEED = Path(__file__).resolve().parents[2] / "data" / "taxonomy.seed.json"


def overconfident_logits(n=4000, c=20, accuracy=0.6, sharpness=8.0, seed=0):
    """Logits that are right `accuracy` of the time but always shout.

    This mimics the failure mode of a real network -- and of every consumer
    mushroom app: confidence near 1.0 regardless of whether it is correct.
    """
    rng = np.random.default_rng(seed)
    labels = rng.integers(0, c, size=n)
    logits = rng.normal(0, 1.0, size=(n, c))
    correct = rng.random(n) < accuracy
    for i in range(n):
        target = labels[i] if correct[i] else (labels[i] + 1 + rng.integers(0, c - 1)) % c
        logits[i, target] += sharpness
    return torch.tensor(logits, dtype=torch.float32), torch.tensor(labels)


def test_temperature_scaling_reduces_calibration_error():
    logits, labels = overconfident_logits()
    before = expected_calibration_error(logits.softmax(1).numpy(), labels.numpy())

    scaler = TemperatureScaler()
    temperature = scaler.fit(logits, labels)
    after = expected_calibration_error((logits / temperature).softmax(1).numpy(), labels.numpy())

    assert after < before, f"calibration did not improve: {before:.4f} -> {after:.4f}"
    assert temperature > 1.0, "an overconfident model requires temperature above 1"


def test_temperature_stays_positive():
    logits, labels = overconfident_logits(n=500, c=5)
    scaler = TemperatureScaler()
    t = scaler.fit(logits, labels)
    assert t > 0, "temperature must never go negative -- it would invert the ranking"
    assert np.isfinite(t)


def test_temperature_scaling_preserves_ranking():
    """Calibration must change confidence, never the predicted class."""
    logits, labels = overconfident_logits(n=800, c=12)
    scaler = TemperatureScaler()
    t = scaler.fit(logits, labels)
    assert torch.equal(logits.argmax(1), (logits / t).argmax(1))


def test_ece_is_zero_for_a_perfectly_calibrated_model():
    rng = np.random.default_rng(3)
    n = 20000
    confidence = rng.uniform(0.5, 1.0, size=n)
    correct = rng.random(n) < confidence  # accuracy matches stated confidence
    probs = np.zeros((n, 2))
    probs[:, 0] = confidence
    probs[:, 1] = 1 - confidence
    labels = np.where(correct, 0, 1)
    assert expected_calibration_error(probs, labels) < 0.02


def test_threshold_search_achieves_requested_precision():
    logits, labels = overconfident_logits(n=6000, c=15, accuracy=0.55)
    scaler = TemperatureScaler()
    t = scaler.fit(logits, labels)
    probs = (logits / t).softmax(1).numpy()

    result = fit_confidence_thresholds(probs, labels.numpy(), target_precision=0.90)
    mask = probs.max(1) >= result["confidence_threshold"]
    if mask.sum() >= 30:
        assert probs.argmax(1)[mask].__eq__(labels.numpy()[mask]).mean() >= 0.88
    assert 0.0 <= result["coverage"] <= 1.0


def test_reliability_table_bins_cover_all_samples():
    logits, labels = overconfident_logits(n=1000, c=8)
    rows = reliability_table(logits.softmax(1).numpy(), labels.numpy(), n_bins=10)
    assert sum(r["count"] for r in rows) == 1000


def test_coverage_decreases_as_threshold_rises():
    logits, labels = overconfident_logits(n=2000, c=10)
    curve = coverage_precision_curve(logits.softmax(1).numpy(), labels.numpy())
    coverages = [r["coverage"] for r in curve]
    assert coverages == sorted(coverages, reverse=True)


# --- safety metrics -------------------------------------------------------


@pytest.fixture(scope="module")
def taxonomy():
    return Taxonomy.load(SEED)


def test_dangerous_confusion_detected_in_the_harmful_direction(taxonomy):
    classes = ["amanita-phalloides", "agaricus-campestris"]
    # Truth is the death cap; the model says field mushroom, confidently.
    probs = np.array([[0.05, 0.95]])
    labels = np.array([0])

    rows = dangerous_confusions(probs, labels, classes, taxonomy)
    assert len(rows) == 1
    assert rows[0]["true_species"] == "amanita-phalloides"
    assert rows[0]["predicted_as"] == "agaricus-campestris"


def test_over_caution_is_not_counted_as_a_dangerous_confusion(taxonomy):
    classes = ["amanita-phalloides", "agaricus-campestris"]
    # Truth is the field mushroom; the model cries death cap. Wrong, but safe.
    probs = np.array([[0.95, 0.05]])
    labels = np.array([1])
    assert dangerous_confusions(probs, labels, classes, taxonomy) == []


def test_risk_weighted_error_punishes_the_fatal_direction(taxonomy):
    classes = ["amanita-phalloides", "agaricus-campestris"]
    matrix = build_risk_matrix(taxonomy, classes)

    fatal = risk_weighted_error(np.array([[0.05, 0.95]]), np.array([0]), matrix)
    cautious = risk_weighted_error(np.array([[0.95, 0.05]]), np.array([1]), matrix)

    assert fatal > cautious * 100


def test_genus_accuracy_exceeds_species_accuracy(taxonomy):
    classes = ["amanita-phalloides", "amanita-virosa", "agaricus-campestris"]
    # Every prediction confuses the two Amanitas: species wrong, genus right.
    probs = np.array([[0.1, 0.9, 0.0], [0.9, 0.1, 0.0]])
    labels = np.array([0, 1])

    assert topk_accuracy(probs, labels, 1) == 0.0
    assert genus_accuracy(probs, labels, classes, taxonomy) == 1.0


def test_deadly_recall_reports_group_level(taxonomy):
    classes = ["amanita-phalloides", "amanita-virosa", "agaricus-campestris"]
    probs = np.array([[0.1, 0.9, 0.0]])  # death cap called destroying angel
    labels = np.array([0])

    recall = deadly_recall(probs, labels, classes, taxonomy)
    assert recall["amanita-phalloides"] == 0.0, "species-level recall should be zero"
    assert recall["_group_level_recall"] == 1.0, "genus-level recall should be one"


def test_risk_weighted_loss_exceeds_plain_cross_entropy_on_fatal_errors(taxonomy):
    classes = ["amanita-phalloides", "agaricus-campestris"]
    matrix = build_risk_matrix(taxonomy, classes)
    criterion = RiskWeightedCrossEntropy(matrix, label_smoothing=0.0)

    # Identical logit magnitude, opposite direction of error.
    fatal_logits = torch.tensor([[-3.0, 3.0]])   # says edible
    fatal_target = torch.tensor([0])             # truly the death cap

    safe_logits = torch.tensor([[3.0, -3.0]])    # says death cap
    safe_target = torch.tensor([1])              # truly edible

    fatal_loss = criterion(fatal_logits, fatal_target)
    safe_loss = criterion(safe_logits, safe_target)

    assert fatal_loss > safe_loss * 2, (
        f"fatal error must dominate the gradient: {fatal_loss:.3f} vs {safe_loss:.3f}"
    )


def test_risk_loss_scale_is_capped(taxonomy):
    """Without a cap, one death-cap example destabilises the whole batch."""
    classes = ["amanita-phalloides", "agaricus-campestris"]
    matrix = build_risk_matrix(taxonomy, classes)
    criterion = RiskWeightedCrossEntropy(matrix, label_smoothing=0.0, max_scale=20.0)

    logits = torch.tensor([[-20.0, 20.0]])
    loss = criterion(logits, torch.tensor([0]))
    plain = torch.nn.functional.cross_entropy(logits, torch.tensor([0]))
    assert loss <= plain * 20.0 + 1e-3
