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
    # Relative to the threshold, not a literal. The trigger moved from 2%
    # to 1% on 2026-10-29 and the old literals -- 0.05 above, 0.01 below --
    # put the second one exactly ON the new line, where `mass < threshold`
    # is false. A fixture that encodes the current value tests the value
    # rather than the behaviour.
    probs = np.array([_sample(deadly=DEADLY_MASS_THRESHOLD * 5)])
    rows = dangerous_confusions(probs, np.array([D]), CLASSES, taxonomy)
    assert rows[0]["count"] == 1
    assert rows[0]["silent"] == 0, "well clear of the trigger; the user is warned"


def test_a_confusion_below_the_threshold_is_silent(taxonomy):
    probs = np.array([_sample(deadly=DEADLY_MASS_THRESHOLD / 2)])
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


# --- The release gate ------------------------------------------------------
#
# `scripts/make_model_card.py` is the only thing that turns a checkpoint into
# a document and a decision. These read its source rather than running it,
# because running it needs torch, a checkpoint and a prepared manifest -- the
# same reason `test_config.py` reads source.

CARD_SCRIPT = ROOT / "scripts" / "make_model_card.py"


def test_the_card_script_gates_on_the_silent_count_separately():
    """A documented exception on the total must not quietly cover these.

    The first real run had 10 dangerous confusions against SAFETY.md's
    required zero, so it needed `--max-dangerous-confusions` raised to pass
    a pipeline. If that one dial also governed the silent subset, raising it
    to admit nine caught-by-the-safety-layer confusions would have admitted
    a silent one in the same breath.
    """
    source = CARD_SCRIPT.read_text(encoding="utf-8")
    assert "--max-silent-dangerous-confusions" in source
    assert "silent_dangerous_confusion_count" in source, (
        "the script must read the silent count, not re-derive it"
    )
    # Both dials default to zero: SAFETY.md's number, not a comfortable one.
    # `rsplit`, because the module docstring names the first flag too.
    for flag in ("--max-dangerous-confusions", "--max-silent-dangerous-confusions"):
        block = source.rsplit(flag, 1)[1].split("    )")[0]
        assert "default=0" in block.replace(" ", ""), f"{flag} no longer defaults to 0"


def test_the_card_script_prints_the_silent_count_in_the_summary():
    """The terminal summary is what a person reads at 2am on a rented GPU."""
    source = CARD_SCRIPT.read_text(encoding="utf-8")
    summary = source.split("acc = report[")[1]
    assert "n_silent" in summary, "the printed summary omits the silent count"


def test_the_card_script_can_save_the_predictions():
    """Because the first run could not, and the question arrived too late.

    The deadly probability mass behind every dangerous confusion was
    computed during evaluation, used, and discarded. When we later asked
    what the app would have SHOWN for the worst one, nothing on disk could
    answer and the pod had been destroyed. A few megabytes of float16 makes
    every later question about a run answerable with no GPU and no dataset.
    """
    source = CARD_SCRIPT.read_text(encoding="utf-8")
    assert "--probs-out" in source
    block = source.split("np.savez_compressed(")[1].split("        )")[0]
    for key in ("probs=", "labels=", "classes=", "split=", "calibrated="):
        assert key in block, f"the predictions file omits {key!r}"
    assert "float16" in block, (
        "store float16: float32 doubles a file whose whole argument is that "
        "it is small enough to keep"
    )


def test_rescoring_appends_provenance_rather_than_overwriting_it():
    """A recomputed figure must never read as a measured one.

    `scripts/rescore_run.py` brings a finished run's card into step with a
    changed safety threshold, using the committed predictions and no GPU.
    That is a genuinely useful thing and a genuinely dangerous one: the
    card is the evidence for a release decision, and a number quietly
    recomputed under a new rule looks exactly like a number measured under
    it.

    So the record is appended, for the same reason an incident outcome is:
    a history that can be edited is one nobody can trust.
    """
    source = (ROOT / "scripts" / "rescore_run.py").read_text(encoding="utf-8")
    assert 'report.setdefault("rescored", []).append(' in source, (
        "rescoring must append to a list, not replace a field -- a run "
        "rescored twice has to show both"
    )
    assert '"from": was' in source, (
        "the record must say what the threshold was, not only what it became"
    )


def test_rescoring_leaves_the_threshold_independent_metrics_alone():
    """Accuracy, risk and the coverage curve do not depend on where the
    warning fires, so recomputing them would be inventing figures the
    predictions cannot support any better than the original run did."""
    source = (ROOT / "scripts" / "rescore_run.py").read_text(encoding="utf-8")
    for untouched in ("accuracy", "risk_weighted_error", "coverage_precision",
                      "deadly_recall", "genus_accuracy"):
        assert f'report["{untouched}"]' not in source, (
            f"rescoring must not rewrite {untouched}: it does not depend on "
            f"the deadly-mass threshold"
        )
