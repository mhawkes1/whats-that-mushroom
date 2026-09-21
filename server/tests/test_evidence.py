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

# Every species now carries some states, but only for the characters it
# declares as diagnostic. These three describe nothing about gills, so an
# answer about gill colour still takes the undescribed path through them.
NO_GILL_STATES_A = "boletus-edulis"
NO_GILL_STATES_B = "hydnum-repandum"
NO_GILL_STATES_C = "sparassis-crispa"


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
    ranked = [(NO_GILL_STATES_A, 0.5), (NO_GILL_STATES_B, 0.3), (NO_GILL_STATES_C, 0.2)]
    assert reweight(ranked, "gill_colour", "White", taxonomy) == ranked


def test_every_deadly_species_is_described(taxonomy):
    """The species that can kill are the ones an answer most needs to move."""
    deadly = taxonomy.deadly_keys()
    undescribed = sorted(k for k in deadly if not taxonomy[k].character_states)
    assert undescribed == [], f"deadly species with no states: {undescribed}"


def test_every_species_in_a_lethal_pair_is_described(taxonomy):
    """Both halves of every dangerous pair carry states.

    The deadly half alone is not enough. With only the deadly species
    described, evidence could move mass away from a lethal candidate but
    never back toward one, because nothing could contradict the safe
    lookalike sitting opposite it.
    """
    in_a_lethal_pair = {key for pair in taxonomy.dangerous_pairs() for key in pair}
    undescribed = sorted(
        k for k in in_a_lethal_pair if not taxonomy[k].character_states
    )
    assert undescribed == [], f"a lethal pair has an undescribed half: {undescribed}"


def test_every_species_in_the_taxonomy_is_described(taxonomy):
    """The table is complete: every species carries states for its own characters.

    Complete is not the same as reviewed. Every entry was compiled from the
    taxonomy's own notes and still needs field-character sign-off; `/health`
    reports `taxonomy_reviewed: false` and this test says nothing about that.
    """
    coverage = described_coverage(taxonomy)
    assert coverage["described"] == len(taxonomy.species)
    assert coverage["fraction"] == 1.0

    undescribed = sorted(k for k, s in taxonomy.species.items() if not s.character_states)
    assert undescribed == []


def test_a_species_is_only_described_for_characters_it_declares(taxonomy):
    """States are recorded against diagnostic characters, not arbitrary ones.

    A state on a character the species does not declare would never be asked
    about in the first place, so it could only ever fire by accident.
    """
    for species in taxonomy.species.values():
        extra = set(species.character_states) - set(species.diagnostic_characters)
        assert extra == set(), f"{species.key} describes undeclared {sorted(extra)}"


# --- The likelihood, per species ---------------------------------------------


def test_an_undescribed_species_is_untouched(taxonomy):
    evidence = likelihood_for(taxonomy[NO_GILL_STATES_A], "gill_colour", "White")
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
    """Every species is described, so this clears two and checks the fall."""
    baseline = described_coverage(taxonomy)
    lost = sum(
        len(taxonomy[key].character_states)
        for key in (NO_GILL_STATES_A, NO_GILL_STATES_B)
    )
    assert lost > 0, "fixture species should already carry states"

    stripped = with_states(taxonomy, {NO_GILL_STATES_A: {}, NO_GILL_STATES_B: {}})
    coverage = described_coverage(stripped)

    assert coverage["described"] == baseline["described"] - 2
    assert coverage["state_entries"] == baseline["state_entries"] - lost
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


# --- The safe half of a lethal pair ------------------------------------------
#
# Describing only the deadly species was not enough. With the safe lookalike
# undescribed, nothing a user reported could contradict it, so evidence could
# move mass away from a lethal candidate but never back toward one.


def test_describing_an_amanita_raises_the_death_cap_over_the_field_mushroom(taxonomy):
    """The case the whole project exists for.

    A user who has picked a death cap and believes it is a field mushroom
    reports what they see. Each observation is consistent with the death cap
    and contradicts the field mushroom, so the ranking has to move toward the
    lethal candidate, not away from it.
    """
    ranked = [(FIELD_MUSHROOM, 0.70), (DEATH_CAP, 0.30)]
    for character, answer in [
        ("volva", "Clear cup or sac"),
        ("spore_print_colour", "White or cream"),
        ("gill_colour", "White"),
    ]:
        ranked = reweight(ranked, character, answer, taxonomy)

    updated = dict(ranked)
    assert updated[DEATH_CAP] > updated[FIELD_MUSHROOM]
    assert updated[DEATH_CAP] > 0.9, "three consistent observations should be decisive"


