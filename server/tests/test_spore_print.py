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


# --- Reading the patches off a photograph ------------------------------------


def a_card(
    deposit: tuple[int, int, int],
    white: tuple[int, int, int] = (243, 243, 243),
    size: tuple[int, int] = (400, 200),
):
    """A half-white card with a deposit on the left, white reference right."""
    from PIL import Image

    image = Image.new("RGB", size, white)
    image.paste(
        Image.new("RGB", (size[0] // 2, size[1]), deposit), (0, 0)
    )
    return image


LEFT_HALF = (0.05, 0.2, 0.35, 0.6)
RIGHT_HALF = (0.6, 0.2, 0.35, 0.6)


def test_a_photographed_print_matches_the_chart():
    from app.spore_print import read_from_photograph

    for option, rgb in REFERENCE_CHART.items():
        reading = read_from_photograph(a_card(rgb), LEFT_HALF, RIGHT_HALF)
        assert reading.confident, f"{option}: {reading.reason}"
        assert reading.option == option


def test_sampling_takes_the_median_not_the_mean():
    """The reason the statistic is a median.

    A black deposit on paper collects dust specks and a glare highlight or
    two. A mean folds them in and drags the sample toward grey, which is a
    different chart entry; a median ignores anything that is not most of the
    patch.
    """
    from app.spore_print import read_from_photograph, sample_patch

    image = a_card(REFERENCE_CHART["Black"])
    # Scatter bright specks across the deposit, as dust and glare would.
    for x in range(5, 190, 9):
        for y in range(45, 155, 11):
            image.putpixel((x, y), (255, 255, 255))

    sampled = sample_patch(image, LEFT_HALF)
    assert sampled == pytest.approx(REFERENCE_CHART["Black"], abs=1.0), (
        "specks should not move a median"
    )

    reading = read_from_photograph(image, LEFT_HALF, RIGHT_HALF)
    assert reading.option == "Black"


def test_sampling_is_independent_of_image_resolution():
    """Regions are fractions, so the client need not know what it captured at."""
    from app.spore_print import sample_patch

    small = sample_patch(a_card((120, 90, 60), size=(200, 100)), LEFT_HALF)
    large = sample_patch(a_card((120, 90, 60), size=(1600, 800)), LEFT_HALF)
    assert small == pytest.approx(large, abs=1.0)


def test_a_region_outside_the_image_is_refused():
    from app.spore_print import sample_patch

    for bad in [(0.8, 0.0, 0.5, 0.5), (0.0, 0.9, 0.2, 0.4), (-0.1, 0.0, 0.2, 0.2)]:
        with pytest.raises(ValueError):
            sample_patch(a_card((100, 100, 100)), bad)


def test_a_region_with_no_area_is_refused():
    from app.spore_print import sample_patch

    for bad in [(0.1, 0.1, 0.0, 0.2), (0.1, 0.1, 0.2, -0.1)]:
        with pytest.raises(ValueError):
            sample_patch(a_card((100, 100, 100)), bad)


def test_a_patch_too_small_to_average_is_refused():
    """A handful of pixels is one speck away from a different answer."""
    from app.spore_print import sample_patch

    with pytest.raises(ValueError, match="larger area"):
        sample_patch(a_card((100, 100, 100), size=(40, 40)), (0.0, 0.0, 0.05, 0.05))


def test_a_photograph_under_a_warm_bulb_still_matches():
    """The white half is in the same frame precisely so this works."""
    from app.spore_print import read_from_photograph

    cast, exposure = (1.25, 1.0, 0.75), 0.75
    for option in ("Black", "Rust or cinnamon brown", "Chocolate or purple-brown"):
        lit = tuple(
            int(min(255, c * k * exposure))
            for c, k in zip(REFERENCE_CHART[option], cast)
        )
        lit_white = tuple(int(min(255, 243 * k * exposure)) for k in cast)
        reading = read_from_photograph(
            a_card(lit, lit_white), LEFT_HALF, RIGHT_HALF
        )
        assert reading.confident, f"{option}: {reading.reason}"
        assert reading.option == option


def test_photographing_the_card_instead_of_the_print_is_refused():
    """Both patches on the white half: nothing on the chart is that colour."""
    from app.spore_print import read_from_photograph

    reading = read_from_photograph(a_card((243, 243, 243)), LEFT_HALF, RIGHT_HALF)
    # White paper is itself close to "White or cream", so the honest failure
    # here is ambiguity or a refusal -- never a confident dark answer.
    assert reading.option in (None, "White or cream")
