"""Deciding whether the photograph is something we know at all.

The test that matters most is `test_softmax_cannot_see_what_energy_sees`. It
is the whole reason this module exists: two inputs can produce byte-identical
softmax output and completely different energies, and the check this replaced
could only read the softmax.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from app.inference import softmax  # noqa: E402
from app.ood import (  # noqa: E402
    OodDetector,
    combine_views,
    fit_energy_threshold,
    free_energy,
)
from app.safety import SafetyLayer, Verdict  # noqa: E402
from app.config import settings  # noqa: E402
from app.taxonomy_service import TaxonomyService  # noqa: E402

import numpy as np  # noqa: E402


def recognised(rng, n_classes: int = 60):
    """Logits from a network that strongly activated one class."""
    logits = rng.normal(0.0, 1.0, n_classes)
    logits[rng.integers(n_classes)] += 8.0
    return logits


@pytest.fixture
def detector():
    rng = np.random.default_rng(0)
    energies = [free_energy(recognised(rng).tolist()) for _ in range(400)]
    return OodDetector(threshold=fit_energy_threshold(energies))


# --- The property the old check could not have -------------------------------


def test_softmax_cannot_see_what_energy_sees(detector):
    """Shift every logit down and softmax does not move; energy does.

    Softmax depends only on differences between logits, so it is invariant to
    a constant shift. An input the network has no features for produces
    exactly that: the same preferences, nothing strongly activated. The top-1
    probability rule accepts both of these at 98% confidence and puts a
    species name to the second one.
    """
    rng = np.random.default_rng(0)
    strong = recognised(rng)
    faint = strong - 7.0

    assert softmax(strong[None, :])[0].max() == pytest.approx(
        softmax(faint[None, :])[0].max()
    )
    assert softmax(strong[None, :])[0].max() > 0.20  # the old rule accepts both

    assert not detector.assess_logits(strong.tolist()).out_of_distribution
    assert detector.assess_logits(faint.tolist()).out_of_distribution


def test_energy_is_lower_when_something_is_recognised():
    strong = [8.0] + [0.0] * 59
    faint = [0.5] + [0.0] * 59
    assert free_energy(strong) < free_energy(faint)


def test_energy_shifts_exactly_with_the_logits():
    """The property the whole method rests on, stated directly."""
    base = [1.0, 2.0, 3.0, 4.0]
    shifted = [value - 5.0 for value in base]
    assert free_energy(shifted) == pytest.approx(free_energy(base) + 5.0)


def test_energy_does_not_overflow_on_confident_logits():
    """A trained network produces large logits; exp() of them must not blow up."""
    assert math.isfinite(free_energy([900.0, 0.0, -900.0]))


def test_energy_rejects_nonsense_inputs():
    with pytest.raises(ValueError):
        free_energy([])
    with pytest.raises(ValueError):
        free_energy([1.0], temperature=0.0)


# --- Fitting the threshold ---------------------------------------------------


def test_the_threshold_flags_the_rate_it_was_asked_for():
    rng = np.random.default_rng(1)
    energies = [free_energy(recognised(rng).tolist()) for _ in range(1000)]
    threshold = fit_energy_threshold(energies, false_unknown_rate=0.05)

    flagged = sum(1 for e in energies if e > threshold) / len(energies)
    assert flagged == pytest.approx(0.05, abs=0.02)


def test_a_stricter_rate_gives_a_higher_threshold():
    """Accepting fewer false unknowns must mean flagging less, not more."""
    rng = np.random.default_rng(2)
    energies = [free_energy(recognised(rng).tolist()) for _ in range(500)]
    assert fit_energy_threshold(energies, 0.01) > fit_energy_threshold(energies, 0.20)


def test_fitting_rejects_an_impossible_rate():
    for rate in (0.0, 1.0, -0.1, 1.5):
        with pytest.raises(ValueError):
            fit_energy_threshold([1.0, 2.0], false_unknown_rate=rate)
    with pytest.raises(ValueError):
        fit_energy_threshold([])


# --- Combining views ---------------------------------------------------------


def test_views_are_averaged_not_minimised():
    """One good frame must not vouch for a set that is otherwise unreadable.

    Taking the minimum would let the most flattering view decide, and the
    photographs that most need flagging are exactly the ones where a single
    frame happens to look like a mushroom.
    """
    energies = [-8.0, -1.0, -1.0]
    assert combine_views(energies) == pytest.approx(-10.0 / 3)
    assert combine_views(energies) > min(energies)


def test_combining_needs_something_to_combine():
    with pytest.raises(ValueError):
        combine_views([])


# --- Refusing to guess before it is fitted -----------------------------------


def test_an_unfitted_detector_says_so_rather_than_guessing():
    """Rule 4 applied to this check: no threshold means no verdict.

    Inventing an energy threshold would be the same error as serving
    uncalibrated confidence as confidence. The caller has to be able to tell,
    so it can fall back to the weaker rule knowingly.
    """
    verdict = OodDetector().assess_logits([5.0, 1.0, 0.0])
    assert verdict.fitted is False
    assert verdict.out_of_distribution is False
    assert verdict.threshold is None
    assert verdict.margin is None


def test_a_calibration_without_energy_fields_yields_an_unfitted_detector():
    """Checkpoints calibrated before this existed must still serve."""
    assert OodDetector.from_calibration({"temperature": 1.3}).fitted is False


def test_a_calibration_with_energy_fields_is_fitted():
    detector = OodDetector.from_calibration(
        {"energy_threshold": -4.5, "energy_temperature": 1.0}
    )
    assert detector.fitted
    assert detector.threshold == -4.5


# --- What the safety layer does with it --------------------------------------


@pytest.fixture
def taxonomy():
    return TaxonomyService.load(settings.taxonomy_path)


def test_the_safety_layer_falls_back_when_no_threshold_is_fitted(taxonomy):
    """Unfitted must mean the old rule, not silent acceptance."""
    layer = SafetyLayer(taxonomy, ood_threshold=0.20)
    assert not layer.ood_detector.fitted

    low = [("amanita-phalloides", 0.05), ("agaricus-campestris", 0.04)]
    assert layer.is_out_of_scope(low, energy=None) is True
    assert layer.is_out_of_scope(low, energy=-99.0) is True, (
        "an unfitted detector must not override the fallback"
    )


def test_a_fitted_detector_overrules_a_confident_ranking(taxonomy):
    """The point of the change, at the level the user sees.

    A ranking can be confident and still be about nothing. When energy says
    the network recognised nothing, the verdict is out of scope however high
    the top probability climbed.
    """
    layer = SafetyLayer(taxonomy, ood_detector=OodDetector(threshold=-5.0))
    confident = [("cantharellus-cibarius", 0.97), ("hydnum-repandum", 0.02)]

    assert layer.assess(confident, energy=-9.0).verdict is not Verdict.OUT_OF_SCOPE
    assert layer.assess(confident, energy=-1.0).verdict is Verdict.OUT_OF_SCOPE


def test_not_recognising_something_is_never_presented_as_reassurance(taxonomy):
    """An unrecognised mushroom is not a harmless one.

    Sixty species is a small fraction of what grows in Britain, and what is
    missing skews uncommon -- which does not exclude the lethal. The refusal
    has to say so, and say it before the candidate list it is disowning.
    """
    layer = SafetyLayer(taxonomy, ood_detector=OodDetector(threshold=-5.0))
    result = layer.assess([("hydnum-repandum", 0.9)], energy=-1.0)

    assert result.verdict is Verdict.OUT_OF_SCOPE
    assert result.warnings, "an out-of-scope verdict must carry a warning"
    assert "cannot rule out" in result.warnings[0]
    assert "kill" in result.warnings[0]


def test_an_out_of_scope_verdict_still_warns_about_a_deadly_candidate(taxonomy):
    """Declining to identify must not drop a warning that was already earned."""
    layer = SafetyLayer(taxonomy, ood_detector=OodDetector(threshold=-5.0))
    result = layer.assess(
        [("hydnum-repandum", 0.6), ("amanita-phalloides", 0.4)], energy=-1.0
    )

    assert result.verdict is Verdict.OUT_OF_SCOPE
    assert result.deadly_in_play
    blob = " ".join(result.warnings).lower()
    assert "can kill" in blob or "cannot rule out" in blob
