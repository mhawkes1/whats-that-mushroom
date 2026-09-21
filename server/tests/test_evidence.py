"""The answer-weighting mechanism.

Most of these build a taxonomy with states filled in by hand rather than
using the committed ones, so they test the update rather than the data. The
two are separate failures and conflating them makes a wrong table look like a
wrong mechanism.

The tests over the real, committed table are at the bottom.
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


def test_an_undescribed_character_leaves_the_ranking_exactly_as_it_was(taxonomy):
    """No description means no evidence, so nothing may move.

    Most of the taxonomy is still undescribed, and for those characters the
    update must be an exact no-op. A ranking that drifted slightly would be
    worse than one that does not move, because it would look like it worked.
    """
    ranked = [(CHANTERELLE, 0.5), (FIELD_MUSHROOM, 0.3), ("morchella-esculenta", 0.2)]
    assert reweight(ranked, "gill_colour", "White", taxonomy) == ranked


def test_every_deadly_species_is_described(taxonomy):
    """The species that can kill are the ones an answer most needs to move."""
    deadly = taxonomy.deadly_keys()
    undescribed = sorted(k for k in deadly if not taxonomy[k].character_states)
    assert undescribed == [], f"deadly species with no states: {undescribed}"


def test_most_of_the_taxonomy_is_still_undescribed(taxonomy):
    """A guard on the claim the docs make about coverage.

    If someone describes the rest, this fails and the docs saying only the
    deadly species are filled in need updating with it.
    """
    coverage = described_coverage(taxonomy)
    assert coverage["described"] == len(taxonomy.deadly_keys())
    assert 0.0 < coverage["fraction"] < 0.5


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


def test_coverage_counts_species_and_entries(taxonomy):
    baseline = described_coverage(taxonomy)
    described = with_states(
        taxonomy,
        {
            CHANTERELLE: {"gill_type": ("Blunt forking ridges",)},
            FIELD_MUSHROOM: {"gill_colour": ("Pink",)},
        },
    )
    coverage = described_coverage(described)
    assert coverage["described"] == baseline["described"] + 2
    assert coverage["state_entries"] == baseline["state_entries"] + 2
    assert 0 < coverage["fraction"] < 1


# --- Over the real, committed table ------------------------------------------
#
# Everything above tests the update with hand-built data. These test the data
# that actually ships, on the confusions it exists to handle.


def test_destroying_the_evidence_does_not_clear_an_amanita(taxonomy):
    """"I cut it off" says nothing about whether there was a volva.

    It is the single most important case in the file. Cutting the stem at
    ground level is how an Amanita is missed in the field -- the character's
    own safety note says so -- and treating it as a state would let the most
    common field mistake push the deadliest genus down the list.
    """
    ranked = [(DEATH_CAP, 0.5), (FIELD_MUSHROOM, 0.5)]
    assert reweight(ranked, "volva", "I cut it off", taxonomy) == ranked

    evidence = likelihood_for(taxonomy[DEATH_CAP], "volva", "I cut it off")
    assert evidence.verdict == "unobserved"
    assert evidence.likelihood == 1.0


def test_not_being_able_to_tell_is_not_evidence_either(taxonomy):
    """The same, for the webcap's cortina."""
    webcap = "cortinarius-rubellus"
    ranked = [(webcap, 0.5), (CHANTERELLE, 0.5)]
    assert reweight(ranked, "cortina", "Can't tell", taxonomy) == ranked


def test_seeing_a_volva_keeps_the_death_cap_in_play(taxonomy):
    """A consistent answer must never push a deadly candidate down."""
    ranked = [(FIELD_MUSHROOM, 0.7), (DEATH_CAP, 0.3)]
    updated = dict(reweight(ranked, "volva", "Clear cup or sac", taxonomy))
    assert updated[DEATH_CAP] >= 0.3


def test_a_rust_spore_print_does_not_clear_the_funeral_bell(taxonomy):
    """The confusion the notes call the most dangerous for experienced foragers.

    Galerina marginata and Kuehneromyces mutabilis share a rust-brown spore
    print and dead wood. An answer consistent with both must not separate
    them -- if anything could, this pair would not be dangerous.
    """
    ranked = [("galerina-marginata", 0.5), ("kuehneromyces-mutabilis", 0.5)]
    updated = dict(reweight(ranked, "spore_print_colour", "Rust or cinnamon brown", taxonomy))
    assert updated["galerina-marginata"] >= 0.5


def test_no_ring_does_not_clear_the_funeral_bell(taxonomy):
    """Galerina's ring is fragile and frequently absent by the time it is found.

    All four ring states are listed for it on purpose, so that seeing no ring
    cannot be used to rule it out.
    """
    ranked = [("galerina-marginata", 0.5), ("kuehneromyces-mutabilis", 0.5)]
    updated = dict(reweight(ranked, "ring", "No ring", taxonomy))
    assert updated["galerina-marginata"] >= 0.5


def test_a_pale_cap_does_not_clear_the_death_cap(taxonomy):
    """Cap colour is listed generously because death caps are not reliably olive.

    Pinning cap_colour to olive alone would let a pale specimen -- which is
    exactly what gets mistaken for a field mushroom -- be dismissed.
    """
    for colour in ("White or cream", "Yellow", "Brown", "Grey", "Olive or greenish"):
        ranked = [(FIELD_MUSHROOM, 0.5), (DEATH_CAP, 0.5)]
        updated = dict(reweight(ranked, "cap_colour", colour, taxonomy))
        assert updated[DEATH_CAP] >= 0.5, f"a {colour.lower()} cap dismissed the death cap"


def test_every_committed_state_is_a_real_answer_option(taxonomy):
    """A state no answer can equal would be a table entry that never fires."""
    from app.characters import CHARACTERS

    for species in taxonomy.species.values():
        for character_key, states in species.character_states.items():
            character = CHARACTERS[character_key]
            for state in states:
                assert state in character.options, f"{species.key}/{character_key}: {state!r}"


def test_no_committed_state_is_an_unobservable_answer(taxonomy):
    """A species cannot "be" an answer that means the user failed to look."""
    from app.evidence import is_uninformative

    for species in taxonomy.species.values():
        for character_key, states in species.character_states.items():
            for state in states:
                assert not is_uninformative(character_key, state), (
                    f"{species.key}/{character_key}: {state!r} is a non-observation"
                )