def test_that_movement_depends_on_the_safe_half_being_described(taxonomy):
    """Pins why Tier 2 mattered, so nobody strips it as redundant.

    With only the deadly species described the same three answers move the
    death cap exactly nowhere, because nothing contradicts the field mushroom.
    """
    from dataclasses import replace

    deadly = taxonomy.deadly_keys()
    tier_one_only = TaxonomyService(
        species={
            key: (s if key in deadly else replace(s, character_states={}))
            for key, s in taxonomy.species.items()
        }
    )

    answers = [
        ("volva", "Clear cup or sac"),
        ("spore_print_colour", "White or cream"),
        ("gill_colour", "White"),
    ]
    ranked = [(FIELD_MUSHROOM, 0.70), (DEATH_CAP, 0.30)]
    for character, answer in answers:
        ranked = reweight(ranked, character, answer, tier_one_only)

    assert dict(ranked)[DEATH_CAP] == pytest.approx(0.30), (
        "with the safe half undescribed this evidence is inert"
    )


def test_decurrent_crowded_gills_move_away_from_the_fairy_ring_champignon(taxonomy):
    """Both deadly Clitocybe species share lawns and fairy rings with it.

    The separation is gill attachment and spacing: crowded and running down
    the stem for the Clitocybe, well spaced and free for Marasmius.
    """
    ranked = [("marasmius-oreades", 0.7), ("clitocybe-rivulosa", 0.3)]
    for character, answer in [
        ("gill_attachment", "Running down the stem"),
        ("gill_spacing", "Crowded"),
    ]:
        ranked = reweight(ranked, character, answer, taxonomy)

    updated = dict(ranked)
    assert updated["clitocybe-rivulosa"] > updated["marasmius-oreades"]


def test_a_chambered_interior_moves_away_from_the_true_morel(taxonomy):
    """A true morel is hollow from tip to base; the false morel is chambered."""
    ranked = [("morchella-esculenta", 0.7), ("gyromitra-esculenta", 0.3)]
    for character, answer in [
        ("cap_surface", "Brain-like or folded"),
        ("interior_structure", "Chambered or cottony"),
    ]:
        ranked = reweight(ranked, character, answer, taxonomy)

    updated = dict(ranked)
    assert updated["gyromitra-esculenta"] > updated["morchella-esculenta"]


def test_a_volva_alone_does_not_settle_anything(taxonomy):
    """Volvopluteus is in the label space precisely to break that shortcut.

    It has a volva and no ring, so "there is a volva" is consistent with both
    it and the death cap, and must not separate them.
    """
    ranked = [(DEATH_CAP, 0.5), ("volvopluteus-gloiocephalus", 0.5)]
    updated = dict(reweight(ranked, "volva", "Clear cup or sac", taxonomy))
    assert updated[DEATH_CAP] == pytest.approx(0.5)
    assert updated["volvopluteus-gloiocephalus"] == pytest.approx(0.5)


def test_a_pink_spore_print_is_what_separates_volvopluteus(taxonomy):
    """The check that actually works, once the user has been sent to make it."""
    ranked = [(DEATH_CAP, 0.5), ("volvopluteus-gloiocephalus", 0.5)]
    updated = dict(reweight(ranked, "spore_print_colour", "Pink", taxonomy))
    assert updated["volvopluteus-gloiocephalus"] > updated[DEATH_CAP]


# --- Species added to close the gaps docs/REVIEW.md named --------------------


def test_the_gaps_review_named_are_now_in_the_label_space(taxonomy):
    """A species the model has never seen cannot be flagged as dangerous.

    REVIEW.md items 10-12: the amatoxin-containing small Lepiota, the Panther
    Cap, and the second orellanine webcap. Absent from the label space, each
    would have been forced into the nearest class the model knows -- for the
    Lepiota, a lawn mushroom.
    """
    for key in (
        "lepiota-brunneoincarnata",
        "amanita-pantherina",
        "cortinarius-orellanus",
    ):
        assert key in taxonomy.species, key
        assert taxonomy[key].character_states, f"{key} was added but not described"


