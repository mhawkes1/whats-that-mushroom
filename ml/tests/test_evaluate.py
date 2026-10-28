"""A dangerous confusion counts the model. Only some of them reach a person.

`dangerous_confusions` has always counted every case where a deadly species
was called something harmless. What it did not record, until 2026-10-28, was
**how much probability stayed on the deadly species** -- and that single
number decides whether the user ever hears about it.

`server/app/safety.py` raises the lethal warning whenever the deadly species
hold `dangerous_mass_threshold` (2%) between them, at *any* rank, because
`deadly_probability_mass` sums the whole distribution rather than the top of
it. So a confusion where the true deadly species kept 30% shows the full
"species that can kill" banner, while one where it kept 0.5% names a
harmless species and -- rule 1 renders nothing at all for
`NO_RECORDED_TOXICITY` -- shows no hazard line either.

Those two outcomes used to tally identically, which made the metric that
gates release blind to the layer that does the protecting. The first real
run's worst confusion (*Galerina marginata* called *Crepidotus cesatii* at
0.850) could not be judged from the model card at all.

These tests pin the measurement and, more importantly, pin the threshold
against safety.py's own default. `ml/` and `server/` are separate packages
with no import path between them, so the constant is duplicated; if the
safety layer's trigger moves and this one does not, the card would report
silence against a line the app no longer uses.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fungi_ml.evaluate import (  # noqa: E402
    DEADLY_MASS_THRESHOLD,
    dangerous_confusions,
    evaluate,
    write_model_card,
)
from fungi_ml.taxonomy import Taxonomy  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SAFETY = ROOT / "server" / "app" / "safety.py"

DEADLY = "galerina-marginata"
OTHER_DEADLY = "amanita-phalloides"
BENIGN = "crepidotus-cesatii"
FILLER = "stereum-hirsutum"
CLASSES = [DEADLY, OTHER_DEADLY, BENIGN, FILLER]
D, OD, B, F = range(4)


@pytest.fixture(scope="module")
def taxonomy() -> Taxonomy:
    return Taxonomy.load(ROOT / "data" / "taxonomy.seed.json")


def _sample(deadly: float, other_deadly: float = 0.0, benign: float | None = None):
    """One row predicting `benign` as argmax, with the deadly mass we choose.

    `benign` defaults to everything the deadly species did not claim, less a
    sliver for the filler, so a row stays a valid distribution at any deadly
    mass -- which is the variable every test here is actually moving.
    """
    row = np.zeros(4)
    row[D], row[OD] = deadly, other_deadly
    row[B] = 1.0 - deadly - other_deadly - 0.01 if benign is None else benign
    row[F] = 1.0 - row.sum()
    assert row[F] >= 0 and row.argmax() == B
    return row


def test_the_threshold_matches_the_safety_layers_own_default():
    """The two constants live in separate packages and must not drift.

    Read from source rather than imported: `server/` is not on `ml/`'s path,
    and a test that cannot run is not a guard.
    """
    source = SAFETY.read_text(encoding="utf-8")
    match = re.search(r"dangerous_mass_threshold: float = ([0-9.]+)", source)
    assert match, "safety.py no longer declares dangerous_mass_threshold"
    assert float(match.group(1)) == DEADLY_MASS_THRESHOLD, (
        "The safety layer's warning trigger has moved and evaluate.py's copy "
        "has not. The model card would report silent confusions against a "
        "line the app no longer uses."
    )


def test_a_confusion_above_the_threshold_is_not_silent(taxonomy):
    probs = np.array([_sample(deadly=0.05)])
    rows = dangerous_confusions(probs, np.array([D]), CLASSES, taxonomy)
    assert rows[0]["count"] == 1
    assert rows[0]["silent"] == 0, "5% clears the 2% trigger; the user is warned"


def test_a_confusion_below_the_threshold_is_silent(taxonomy):
    probs = np.array([_sample(deadly=0.01)])
    rows = dangerous_confusions(probs, np.array([D]), CLASSES, taxonomy)
    assert rows[0]["count"] == 1
    assert rows[0]["silent"] == 1, (
        "Below the trigger the app names a harmless species with no hazard "
        "line -- the dangerous_miss this project exists to prevent."
    )


def test_the_mass_is_summed_over_every_deadly_species(taxonomy):
    """Not merely the true one. The safety layer sums them all.

    1% on the funeral bell plus 1.5% on the death cap is 2.5% of mass on
    species that can kill, and the warning fires. Counting only the true
    label would have called this silent.
    """
    probs = np.array([_sample(deadly=0.01, other_deadly=0.015)])
    rows = dangerous_confusions(probs, np.array([D]), CLASSES, taxonomy)
    assert rows[0]["silent"] == 0
    assert rows[0]["min_deadly_mass"] == pytest.approx(0.025, abs=1e-6)


def test_rank_is_irrelevant(taxonomy):
    """A deadly species in fourth place still triggers the warning.

    `deadly_probability_mass` walks the whole distribution; only
    `straddles_dangerous_pair` is limited to the top five. A silent-count
    that quietly assumed a top-k window would overstate the danger.
    """
    probs = np.array([_sample(deadly=0.03, benign=0.60)])
    probs[0, F] = 1.0 - probs[0, :3].sum()
    assert probs[0].argsort()[::-1].tolist().index(D) == 2
    rows = dangerous_confusions(probs, np.array([D]), CLASSES, taxonomy)
    assert rows[0]["silent"] == 0


def test_the_mass_range_spans_the_samples_in_a_row(taxonomy):
    probs = np.array([_sample(0.30), _sample(0.004), _sample(0.08)])
    rows = dangerous_confusions(probs, np.array([D, D, D]), CLASSES, taxonomy)
    assert rows[0]["count"] == 3 and rows[0]["silent"] == 1
    assert rows[0]["min_deadly_mass"] == pytest.approx(0.004, abs=1e-6)
    assert rows[0]["max_deadly_mass"] == pytest.approx(0.30, abs=1e-6)


def test_silent_rows_sort_first(taxonomy):
    """Even behind a row with more confusions in it.

    A queue ordered by count puts the loud, caught failure above the quiet
    one that reaches somebody.
    """
    probs = np.array([_sample(0.40), _sample(0.40), _sample(0.001)])
    probs[2, B] = 0.0
    probs[2, F] = 1.0 - probs[2, :3].sum()  # argmax moves to the filler
    labels = np.array([D, D, D])
    rows = dangerous_confusions(probs, labels, CLASSES, taxonomy)
    assert len(rows) == 2
    assert rows[0]["predicted_as"] == FILLER and rows[0]["silent"] == 1
    assert rows[1]["count"] == 2 and rows[1]["silent"] == 0


def test_the_report_and_the_card_both_carry_the_silent_count(taxonomy, tmp_path):
    """Present in report.json is not the same as visible to a reviewer."""
    probs = np.array([_sample(0.30), _sample(0.004)])
    labels = np.array([D, D])
    risk = np.ones((4, 4), dtype=np.float32)
    report = evaluate(probs, labels, CLASSES, taxonomy, risk, topk=(1,))

    assert report["dangerous_confusion_count"] == 2
    assert report["silent_dangerous_confusion_count"] == 1
    assert report["silent_dangerous_confusion_rate"] == pytest.approx(0.5)
    assert report["deadly_mass_threshold"] == DEADLY_MASS_THRESHOLD

    card = write_model_card(report, None, tmp_path / "MODEL_CARD.md").read_text(
        encoding="utf-8"
    )
    assert "Silent" in card, "the table must name the column"
    assert "Deadly mass" in card
    assert "0.004" in card, "the measured range, not just the count"
