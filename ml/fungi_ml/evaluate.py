"""Evaluation, reported the way this application actually needs.

Top-1 accuracy is the headline number every competitor quotes and it is the
least informative thing here. This module reports, in rough order of
importance:

  dangerous confusions  -- every instance where a deadly species was called
                           something a user might eat, named individually
  risk-weighted error   -- mean real-world cost of the model's first choice
  genus accuracy        -- usually far higher than species accuracy, and
                           much more honest about what the model knows
  calibration           -- is the stated confidence trustworthy
  coverage vs precision -- what fraction of queries can be answered at a
                           given reliability

A model card generated from this is published with each release.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path

import numpy as np

from .taxonomy import Taxonomy, Toxicity

log = logging.getLogger(__name__)


def topk_accuracy(probs: np.ndarray, labels: np.ndarray, k: int) -> float:
    if probs.shape[1] < k:
        k = probs.shape[1]
    topk = np.argpartition(-probs, kth=k - 1, axis=1)[:, :k]
    return float((topk == labels[:, None]).any(axis=1).mean())


def genus_accuracy(
    probs: np.ndarray, labels: np.ndarray, classes: list[str], taxonomy: Taxonomy
) -> float:
    genera = np.array([taxonomy.genus_of(c) for c in classes])
    predicted = genera[probs.argmax(axis=1)]
    actual = genera[labels]
    return float((predicted == actual).mean())


def risk_weighted_error(
    probs: np.ndarray, labels: np.ndarray, risk_matrix: np.ndarray
) -> float:
    return float(risk_matrix[labels, probs.argmax(axis=1)].mean())


# `server/app/safety.py` warns whenever the deadly species hold at least
# this much probability mass, wherever they sit in the ranking. It is
# duplicated here rather than imported because `ml/` and `server/` are
# separate packages, and `ml/tests/test_evaluate.py` asserts the two stay
# equal by reading safety.py's source.
DEADLY_MASS_THRESHOLD = 0.01


def dangerous_confusions(
    probs: np.ndarray,
    labels: np.ndarray,
    classes: list[str],
    taxonomy: Taxonomy,
    deadly_mass_threshold: float = DEADLY_MASS_THRESHOLD,
) -> list[dict]:
    """Every case where a deadly species was predicted as something safer.

    This is the number that decides whether the model ships. A single
    instance here is worth more scrutiny than a percentage point of top-1.

    **It also records how much mass stayed on the deadly species, which is
    what decides whether a user ever hears about it.** The count alone
    measures the *model*; the app is model plus safety layer, and that layer
    raises the lethal warning whenever the deadly species hold
    `deadly_mass_threshold` between them -- at any rank, because
    `deadly_probability_mass` sums the whole distribution rather than the
    top of it.

    So a confusion splits two ways, and they are not remotely equivalent:

    **Warned.** The argmax was a harmless species, but the deadly mass
    cleared the threshold, so the user got the full "species that can kill"
    banner anyway. Bad, worth fixing, not dangerous.

    **Silent.** The deadly mass was below the threshold, so the app named a
    harmless species and -- since rule 1 renders nothing at all for
    `NO_RECORDED_TOXICITY` -- showed no hazard line either. That is the
    `dangerous_miss` the whole project exists to prevent, and until
    2026-10-28 nothing counted it separately.

    Found while asking what the app would do with the first real run's worst
    confusion: *Galerina marginata* called *Crepidotus cesatii* at 0.850.
    The card could not answer, because it never recorded the one number that
    decides.
    """
    predictions = probs.argmax(axis=1)
    confidences = probs.max(axis=1)

    deadly_cols = [
        i for i, key in enumerate(classes)
        if (sp := taxonomy.get(key)) is not None and sp.toxicity is Toxicity.DEADLY
    ]
    # Mass on ALL deadly species per sample, which is what the safety layer
    # actually sums -- not merely the mass on the true one.
    deadly_mass = probs[:, deadly_cols].sum(axis=1) if deadly_cols else np.zeros(len(probs))

    tally: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"count": 0, "max_confidence": 0.0, "silent": 0,
                 "min_deadly_mass": 1.0, "max_deadly_mass": 0.0}
    )

    for true_idx, pred_idx, conf, mass in zip(
        labels, predictions, confidences, deadly_mass
    ):
        true_key, pred_key = classes[true_idx], classes[pred_idx]
        if true_key == pred_key:
            continue
        true_sp, pred_sp = taxonomy.get(true_key), taxonomy.get(pred_key)
        if true_sp is None or pred_sp is None:
            continue
        # The direction that harms people: truly deadly, predicted benign.
        if true_sp.toxicity is Toxicity.DEADLY and pred_sp.toxicity < Toxicity.TOXIC:
            entry = tally[(true_key, pred_key)]
            entry["count"] += 1
            entry["max_confidence"] = max(entry["max_confidence"], float(conf))
            entry["min_deadly_mass"] = min(entry["min_deadly_mass"], float(mass))
            entry["max_deadly_mass"] = max(entry["max_deadly_mass"], float(mass))
            if mass < deadly_mass_threshold:
                entry["silent"] += 1

    rows = [
        {
            "true_species": t,
            "predicted_as": p,
            "count": v["count"],
            "max_confidence": round(v["max_confidence"], 4),
            # How many of those the user would never have been warned about.
            "silent": v["silent"],
            "min_deadly_mass": round(v["min_deadly_mass"], 4),
            "max_deadly_mass": round(v["max_deadly_mass"], 4),
        }
        for (t, p), v in tally.items()
    ]
    # Silent ones first: they are the ones that reach a person.
    return sorted(rows, key=lambda r: (-r["silent"], -r["count"], -r["max_confidence"]))


def deadly_recall(
    probs: np.ndarray, labels: np.ndarray, classes: list[str], taxonomy: Taxonomy
) -> dict[str, float]:
    """Per-species recall for the deadly classes, plus group-level recall.

    Group-level recall -- did we at least place it in a dangerous genus --
    is the metric that maps onto the product's actual behaviour, since the
    app warns at group level rather than committing to a species.
    """
    deadly = taxonomy.deadly_keys()
    predictions = probs.argmax(axis=1)
    out: dict[str, float] = {}

    group_hit = group_total = 0
    for idx, key in enumerate(classes):
        if key not in deadly:
            continue
        mask = labels == idx
        if not mask.any():
            continue
        out[key] = float((predictions[mask] == idx).mean())

        genus = taxonomy.genus_of(key)
        pred_genera = np.array([taxonomy.genus_of(classes[p]) for p in predictions[mask]])
        group_hit += int((pred_genera == genus).sum())
        group_total += int(mask.sum())

    out["_group_level_recall"] = group_hit / max(1, group_total)
    return out


def coverage_precision_curve(
    probs: np.ndarray, labels: np.ndarray, thresholds: np.ndarray | None = None
) -> list[dict]:
    """How often can we answer, and how often are we right when we do."""
    if thresholds is None:
        thresholds = np.arange(0.1, 1.0, 0.05)
    confidences = probs.max(axis=1)
    correct = probs.argmax(axis=1) == labels

    rows = []
    for t in thresholds:
        mask = confidences >= t
        rows.append(
            {
                "threshold": round(float(t), 2),
                "coverage": float(mask.mean()),
                "precision": float(correct[mask].mean()) if mask.any() else None,
                "n": int(mask.sum()),
            }
        )
    return rows


def evaluate(
    probs: np.ndarray,
    labels: np.ndarray,
    classes: list[str],
    taxonomy: Taxonomy,
    risk_matrix: np.ndarray,
    topk: tuple[int, ...] = (1, 3, 5),
) -> dict:
    from .calibrate import expected_calibration_error, reliability_table

    report = {
        "n_samples": int(len(labels)),
        "n_classes": len(classes),
        "accuracy": {f"top{k}": topk_accuracy(probs, labels, k) for k in topk},
        "genus_accuracy": genus_accuracy(probs, labels, classes, taxonomy),
        "risk_weighted_error": risk_weighted_error(probs, labels, risk_matrix),
        "expected_calibration_error": expected_calibration_error(probs, labels),
        "deadly_recall": deadly_recall(probs, labels, classes, taxonomy),
        "dangerous_confusions": dangerous_confusions(probs, labels, classes, taxonomy),
        "coverage_precision": coverage_precision_curve(probs, labels),
        "reliability": reliability_table(probs, labels),
    }

    n_dangerous = sum(r["count"] for r in report["dangerous_confusions"])
    report["dangerous_confusion_count"] = n_dangerous
    report["dangerous_confusion_rate"] = n_dangerous / max(1, len(labels))

    # The subset that reaches a person. The safety layer raises the lethal
    # warning whenever the deadly species hold DEADLY_MASS_THRESHOLD between
    # them, so a confusion above that line is caught in the app even though
    # the model got it wrong. Below it, the user is told a harmless name and
    # nothing else.
    n_silent = sum(r["silent"] for r in report["dangerous_confusions"])
    report["silent_dangerous_confusion_count"] = n_silent
    report["silent_dangerous_confusion_rate"] = n_silent / max(1, len(labels))
    report["deadly_mass_threshold"] = DEADLY_MASS_THRESHOLD

    if n_dangerous:
        log.warning(
            "%d dangerous confusions in %d samples (%.3f%%), of which %d are "
            "SILENT (deadly mass < %.0f%%, so no warning reaches the user) "
            "-- review before release",
            n_dangerous, len(labels), 100 * n_dangerous / len(labels),
            n_silent, 100 * DEADLY_MASS_THRESHOLD,
        )
    return report


def write_model_card(report: dict, calibration: dict | None, out_path: str | Path) -> Path:
    """Emit a human-readable model card.

    Competitors publish nothing of the sort. Publishing this is both a
    credibility asset and a forcing function on our own honesty.
    """
    out_path = Path(out_path)
    acc = report["accuracy"]
    lines = [
        "# Model card — Funga classifier",
        "",
        "## What this model does",
        "",
        "Given a photograph and optional field metadata (month, location), it",
        "returns a probability distribution over the species in its label space.",
        "It does **not** determine edibility and must never be presented as doing so.",
        "",
        "## Headline numbers",
        "",
        f"- Evaluated on **{report['n_samples']}** held-out images across **{report['n_classes']}** species",
        f"- Top-1 species accuracy: **{acc.get('top1', 0):.1%}**",
        f"- Top-5 species accuracy: **{acc.get('top5', 0):.1%}**",
        f"- Genus-level accuracy: **{report['genus_accuracy']:.1%}**",
        f"- Risk-weighted error: **{report['risk_weighted_error']:.3f}**",
        f"- Expected calibration error: **{report['expected_calibration_error']:.4f}**",
        "",
        "Genus accuracy is the more honest figure. Many fungi cannot be separated",
        "to species from a photograph at all, by this model or by an expert.",
        "",
        "## Safety-critical results",
        "",
        f"Dangerous confusions (a deadly species predicted as something a user might eat): "
        f"**{report['dangerous_confusion_count']}** "
        f"({report['dangerous_confusion_rate']:.4%} of samples)",
        "",
        f"Of those, **{report.get('silent_dangerous_confusion_count', 0)}** are "
        f"**silent**: the deadly species held less than "
        f"{report.get('deadly_mass_threshold', DEADLY_MASS_THRESHOLD):.0%} of the probability "
        f"mass, so the app's lethal warning never fires and the user is shown "
        f"a harmless name with no hazard line. The rest are caught by the "
        f"safety layer and the user sees the warning regardless. **The silent "
        f"count is the one that reaches a person.**",
        "",
    ]

    if report["dangerous_confusions"]:
        lines += [
            "`Silent` is the count the app would NOT have warned about. "
            "`Deadly mass` is how much probability stayed on the deadly "
            "species across those samples; the safety layer warns from "
            f"{report.get('deadly_mass_threshold', DEADLY_MASS_THRESHOLD):.0%} upward, at any "
            "rank.",
            "",
            "| True species | Predicted as | Count | Silent | Deadly mass "
            "(min–max) | Max confidence |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
        for row in report["dangerous_confusions"][:20]:
            lines.append(
                f"| _{row['true_species']}_ | _{row['predicted_as']}_ "
                f"| {row['count']} | **{row.get('silent', 0)}** "
                f"| {row.get('min_deadly_mass', 0):.3f}–"
                f"{row.get('max_deadly_mass', 0):.3f} "
                f"| {row['max_confidence']:.3f} |"
            )
        lines.append("")
    else:
        lines += ["No dangerous confusions were observed on this evaluation set.", ""]

    lines += ["### Recall on deadly species", "", "| Species | Recall |", "| --- | ---: |"]
    for key, value in sorted(report["deadly_recall"].items()):
        label = "**Group-level (genus) recall**" if key.startswith("_") else f"_{key}_"
        lines.append(f"| {label} | {value:.1%} |")
    lines.append("")

    if calibration:
        lines += [
            "## Calibration",
            "",
            f"- Temperature: **{calibration['temperature']:.3f}**",
            f"- ECE before scaling: {calibration['ece_before']:.4f}",
            f"- ECE after scaling: **{calibration['ece_after']:.4f}**",
            f"- Confidence threshold for {calibration['target_precision']:.0%} precision: "
            f"**{calibration['confidence_threshold']:.2f}**",
            f"- Coverage at that threshold: **{calibration['coverage']:.1%}**",
            "",
            "Below the threshold the app declines to name a species and asks for",
            "further evidence instead. Low coverage is a deliberate outcome.",
            "",
        ]

    lines += [
        "## Coverage versus precision",
        "",
        "| Confidence threshold | Coverage | Precision |",
        "| ---: | ---: | ---: |",
    ]
    for row in report["coverage_precision"]:
        if row["precision"] is None:
            continue
        lines.append(
            f"| {row['threshold']:.2f} | {row['coverage']:.1%} | {row['precision']:.1%} |"
        )

    lines += [
        "",
        "## Known limitations",
        "",
        "- Trained predominantly on citizen-science photographs, which are biased",
        "  towards photogenic, mature, well-lit specimens. Real queries are worse.",
        "- Geographic coverage reflects where observers are dense, not where fungi are.",
        "- Species outside the label space cannot be recognised as absent; the",
        "  out-of-distribution check in the serving layer handles this, not the model.",
        "- Microscopic and chemical characters are invisible to it. Many genera",
        "  (notably _Cortinarius_, _Inocybe_, _Russula_) cannot be resolved to",
        "  species without them.",
        "",
        "## Intended use",
        "",
        "An aid to learning and to narrowing possibilities. Not a food-safety device.",
        "No output of this model should be used to decide whether to eat a mushroom.",
    ]

    out_path.write_text("\n".join(lines), encoding="utf-8")
    log.info("Model card -> %s", out_path)
    return out_path
