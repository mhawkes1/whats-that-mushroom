"""Spore print colour matching.

The tests that matter here are the refusals. Matching a clean swatch is easy;
the failure that hurts a user is a confident answer drawn from a photograph
that could not support one.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from app.characters import CHARACTERS  # noqa: E402
from app.spore_print import (  # noqa: E402
    AMBIGUOUS_MARGIN,
    REFERENCE_CHART,
    ciede2000,
    match_spore_print,
    rank_against_chart,
    rgb_to_lab,
    white_balance,
)

NEUTRAL_WHITE = (243.0, 243.0, 243.0)


def photograph(
    true_rgb: tuple[int, int, int],
    cast: tuple[float, float, float] = (1.0, 1.0, 1.0),
    exposure: float = 1.0,
) -> tuple[float, float, float]:
    """Simulate a camera: apply the illuminant and exposure, then clip.

    The clip matters. A sensor cannot record above 255, and code that is only
    ever tested on unclipped values will meet clipping for the first time in
    a user's kitchen.
    """
    return tuple(
        min(255.0, max(0.0, channel * k * exposure))
        for channel, k in zip(true_rgb, cast)
    )


def test_chart_options_match_the_character_catalogue_exactly():
    """The matched string goes straight back to /answer.

    If the chart and the catalogue drift apart, the app submits an answer the
    server does not recognise -- and does it silently, which is worse.
    """
    catalogue = set(CHARACTERS["spore_print_colour"].options)
    assert set(REFERENCE_CHART) == catalogue


def test_every_chart_colour_matches_itself_under_neutral_light():
    for option, rgb in REFERENCE_CHART.items():
        reading = match_spore_print(tuple(float(c) for c in rgb), NEUTRAL_WHITE)
        assert reading.confident, f"{option}: {reading.reason}"
        assert reading.option == option


def test_chart_colours_are_further_apart_than_the_ambiguity_margin():
    """A chart whose own entries sat inside the margin could never match anything."""
    labs = {k: rgb_to_lab(v) for k, v in REFERENCE_CHART.items()}
    names = list(labs)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            assert ciede2000(labs[a], labs[b]) > AMBIGUOUS_MARGIN


def test_a_warm_bulb_does_not_turn_white_into_cream():
    """The correction is the reason the white half of the card is there.

    Tungsten light reddens everything. Uncorrected, a white print measures
    warm; the reference card measures equally warm, so dividing it out
    recovers the neutral.
    """
    cast = (1.25, 1.0, 0.75)  # tungsten
    exposure = 0.75  # dim enough that nothing clips

    for option in ("Black", "Rust or cinnamon brown", "Chocolate or purple-brown"):
        reading = match_spore_print(
            photograph(REFERENCE_CHART[option], cast, exposure),
            photograph((243, 243, 243), cast, exposure),
        )
        assert reading.confident, f"{option}: {reading.reason}"
        assert reading.option == option


def test_the_same_print_matches_the_same_colour_at_any_exposure():
    """Exposure must not change the answer.

    This is why the correction normalises brightness and not just hue. A print
    photographed by a window and the same print photographed in a dim kitchen
    are the same print, and must not land on different chart entries.
    """
    for option in ("Rust or cinnamon brown", "Chocolate or purple-brown", "Olive or yellow"):
        matched = {
            match_spore_print(
                photograph(REFERENCE_CHART[option], exposure=e),
                photograph((243, 243, 243), exposure=e),
            ).option
            for e in (0.45, 0.7, 1.0)
        }
        assert matched == {option}, f"{option} drifted across exposures: {matched}"


def test_white_balance_maps_the_card_onto_the_reference_white():
    assert white_balance((243.0, 243.0, 243.0), (243.0, 243.0, 243.0)) == (243, 243, 243)
    # A dim neutral card scales the sample up rather than leaving it dark.
    assert white_balance((60.0, 60.0, 60.0), (120.0, 120.0, 120.0)) == (122, 122, 122)


def test_refuses_when_the_card_is_too_dark():
    reading = match_spore_print((30.0, 28.0, 27.0), (20.0, 20.0, 20.0))
    assert not reading.confident
    assert reading.option is None
    assert "dark" in reading.reason.lower()


def test_refuses_when_the_card_is_blown_out():
    """A clipped white carries no ratio, so there is nothing to correct with."""
    reading = match_spore_print((250.0, 250.0, 250.0), (252.0, 254.0, 255.0))
    assert not reading.confident
    assert "overexposed" in reading.reason.lower()


def test_refuses_under_a_strongly_coloured_light():
    reading = match_spore_print((200.0, 120.0, 60.0), (220.0, 110.0, 40.0))
    assert not reading.confident
    assert "light" in reading.reason.lower()


def test_refuses_when_the_sample_sits_between_two_chart_colours():
    """The white/pink boundary is the one that matters.

    It is the distinction that separates an Amanita from a young Agaricus, so
    a reading that lands between them must decline rather than pick a side.
    """
    white = REFERENCE_CHART["White or cream"]
    pink = REFERENCE_CHART["Pink"]
    midpoint = tuple((a + b) / 2 for a, b in zip(white, pink))

    reading = match_spore_print(midpoint, NEUTRAL_WHITE)
    assert not reading.confident
    assert reading.option is None
    assert "too close to call" in reading.reason
    # The ranking still comes back, for ordering the manual picker.
    assert {m.option for m in reading.ranked[:2]} == {"White or cream", "Pink"}


def test_refuses_when_nothing_on_the_chart_is_close():
    """Saturated blue is not a spore colour; they photographed something else."""
    reading = match_spore_print((20.0, 40.0, 220.0), NEUTRAL_WHITE)
    assert not reading.confident
    assert "does not match anything" in reading.reason


def test_rejects_values_that_are_not_colours():
    for bad in [(-1.0, 0.0, 0.0), (0.0, 300.0, 0.0), (float("nan"), 0.0, 0.0)]:
        reading = match_spore_print(bad, NEUTRAL_WHITE)
        assert not reading.confident
        assert "usable RGB" in reading.reason


def test_ranking_is_ordered_and_complete():
    ranked = rank_against_chart(REFERENCE_CHART["Black"])
    assert len(ranked) == len(REFERENCE_CHART)
    assert ranked[0].option == "Black"
    assert all(ranked[i].distance <= ranked[i + 1].distance for i in range(len(ranked) - 1))


@pytest.mark.parametrize("option", list(REFERENCE_CHART))
def test_a_confident_reading_always_names_a_real_answer_option(option):
    """Whatever comes back must be submittable to /answer unchanged."""
    reading = match_spore_print(tuple(float(c) for c in REFERENCE_CHART[option]), NEUTRAL_WHITE)
    if reading.confident:
        assert reading.option in CHARACTERS["spore_print_colour"].options
