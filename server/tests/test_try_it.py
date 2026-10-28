"""The launcher must not describe the wrong backend.

`scripts/try_it.py` is the one command between a fresh clone and the app in
a browser, and the paragraph it prints is the only instruction most people
will ever read. It said "the classifier is a stub, so whatever it names is
meaningless" unconditionally.

That sentence is true of the stub and is **dangerous advice about a trained
model**: it tells the reader to disregard a real identification of a species
that might be lethal. It became wrong the moment a `model.onnx` was dropped
into `ml/runs/baseline/`, which is all that wiring the trained model takes --
no code change, no flag. So the one step that turns the stub into the real
thing was also the step that turned the instructions into a lie.

The launcher already reads `/health` before printing. These pin that it uses
what it read.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from try_it import closing_advice  # noqa: E402

STUB = {"model_loaded": False, "calibrated": False}
TRAINED = {"model_loaded": True, "calibrated": True}
TRAINED_UNCALIBRATED = {"model_loaded": True, "calibrated": False}


def test_the_stub_is_called_meaningless_only_when_it_is_the_stub():
    assert "meaningless" in closing_advice(STUB)
    for health in (TRAINED, TRAINED_UNCALIBRATED):
        advice = closing_advice(health)
        assert "meaningless" not in advice, (
            "a trained model's identification must not be described as "
            "meaningless -- that is advice to ignore a real warning"
        )
        assert "stub" not in advice.lower()


def test_a_real_identification_is_only_claimed_when_one_is_possible():
    assert "real identification" in closing_advice(TRAINED)
    assert "real identification" not in closing_advice(STUB)


def test_rule_four_is_stated_exactly_when_calibration_is_missing():
    """An uncalibrated percentage must not be presented as a confidence."""
    uncalibrated = closing_advice(TRAINED_UNCALIBRATED)
    assert "uncalibrated" in uncalibrated
    assert "Rule 4" in uncalibrated
    assert "uncalibrated" not in closing_advice(TRAINED)


def test_only_the_stub_run_is_told_how_to_load_a_model():
    assert "model.onnx" in closing_advice(STUB)
    assert "run this again" not in closing_advice(TRAINED)


@pytest.mark.parametrize("health", [STUB, TRAINED, TRAINED_UNCALIBRATED])
def test_every_state_keeps_the_things_that_must_always_be_said(health):
    """The consent gate, the refusal framing and the emergency route.

    The emergency screen is the one control that must never need a scroll,
    and step 4 is the only place the launcher points at it.
    """
    advice = closing_advice(health)
    assert "accept-all" in advice, "the per-item consent is the point of step 1"
    assert "AROUND the name" in advice, "the refusal framing is the product"
    assert "red cross" in advice and "offline" in advice
    assert "Ctrl-C" in advice


@pytest.mark.parametrize("health", [STUB, TRAINED, TRAINED_UNCALIBRATED])
def test_the_launcher_makes_no_edibility_claim(health):
    """Rule 1 reaches the terminal too.

    The same omission that left a soft edibility verdict in `disclaimer.py`
    through the September purge: a test that scans what `assess` returns
    never reads the text a launcher prints.
    """
    advice = closing_advice(health).lower()
    for phrase in ("edible", "safe to eat", "inedible", "not assessed as safe",
                   "choice edible", "good to eat"):
        assert phrase not in advice, f"the launcher says {phrase!r}"
