"""Tests for the risk model.

These encode the project's central safety claim: that the model treats a
potentially lethal confusion as categorically worse than a harmless one.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fungi_ml.taxonomy import Taxonomy, Toxicity  # noqa: E402

SEED = Path(__file__).resolve().parents[2] / "data" / "taxonomy.seed.json"


@pytest.fixture(scope="module")
def taxonomy() -> Taxonomy:
    return Taxonomy.load(SEED)


def test_seed_loads_and_is_populated(taxonomy):
    assert len(taxonomy.species) >= 50
    assert "amanita-phalloides" in taxonomy


def test_every_lookalike_reference_resolves(taxonomy):
    dangling = {
        (key, la)
        for key, sp in taxonomy.species.items()
        for la in sp.lookalikes
        if la not in taxonomy
    }
    assert not dangling, f"lookalikes referencing unknown species: {sorted(dangling)}"


def test_lookalikes_are_never_self_referential(taxonomy):
    assert not [k for k, sp in taxonomy.species.items() if k in sp.lookalikes]


def test_known_deadly_species_are_flagged(taxonomy):
    deadly = taxonomy.deadly_keys()
    for key in ("amanita-phalloides", "amanita-virosa", "galerina-marginata",
                "cortinarius-rubellus", "gyromitra-esculenta"):
        assert key in deadly, f"{key} must be classified DEADLY"


def test_the_classic_fatal_confusions_are_captured(taxonomy):
    pairs = taxonomy.dangerous_pairs()

    def paired(a, b):
        return tuple(sorted((a, b))) in pairs

    # Death cap mistaken for a field mushroom -- the textbook fatality.
    assert paired("amanita-phalloides", "agaricus-campestris")
    # Destroying angel mistaken for a horse mushroom.
    assert paired("amanita-virosa", "agaricus-arvensis")
    # Funeral bell mistaken for sheathed woodtuft -- kills experienced foragers.
    assert paired("galerina-marginata", "kuehneromyces-mutabilis")
    # False morel mistaken for a true morel.
    assert paired("gyromitra-esculenta", "morchella-esculenta")
    # Fool's funnel mistaken for a fairy ring champignon.
    assert paired("clitocybe-rivulosa", "marasmius-oreades")


def test_deadly_pairs_never_contain_two_deadly_species(taxonomy):
    for a, b in taxonomy.dangerous_pairs():
        tox = {taxonomy[a].toxicity, taxonomy[b].toxicity}
        assert Toxicity.DEADLY in tox, "a dangerous pair must involve a deadly species"
        assert tox != {Toxicity.DEADLY}, (
            f"{a}/{b}: confusing two deadly species is not a safety event"
        )


def test_risk_is_asymmetric_in_the_direction_that_matters(taxonomy):
    # Truth is deadly, we called it benign: catastrophic.
    fatal = taxonomy.risk_weight("amanita-phalloides", "agaricus-campestris")
    # Truth is benign, we called it deadly: merely a wasted meal.
    cautious = taxonomy.risk_weight("agaricus-campestris", "amanita-phalloides")

    assert fatal >= 1000.0, "under-calling a death cap must carry extreme cost"
    assert cautious <= 5.0, "over-caution must stay cheap"
    assert fatal > cautious * 100, (
        f"asymmetry too weak: {fatal} vs {cautious} -- the model would learn "
        "to trade a fatality against a few false alarms"
    )


def test_correct_prediction_is_free(taxonomy):
    for key in list(taxonomy.species)[:10]:
        assert taxonomy.risk_weight(key, key) == 0.0


def test_within_genus_confusion_is_cheaper_than_cross_genus(taxonomy):
    same_genus = taxonomy.risk_weight("russula-cyanoxantha", "russula-ochroleuca")
    cross_genus = taxonomy.risk_weight("russula-cyanoxantha", "hydnum-repandum")
    assert same_genus < cross_genus


def test_genus_containing_a_deadly_species_taints_its_members(taxonomy):
    # Anything in Amanita is suspect even if not itself lethal, because a
    # user cannot safely reason "it's an Amanita, but a harmless one".
    pairs = taxonomy.dangerous_pairs()
    assert tuple(sorted(("amanita-phalloides", "amanita-muscaria"))) in pairs


def test_unknown_toxicity_is_not_treated_as_safe(taxonomy):
    # UNKNOWN must never sort below TOXIC in a way that makes it look benign.
    assert Toxicity.UNKNOWN < Toxicity.TOXIC
    # ...which is precisely why the safety layer must special-case it.
    # Guard that no seed species silently relies on UNKNOWN.
    unknown = [k for k, s in taxonomy.species.items() if s.toxicity is Toxicity.UNKNOWN]
    assert not unknown, f"seed species with unassessed toxicity: {unknown}"


def test_deadly_species_all_declare_diagnostic_characters(taxonomy):
    """The interrogation engine needs these to know what to ask for."""
    missing = [
        k for k in taxonomy.deadly_keys() if not taxonomy[k].diagnostic_characters
    ]
    assert not missing, f"deadly species with no diagnostic characters: {missing}"


def test_species_stays_hashable_with_character_states():
    """`character_states` is a dict on a frozen dataclass.

    A frozen dataclass hashes on its fields, so an unguarded dict field makes
    every Species unhashable. Nothing hashes one today, which is exactly why
    this needs a test: the breakage would surface later, far from the cause,
    in whatever code first put a species in a set.
    """
    from dataclasses import replace

    from fungi_ml.taxonomy import Species, Toxicity

    plain = Species(key="x", scientific_name="Xus xus", genus="Xus")
    described = replace(plain, character_states={"gill_colour": ("White",)})

    assert len({plain, described}) >= 1  # hashable at all
    assert hash(replace(described)) == hash(described)
    # Equality still distinguishes them, even though the hash ignores states.
    assert described != replace(plain, character_states={"gill_colour": ("Pink",)})
    assert Toxicity.UNKNOWN is plain.toxicity