def test_the_deadly_dapperling_is_a_lethal_pair_with_the_lawn_mushrooms(taxonomy):
    """It fruits in grass, which is where people gather small field mushrooms."""
    pairs = taxonomy.dangerous_pairs()
    partners = {
        (b if a == "lepiota-brunneoincarnata" else a)
        for a, b in pairs
        if "lepiota-brunneoincarnata" in (a, b)
    }
    assert "marasmius-oreades" in partners
    assert taxonomy["lepiota-brunneoincarnata"].toxicity is Toxicity.DEADLY


def test_a_spore_print_does_not_separate_the_dapperling_from_the_champignon(taxonomy):
    """Both have a white spore print, so the test cannot tell them apart.

    And when an answer contradicts both -- a rust print fits neither -- the
    deadly one falls more slowly and therefore ends up ahead. That is the
    intended asymmetry: an observation that rules out everything should leave
    you more worried, not less.
    """
    ranked = [("marasmius-oreades", 0.5), ("lepiota-brunneoincarnata", 0.5)]

    same = dict(reweight(ranked, "spore_print_colour", "White or cream", taxonomy))
    assert same["lepiota-brunneoincarnata"] == pytest.approx(0.5)

    neither = dict(reweight(ranked, "spore_print_colour", "Rust or cinnamon brown", taxonomy))
    assert neither["lepiota-brunneoincarnata"] > neither["marasmius-oreades"]


def test_flesh_that_does_not_redden_moves_toward_the_panther_cap(taxonomy):
    """The Blusher reddens where cut; the Panther Cap does not.

    That single reaction is the separation between a mushroom people eat and
    one that hospitalises them.
    """
    ranked = [("amanita-rubescens", 0.5), ("amanita-pantherina", 0.5)]
    updated = dict(reweight(ranked, "bruising_reaction", "No change", taxonomy))
    assert updated["amanita-pantherina"] > updated["amanita-rubescens"]


def test_broadleaf_woodland_separates_the_two_orellanine_webcaps(taxonomy):
    """C. orellanus is with oak and beech; C. rubellus is with conifers.

    Both cause the same delayed kidney failure, so this does not make either
    safe -- it decides which deadly species is in front of you.
    """
    ranked = [("cortinarius-rubellus", 0.5), ("cortinarius-orellanus", 0.5)]
    updated = dict(reweight(ranked, "habitat", "Oak", taxonomy))
    assert updated["cortinarius-orellanus"] > updated["cortinarius-rubellus"]

    conifer = dict(reweight(ranked, "habitat", "Pine or spruce", taxonomy))
    assert conifer["cortinarius-rubellus"] > conifer["cortinarius-orellanus"]


# --- The two answer options added so a character could be recorded -----------


def test_an_apricot_smell_can_now_be_recorded_and_used(taxonomy):
    """Until this option existed the chanterelle's best character was unsayable.

    Note what it does and does not do. A consistent answer never boosts, so
    this cannot promote the chanterelle on its own; what it can do is
    contradict a species whose smell is described as something else.
    """
    from app.evidence import likelihood_for as lf

    assert lf(taxonomy[CHANTERELLE], "smell", "Apricot or fruity").verdict == "consistent"

    ranked = [("calocybe-gambosa", 0.5), (CHANTERELLE, 0.5)]
    updated = dict(reweight(ranked, "smell", "Apricot or fruity", taxonomy))
    assert updated[CHANTERELLE] > updated["calocybe-gambosa"]


def test_green_staining_latex_moves_toward_the_saffron_milkcap(taxonomy):
    ranked = [("cortinarius-rubellus", 0.5), ("lactarius-deliciosus", 0.5)]
    updated = dict(reweight(ranked, "bruising_reaction", "Green", taxonomy))
    assert updated["lactarius-deliciosus"] >= 0.5


def test_a_species_that_hospitalises_is_dismissed_more_slowly_than_a_harmless_one(taxonomy):
    """The middle tier, mirroring the risk matrix's 1 / 100 / 1000."""
    from app.evidence import DEADLY_INCONSISTENT, INCONSISTENT, SERIOUS_INCONSISTENT

    assert INCONSISTENT < SERIOUS_INCONSISTENT < DEADLY_INCONSISTENT

    serious = likelihood_for(taxonomy["entoloma-sinuatum"], "spore_print_colour", "Black")
    ordinary = likelihood_for(taxonomy["clitopilus-prunulus"], "spore_print_colour", "Black")
    assert taxonomy["entoloma-sinuatum"].toxicity is Toxicity.SERIOUS
    assert serious.likelihood > ordinary.likelihood
