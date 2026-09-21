"""Tests for the question-selection engine.

The behaviour that matters: when a lethal ambiguity is present, the engine
must ask for the character that resolves it, ahead of any cheaper question.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from app.characters import CHARACTERS, order_by_effort  # noqa: E402
from app.interrogation import InterrogationEngine, entropy  # noqa: E402
from app.taxonomy_service import TaxonomyService  # noqa: E402

SEED = ROOT / "data" / "taxonomy.seed.json"


@pytest.fixture(scope="module")
def taxonomy():
    return TaxonomyService.load(SEED)


@pytest.fixture(scope="module")
def engine(taxonomy):
    return InterrogationEngine(taxonomy)


def test_entropy_is_zero_when_certain():
    assert entropy([1.0]) == 0.0
    assert entropy([1.0, 0.0, 0.0]) == 0.0


def test_entropy_is_maximal_when_uniform():
    assert entropy([0.25] * 4) == pytest.approx(2.0)


def test_asks_for_the_volva_when_a_death_cap_is_in_play(engine):
    """The stem base is the check that separates Amanita from Agaricus.
    A user who never digs up the base is the user who dies."""
    ranked = [("agaricus-campestris", 0.55), ("amanita-phalloides", 0.45)]
    questions = engine.next_questions(ranked)

    assert questions, "must ask something when a lethal pair is unresolved"
    keys = [q.character.key for q in questions]
    assert "volva" in keys, f"expected volva to be requested, got {keys}"

    volva = next(q for q in questions if q.character.key == "volva")
    assert volva.resolves_dangerous_pair
    assert "kill" in volva.rationale.lower()
    assert volva.character.safety_note, "safety note must be surfaced for lethal pairs"


def test_safety_question_outranks_a_cheaper_one(engine):
    ranked = [("agaricus-campestris", 0.55), ("amanita-phalloides", 0.45)]
    questions = engine.next_questions(ranked, limit=3)
    assert questions[0].resolves_dangerous_pair, (
        f"top question should resolve the lethal pair, got {questions[0].character.key}"
    )


def test_does_not_ask_about_characters_the_candidates_share(engine):
    """The funeral bell and the sheathed woodtuft both have a rust-brown spore
    print and both grow on dead wood.

    This test used to assert the opposite -- that the engine asks for a spore
    print here -- which it did, because it scored questions from the fact that
    both species declared the character as diagnostic without knowing that
    both show the same state. Sending someone away for hours to make a spore
    print that cannot separate the two candidates is worse than asking
    nothing, and this was the confusion the taxonomy itself calls the most
    dangerous for experienced foragers.

    What separates them in the recorded data is the stem surface: scaly on the
    woodtuft, fibrous or smooth on the funeral bell.
    """
    ranked = [("kuehneromyces-mutabilis", 0.52), ("galerina-marginata", 0.48)]
    keys = [q.character.key for q in engine.next_questions(ranked, limit=4)]

    assert "stipe_surface" in keys
    assert "spore_print_colour" not in keys
    assert "substrate" not in keys


def test_does_not_repeat_an_answered_question(engine):
    ranked = [("agaricus-campestris", 0.55), ("amanita-phalloides", 0.45)]
    keys = [
        q.character.key
        for q in engine.next_questions(ranked, already_answered={"volva"})
    ]
    assert "volva" not in keys


def test_no_questions_when_only_one_candidate(engine):
    assert engine.next_questions([("hydnum-repandum", 1.0)]) == []


def test_questions_are_capped_by_limit(engine):
    ranked = [("russula-cyanoxantha", 0.3), ("russula-ochroleuca", 0.3),
              ("russula-emetica", 0.2), ("lepista-nuda", 0.2)]
    assert len(engine.next_questions(ranked, limit=2)) <= 2


def test_every_question_is_answerable_by_a_non_expert(engine):
    """Each question must carry instructions and either options or a photo ask."""
    ranked = [("agaricus-campestris", 0.4), ("amanita-phalloides", 0.3),
              ("agaricus-xanthodermus", 0.3)]
    for q in engine.next_questions(ranked, limit=5):
        payload = q.to_dict()
        assert payload["prompt"], f"{payload['key']} has no prompt"
        assert payload["how"], f"{payload['key']} has no instructions"
        assert payload["options"] or payload["requires_photo"], (
            f"{payload['key']} gives the user no way to answer"
        )


def test_effort_ordering_puts_instant_checks_first():
    ordered = order_by_effort(["spore_print_colour", "cap_colour", "volva"])
    assert ordered[0] == "cap_colour", "instant checks must come first"
    assert ordered[-1] == "spore_print_colour", "multi-hour checks must come last"


def test_taste_is_never_requested_while_a_deadly_species_is_a_candidate(engine):
    """Amatoxins are tasteless. A taste test cannot detect them and asking
    for one would imply otherwise."""
    ranked = [("amanita-phalloides", 0.5), ("russula-cyanoxantha", 0.5)]
    keys = [q.character.key for q in engine.next_questions(ranked, limit=6)]
    assert "taste" not in keys, "must not send a user to taste a possible death cap"


def test_rationale_is_always_populated(engine):
    ranked = [("morchella-esculenta", 0.5), ("gyromitra-esculenta", 0.5)]
    for q in engine.next_questions(ranked, limit=4):
        assert q.rationale.strip(), f"{q.character.key} has an empty rationale"


def test_apply_answer_renormalises_to_one(engine):
    ranked = [("amanita-phalloides", 0.5), ("agaricus-campestris", 0.5)]
    updated = engine.apply_answer(ranked, "volva", "Clear cup or sac")
    assert sum(s for _, s in updated) == pytest.approx(1.0)
    assert updated == sorted(updated, key=lambda kv: -kv[1])


def test_apply_answer_never_zeroes_a_candidate(engine):
    """A user's field observation is a noisy sensor. No single answer may
    eliminate a candidate outright -- especially not a deadly one."""
    ranked = [("amanita-phalloides", 0.4), ("agaricus-campestris", 0.6)]
    updated = dict(engine.apply_answer(ranked, "volva", "Neither"))
    assert updated["amanita-phalloides"] > 0.0, (
        "a single answer must never rule out a deadly candidate entirely"
    )


def test_taste_suppression_is_a_rule_not_a_coincidence(engine):
    """Force taste to the top of the ranking and confirm it is still withheld.

    The earlier test passed because taste happened to rank low. This one
    makes the deadly candidate dominant among species that declare `taste`
    as diagnostic, so only an explicit rule can keep it out.
    """
    ranked = [
        ("russula-cyanoxantha", 0.45),  # declares `taste`
        ("russula-emetica", 0.35),      # declares `taste`
        ("amanita-phalloides", 0.20),   # deadly, in play
    ]
    keys = [q.character.key for q in engine.next_questions(ranked, limit=8)]
    assert "taste" not in keys, (
        "taste must be suppressed whenever a deadly species holds real mass"
    )


def test_taste_is_permitted_when_nothing_deadly_is_in_play(engine):
    """The rule must not be so broad that it blocks a legitimate question."""
    ranked = [("russula-cyanoxantha", 0.50), ("russula-emetica", 0.50)]
    questions = engine.next_questions(ranked, limit=8)
    keys = [q.character.key for q in questions]
    # Sanity: these two are genuinely separated by taste (mild vs acrid).
    assert "taste" in keys or not questions, (
        f"taste should be available among harmless Russula candidates, got {keys}"
    )


def test_trace_deadly_mass_still_suppresses_taste(engine):
    ranked = [("russula-cyanoxantha", 0.94), ("amanita-phalloides", 0.06)]
    keys = [q.character.key for q in engine.next_questions(ranked, limit=8)]
    assert "taste" not in keys


def test_never_leads_with_a_character_both_candidates_share(engine, taxonomy):
    """The general form of the funeral-bell bug, over every lethal pair.

    For any two candidates that differ somewhere, the question the engine puts
    first must be one whose recorded states actually differ between them.
    Leading with a shared character sends the user to check something that
    cannot change the answer, and on these pairs that is a wasted trip made
    while a deadly species is on the table.
    """
    for a, b in sorted(taxonomy.dangerous_pairs()):
        states_a, states_b = taxonomy[a].character_states, taxonomy[b].character_states
        differing = {
            c
            for c in set(states_a) | set(states_b)
            if states_a.get(c) and states_b.get(c)
            and set(states_a[c]) != set(states_b[c])
        }
        if not differing:
            continue  # nothing can separate them; covered elsewhere

        questions = engine.next_questions([(a, 0.5), (b, 0.5)], limit=1)
        if not questions:
            continue
        top = questions[0].character.key

        shared = (
            states_a.get(top)
            and states_b.get(top)
            and set(states_a[top]) == set(states_b[top])
        )
        assert not shared, (
            f"{a} vs {b}: leads with {top}, which both show identically, "
            f"while {sorted(differing)} would discriminate"
        )


def test_gain_is_zero_when_no_answer_could_move_anything(engine, taxonomy):
    """A character every candidate answers the same way carries no information."""
    from dataclasses import replace

    from app.taxonomy_service import TaxonomyService

    same = TaxonomyService(
        species={
            **taxonomy.species,
            "agaricus-campestris": replace(
                taxonomy["agaricus-campestris"],
                character_states={"spore_print_colour": ("White or cream",)},
            ),
            "marasmius-oreades": replace(
                taxonomy["marasmius-oreades"],
                character_states={"spore_print_colour": ("White or cream",)},
            ),
        }
    )
    from app.interrogation import InterrogationEngine

    ranked = [("agaricus-campestris", 0.5), ("marasmius-oreades", 0.5)]
    gain = InterrogationEngine(same).expected_gain(ranked, "spore_print_colour")
    assert gain == pytest.approx(0.0, abs=1e-9)


def test_the_reported_gain_is_bits_not_a_priority_score(engine):
    """`expected_information_gain` must mean what it says.

    It used to carry the sort key -- gain plus a safety bonus minus an effort
    discount -- which is how a question with almost no information could be
    published to the client as though it had a great deal.
    """
    ranked = [("amanita-phalloides", 0.5), ("agaricus-campestris", 0.5)]
    for question in engine.next_questions(ranked, limit=3):
        # One bit is the most that can be removed from a two-way split.
        assert 0.0 <= question.expected_information_gain <= 1.0
        assert question.to_dict()["expected_information_gain"] == round(
            question.expected_information_gain, 4
        )
        if question.resolves_dangerous_pair:
            # The bonus lives on `priority`, and only there.
            assert question.priority > question.expected_information_gain
