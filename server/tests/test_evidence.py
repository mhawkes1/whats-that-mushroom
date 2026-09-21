"""The answer-weighting mechanism.

The character-state table is empty, so most of these build a taxonomy with
states filled in by hand. That is the point: the mechanism has to be correct
before the data arrives, or there is no way to tell a wrong table from a
wrong update when it does.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from app.config import settings  # noqa: E402
from app.evidence import (  # noqa: E402
    DEADLY_PROBABILITY_FLOOR,
    described_coverage,
    likelihood_for,
    reweight,
)
from app.taxonomy_service import TaxonomyService, Toxicity  # noqa: E402

DEATH_CAP = "amanita-phalloides"
FIELD_MUSHROOM = "agaricus-campestris"
CHANTERELLE = "cantharellus-cibarius"


@pytest.fixture
def taxonomy() -> TaxonomyService:
    return TaxonomyService.load(settings.taxonomy_path)


def with_states(
    taxonomy: TaxonomyService, states: dict[str, dict[str, tuple[str, ...]]]
) -> TaxonomyService:
    """A copy of the taxonomy with `character_states` filled in for some species."""
    species = dict(taxonomy.species)
    for key, table in states.items():
        species[key] = replace(species[key], character_states=table)
    return TaxonomyService(species=species)


# --- With the table empty, which is today ------------------------------------


def test_an_empty_table_leaves_the_ranking_exactly_as_it_was(taxonomy):
    """No description means no evidence, so nothing may move.

    This is the honest no-op the mechanism degrades to before the review
    lands. It must be exact: a ranking that drifts slightly would be worse
    than one that does not move, because it would look like it worked.
    """
    ranked = [(DEATH_CAP, 0.5), (FIELD_MUSHROOM, 0.3), (CHANTERELLE, 0.2)]
    assert reweight(ranked, "gill_colour", "White", taxonomy) == ranked


def test_the_seed_taxonomy_ships_with_no_states_described(taxonomy):
    """A guard on the claim the docs make.

    If someone fills the table in, this fails and the docs saying answers are
    inert need updating with it.
    """
    coverage = described_coverage(taxonomy)
    assert coverage["described"] == 0
    assert coverage["fraction"] == 0.0


# --- The likelihood, per species ---------------------------------------------


def test_an_undescribed_species_is_untouched(taxonomy):
    evidence = likelihood_for(taxonomy[CHANTERELLE], "gill_colour", "White")
    assert evidence.verdict == "undescribed"
    assert evidence.likelihood == 1.0


def test_a_matching_answer_is_consistent_and_does_not_inflate(taxonomy):
    """Evidence eliminates; it never manufactures confidence."""
    described = with_states(taxonomy, {DEATH_CAP: {"gill_colour": ("White",)}})
    evidence = likelihood_for(described[DEATH_CAP], "gill_colour", "White")
    assert evidence.verdict == "consistent"
    assert evidence.likelihood == 1.0


def test_a_contradicting_answer_is_inconsistent(taxonomy):
    described = with_states(taxonomy, {DEATH_CAP: {"gill_colour": ("White",)}})
    evidence = likelihood_for(described[DEATH_CAP], "gill_colour", "Chocolate or black")
    assert evidence.verdict == "inconsistent"
    assert evidence.likelihood < 1.0


def test_matching_ignores_case_and_surrounding_space(taxonomy):
    described = with_states(taxonomy, {DEATH_CAP: {"gill_colour": ("White",)}})
    assert likelihood_for(described[DEATH_CAP], "gill_colour", "  white ").verdict == (
        "consistent"
    )


def test_contradicting_a_deadly_species_costs_less_than_a_harmless_one(taxonomy):
    """The risk asymmetry, applied to evidence rather than to loss.

    Being wrong about a brittlegill costs a meal; being wrong about a death
    cap costs a life. Dismissing the death cap therefore has to clear a
    higher bar.
    """
    described = with_states(
        taxonomy,
        {
            DEATH_CAP: {"gill_colour": ("White",)},
            CHANTERELLE: {"gill_colour": ("White",)},
        },
    )
    assert described[DEATH_CAP].toxicity is Toxicity.DEADLY
    assert described[CHANTERELLE].toxicity is not Toxicity.DEADLY

    deadly = likelihood_for(described[DEATH_CAP], "gill_colour", "Pink").likelihood
    harmless = likelihood_for(described[CHANTERELLE], "gill_colour", "Pink").likelihood
    assert deadly > harmless


# --- The update, over a distribution -----------------------------------------


def test_a_contradicted_candidate_falls_behind_a_consistent_one(taxonomy):
    described = with_states(
        taxonomy,
        {
            DEATH_CAP: {"spore_print_colour": ("White or cream",)},
            FIELD_MUSHROOM: {"spore_print_colour": ("Chocolate or purple-brown",)},
        },
    )
    ranked = [(DEATH_CAP, 0.5), (FIELD_MUSHROOM, 0.5)]
    updated = dict(
        reweight(ranked, "spore_print_colour", "Chocolate or purple-brown", described)
    )
    assert updated[FIELD_MUSHROOM] > updated[DEATH_CAP]


def test_the_result_is_a_normalised_distribution(taxonomy):
    described = with_states(taxonomy, {DEATH_CAP: {"gill_colour": ("White",)}})
    ranked = [(DEATH_CAP, 0.4), (FIELD_MUSHROOM, 0.35), (CHANTERELLE, 0.25)]
    updated = reweight(ranked, "gill_colour", "Pink", described)

    assert sum(score for _, score in updated) == pytest.approx(1.0)
    assert updated == sorted(updated, key=lambda kv: -kv[1])


def test_a_blank_answer_changes_nothing(taxonomy):
    described = with_states(taxonomy, {DEATH_CAP: {"gill_colour": ("White",)}})
    ranked = [(DEATH_CAP, 0.5), (FIELD_MUSHROOM, 0.5)]
    for blank in ("", "   "):
        assert reweight(ranked, "gill_colour", blank, described) == ranked


def test_an_answer_about_an_undescribed_character_changes_nothing(taxonomy):
    described = with_states(taxonomy, {DEATH_CAP: {"gill_colour": ("White",)}})
    ranked = [(DEATH_CAP, 0.5), (FIELD_MUSHROOM, 0.5)]
    assert reweight(ranked, "smell", "Aniseed", described) == ranked


def test_an_unknown_species_key_is_carried_through(taxonomy):
    """A label space wider than the taxonomy must not crash the update."""
    described = with_states(taxonomy, {DEATH_CAP: {"gill_colour": ("White",)}})
    ranked = [(DEATH_CAP, 0.5), ("not-a-species", 0.5)]
    updated = dict(reweight(ranked, "gill_colour", "Pink", described))
    assert "not-a-species" in updated


# --- The safety floor --------------------------------------------------------


def test_an_answer_cannot_extinguish_a_deadly_candidate(taxonomy):
    """CLAUDE.md rule 3, enforced inside the update.

    A 3% death cap that the user contradicts stays above the threshold at
    which the safety layer warns. Our descriptions are not reviewed; the user
    telling us the mushroom does not match one is not proof it is something
    else.
    """
    described = with_states(
        taxonomy,
        {
            DEATH_CAP: {"gill_colour": ("White",)},
            FIELD_MUSHROOM: {"gill_colour": ("Pink",)},
        },
    )
    ranked = [(FIELD_MUSHROOM, 0.97), (DEATH_CAP, 0.03)]
    updated = dict(reweight(ranked, "gill_colour", "Pink", described))

    assert updated[DEATH_CAP] >= DEADLY_PROBABILITY_FLOOR * 0.99


def test_repeated_contradictions_cannot_grind_a_deadly_candidate_away(taxonomy):
    """The floor has to hold across a whole interrogation, not one answer."""
    described = with_states(
        taxonomy,
        {
            DEATH_CAP: {
                "gill_colour": ("White",),
                "ring": ("Firm skirt-like ring",),
                "spore_print_colour": ("White or cream",),
            },
            FIELD_MUSHROOM: {
                "gill_colour": ("Pink",),
                "ring": ("Firm skirt-like ring",),
                "spore_print_colour": ("Chocolate or purple-brown",),
            },
        },
    )
    ranked = [(DEATH_CAP, 0.5), (FIELD_MUSHROOM, 0.5)]
    for character, answer in [
        ("gill_colour", "Pink"),
        ("spore_print_colour", "Chocolate or purple-brown"),
        ("gill_colour", "Pink"),
        ("spore_print_colour", "Chocolate or purple-brown"),
    ]:
        ranked = reweight(ranked, character, answer, described)

    assert dict(ranked)[DEATH_CAP] >= DEADLY_PROBABILITY_FLOOR * 0.99


def test_the_floor_does_not_promote_a_deadly_species_nobody_proposed(taxonomy):
    """Preserving alarm is right; manufacturing it is not."""
    described = with_states(
        taxonomy,
        {
            DEATH_CAP: {"gill_colour": ("White",)},
            FIELD_MUSHROOM: {"gill_colour": ("Pink",)},
        },
    )
    ranked = [(FIELD_MUSHROOM, 0.999), (DEATH_CAP, 0.001)]
    updated = dict(reweight(ranked, "gill_colour", "Pink", described))
    assert updated[DEATH_CAP] < DEADLY_PROBABILITY_FLOOR


def test_a_deadly_candidate_still_falls_when_contradicted(taxonomy):
    """Protected is not frozen. Above the floor it must still respond."""
    described = with_states(
        taxonomy,
        {
            DEATH_CAP: {"gill_colour": ("White",)},
            FIELD_MUSHROOM: {"gill_colour": ("Pink",)},
        },
    )
    ranked = [(DEATH_CAP, 0.6), (FIELD_MUSHROOM, 0.4)]
    updated = dict(reweight(ranked, "gill_colour", "Pink", described))
    assert updated[DEATH_CAP] < 0.6


def test_coverage_reports_what_has_been_described(taxonomy):
    described = with_states(
        taxonomy,
        {
            DEATH_CAP: {"gill_colour": ("White",), "ring": ("Firm skirt-like ring",)},
            FIELD_MUSHROOM: {"gill_colour": ("Pink",)},
        },
    )
    coverage = described_coverage(described)
    assert coverage["described"] == 2
    assert coverage["state_entries"] == 3
    assert 0 < coverage["fraction"] < 1
