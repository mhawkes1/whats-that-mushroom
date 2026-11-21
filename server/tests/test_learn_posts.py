"""The two numbers the percentages post states are copies of live defaults.

`test_character_guidance.py` is the precedent and the reason: a count
written into prose is a hand-kept copy of a fact that lives in the code,
and this project has already shipped one that was wrong -- `cap_surface`'s
safety note said four deadly species when it contradicts five, in the one
sentence written to warn about it.

`what-the-percentages-mean` tells a beginner two numbers that decide what
they see: the share of probability a deadly species needs before the full
warning fires, and how often the app is right when it does commit to a
species. Both are defaults in code that nothing stops anybody tuning. No
expected value is restated below -- each is read from the source that owns
it, so moving the default fails the test that owns the sentence.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
POSTS = ROOT / "app" / "src" / "content" / "posts.ts"
SAFETY = ROOT / "server" / "app" / "safety.py"
CALIBRATE = ROOT / "ml" / "fungi_ml" / "calibrate.py"


def _post(slug: str) -> str:
    """The one post's text, flattened. Read as source rather than imported:
    `ml/` and the client are separate packages with no import path to here,
    and a test that cannot run is not a guard."""
    body = POSTS.read_text(encoding="utf-8")
    start = body.index(f"slug: '{slug}'")
    nxt = body.find("    slug: '", start + 1)
    return re.sub(r"\s+", " ", body[start : nxt if nxt != -1 else len(body)])


@pytest.fixture(scope="module")
def percentages() -> str:
    return _post("what-the-percentages-mean")


def test_the_post_exists_at_all(percentages: str) -> None:
    assert "What the percentages mean" in percentages


def test_it_states_the_mass_threshold_the_safety_layer_actually_uses(
    percentages: str,
) -> None:
    """Rule 3 is the post's whole middle section, and it quotes the figure."""
    match = re.search(
        r"dangerous_mass_threshold: float = ([\d.]+)", SAFETY.read_text(encoding="utf-8")
    )
    assert match, "safety.py no longer declares dangerous_mass_threshold"
    stated = f"{float(match.group(1)):.0%}"
    assert stated in percentages, (
        f"the post must say {stated}; safety.py warns from "
        f"{match.group(1)} of the probability mass"
    )


def test_it_states_the_precision_the_naming_bar_is_fitted_for(
    percentages: str,
) -> None:
    """'I am right about N times in 100' is the bar, not a round number."""
    match = re.search(
        r"target_precision: float = ([\d.]+)", CALIBRATE.read_text(encoding="utf-8")
    )
    assert match, "calibrate.py no longer declares target_precision"
    stated = f"{round(float(match.group(1)) * 100)} times in 100"
    assert stated in percentages, (
        f"the post must say '{stated}'; the threshold is fitted for "
        f"precision {match.group(1)}"
    )


def test_it_does_not_present_the_percentages_as_calibrated(
    percentages: str,
) -> None:
    """`calibrated` is false wherever the model is, and the post is bundled
    into the client where no health check reaches it. So it has to carry its
    own caveat rather than inherit one."""
    assert "has not been checked" in percentages
