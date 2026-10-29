"""The "how to tell them apart" panel.

The one piece of reference content this app can offer that a
characteristics table cannot: `character_states` was written as a
classifier tiebreaker, so it is thin as a description and dense as a
comparison, and this renders it as the second thing.

Two ways it could go wrong, and both are safety faults rather than
cosmetic ones: a feature both species show presented as a difference, and
an edibility claim arriving through the back door of a comparison.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from app.distinguish import comparisons  # noqa: E402
from app.taxonomy_service import TaxonomyService, Toxicity  # noqa: E402


@pytest.fixture(scope="module")
def taxonomy() -> TaxonomyService:
    return TaxonomyService.load(ROOT / "data" / "taxonomy.seed.json")


def test_a_state_both_species_show_is_never_a_difference(taxonomy):
    """The fault this panel exists to avoid.

    The list-width convention makes the two sides overlap by design: a
    deadly species lists its states generously so a contradiction cannot
    falsely dismiss it, the safe half of the pair lists them tightly. The
    funeral bell declares all four ring states and honey fungus declares
    one, so "funeral bell: four things / honey fungus: firm skirt" would
    have a reader check the ring, see the firm skirt BOTH show, and
    conclude honey fungus.
    """
    for key in taxonomy.species:
        for comparison in comparisons(taxonomy, key):
            for d in comparison.differences:
                assert not (set(d.this_only) & set(d.other_only)), (
                    f"{key} vs {comparison.species_key}: {d.character} puts the "
                    f"same state on both sides"
                )
                assert not (set(d.this_only) & set(d.shared))
                assert not (set(d.other_only) & set(d.shared))


def test_a_row_that_settles_nothing_is_not_emitted(taxonomy):
    """A character with no exclusive state either way reads as a check and
    is not one, so it must not appear at all."""
    for key in taxonomy.species:
        for comparison in comparisons(taxonomy, key):
            for d in comparison.differences:
                assert d.this_only or d.other_only, (
                    f"{key} vs {comparison.species_key}: {d.character} has "
                    f"nothing exclusive to either side"
                )


def test_a_shared_state_is_reported_rather_than_dropped(taxonomy):
    """Not merely allowed -- the data has plenty, and losing them silently
    would make the panel read as more decisive than it is."""
    shared_rows = [
        d
        for key in taxonomy.species
        for c in comparisons(taxonomy, key)
        for d in c.differences
        if d.shared
    ]
    assert shared_rows, (
        "no comparison reports a shared state, which given the list-width "
        "convention means they are being dropped rather than being absent"
    )


def test_an_inseparable_lookalike_is_kept_and_not_hidden(taxonomy):
    """A pair nothing recorded separates is a true and useful thing to be
    told. Dropping it turns a gap in the data into an absence of risk."""
    inseparable = [
        (key, c.species_key)
        for key in taxonomy.species
        for c in comparisons(taxonomy, key)
        if not c.differences
    ]
    assert inseparable, "inseparable pairs exist in the data and must survive"


def test_the_dangerous_lookalike_comes_first(taxonomy):
    """The ordering question is which one it hurts to miss, not which one
    is best separated."""
    for key in taxonomy.species:
        found = comparisons(taxonomy, key)
        hazards = [int(Toxicity[c.toxicity]) for c in found]
        assert hazards == sorted(hazards, reverse=True), (
            f"{key}: lookalikes are not ordered worst hazard first"
        )


def test_no_comparison_says_which_one_is_preferable(taxonomy):
    """Rule 1, in the place it would most plausibly get in.

    A comparison invites a judgement the app does not make. Put a TOXIC
    species beside one with no recorded hazard and a reader supplies "so
    the other is fine" -- so the data must carry the recorded hazard and
    nothing resembling a recommendation.
    """
    banned = ("edible", "safe", "poisonous", "choice", "avoid", "prefer",
              "better", "worse", "harmless")
    for key in taxonomy.species:
        for c in comparisons(taxonomy, key):
            blob = " ".join(
                [c.scientific_name, c.toxicity, *c.common_names]
                + [f"{d.label} {' '.join(d.this_only)} "
                   f"{' '.join(d.other_only)} {' '.join(d.shared)}"
                   for d in c.differences]
            ).lower()
            for word in banned:
                assert word not in blob, (
                    f"{key} vs {c.species_key}: comparison text contains "
                    f"{word!r}, which is a judgement the app does not make"
                )


def test_it_is_served_only_under_a_species_verdict():
    """Under anything else no species was asserted, and a "how to tell this
    from X" heading beside a refusal is the name the app just declined to
    give, printed larger.

    Read from source: exercising it needs a model, and what is pinned is
    that the gate is on the verdict rather than on the candidate list
    being non-empty -- `dangerous_group` has candidates too.
    """
    source = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
    block = source.split("def _how_to_tell_apart(")[1].split("def ")[0]
    assert "Verdict.SPECIES" in block, (
        "the panel must be gated on the species verdict, not on having "
        "candidates -- dangerous_group has those as well"
    )
