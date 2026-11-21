"""How much help a character gives, measured against what it can cost.

In this engine a consistent answer never boosts -- evidence eliminates.
So a user who picks the wrong option does not merely fail to help: they
contradict every species that does not list it, and if one of those is
deadly, a guess has moved mass away from something lethal. The project
already declined `Moderately spaced` as a gill-spacing option on exactly
this reasoning.

Which makes the amount of guidance a character carries a safety property
rather than a presentation one, and it was unevenly distributed: `volva`
gated two deadly species with a paragraph and a safety note, while `ring`
gated five with one line and nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from app.characters import CHARACTERS  # noqa: E402
from app.taxonomy_service import TaxonomyService, Toxicity  # noqa: E402

#: Characters that gate a deadly species and do NOT yet carry a safety
#: note. Named rather than excluded by lowering the bar, because a guard
#: set below the line that matters reports on somewhere nobody is
#: standing -- the `GUARDED_DEPTH` lesson.
#:
#: Each gates two deadly species. `cap_colour` is the one to do next:
#: colour is the least reliable character in the catalogue, it shifts with
#: age and wet, and the death cap depends on it.
AWAITING_GUIDANCE = {"gill_type", "cap_colour", "size"}


@pytest.fixture(scope="module")
def deadly_gated() -> dict[str, int]:
    taxonomy = TaxonomyService.load(ROOT / "data" / "taxonomy.seed.json")
    deadly = [s for s in taxonomy.species.values()
              if s.toxicity is Toxicity.DEADLY]
    return {
        key: sum(1 for s in deadly if key in (s.character_states or {}))
        for key in CHARACTERS
    }


def test_a_character_gating_a_deadly_species_carries_a_safety_note(deadly_gated):
    """The note is what tells a user why this one matters, and it is also
    what makes `QuestionCard` render the question as critical. On the
    highest-stakes characters that mechanism was simply unused."""
    missing = {
        key for key, n in deadly_gated.items()
        if n >= 2 and not CHARACTERS[key].safety_note
    }
    assert missing <= AWAITING_GUIDANCE, (
        f"{sorted(missing - AWAITING_GUIDANCE)} gate a deadly species and "
        f"carry no safety note. Either write one or add the key to "
        f"AWAITING_GUIDANCE with a reason."
    )


def test_the_backlog_does_not_silently_clear_itself(deadly_gated):
    """The failure `DECLARED_BUT_UNREAD` was written to catch, in a new
    place: an allowlist that stops naming anything real has stopped
    guarding, and reads as though the work were done."""
    stale = {
        key for key in AWAITING_GUIDANCE
        if CHARACTERS[key].safety_note or deadly_gated.get(key, 0) < 2
    }
    assert not stale, (
        f"{sorted(stale)} no longer need to be in AWAITING_GUIDANCE. Remove "
        f"them, so the list keeps meaning what it says."
    )


def test_guidance_scales_with_what_a_wrong_answer_costs(deadly_gated):
    """`how` is the text that stops a guess. A character gating five
    deadly species had fifty-three characters of it -- "Photograph the cap
    from directly above in even light" -- which says where to point a
    camera and nothing about how to judge what comes back."""
    thin = {
        key: len(CHARACTERS[key].how)
        for key, n in deadly_gated.items()
        if n >= 5 and len(CHARACTERS[key].how) < 150
    }
    assert not thin, (
        f"{thin} gate five or more deadly species on less than 150 "
        f"characters of guidance"
    )


def test_every_character_offers_a_way_out_of_guessing(deadly_gated):
    """Not an option in the list -- `QuestionCard` carries "I can't tell /
    skip this" on every question, and a second route to the same thing in
    the options would be duplication. This asserts the one route stays.

    It matters most exactly where the new safety notes point at it: three
    of them end by telling the user to skip rather than guess, which is
    only advice if the control is there to take.
    """
    card = (ROOT / "app" / "src" / "components" / "QuestionCard.tsx").read_text(
        encoding="utf-8"
    )
    assert "I can't tell / skip this" in card
    for key in ("ring", "cap_surface", "habitat"):
        assert "skip" in CHARACTERS[key].safety_note.lower(), (
            f"{key}'s safety note should name the escape hatch it relies on"
        )


# ---------------------------------------------------------------------------
# The numbers in the guidance, against the taxonomy that produces them.
#
# These notes quote counts -- "contradicts five of the deadly species" -- and
# a quoted count is prose, which goes stale the way every other hand-written
# figure in this project has. The cap_surface note shipped "four" while the
# answer rules out FIVE: *Gyromitra esculenta* declares only
# "Brain-like or folded", so "slimy or greasy" contradicts it like the rest,
# and it had simply never been counted. An undercount in a safety note is the
# note understating how much a wrong answer costs.
#
# Nothing below restates a count. Each one is computed from the taxonomy and
# the prose is required to agree, so a species added, dropped or re-described
# fails the test that owns the sentence.

import json  # noqa: E402
import re  # noqa: E402

POSTS_TS = ROOT / "app" / "src" / "content" / "posts.ts"

NUMBER_WORD = {
    1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
    6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
}


def _deadly_states() -> list[tuple[str, dict]]:
    data = json.loads((ROOT / "data" / "taxonomy.seed.json").read_text())
    return [
        (s["scientific_name"], s.get("character_states") or {})
        for s in data["species"]
        if s.get("toxicity") == "DEADLY"
    ]


def _contradicted(character: str, answer: str) -> list[str]:
    """Deadly species an answer rules out.

    A species is contradicted where it DECLARES the character and does not
    list that state. One that declares nothing cannot be contradicted at
    all -- an undescribed character gets likelihood 1.0 -- which is why a
    count of "deadly species gated by this character" is not the same
    number as "deadly species in the label space".
    """
    return sorted(
        name
        for name, states in _deadly_states()
        if states.get(character) and answer not in states[character]
    )


def _grassland_deadly() -> list[str]:
    return sorted(
        name
        for name, states in _deadly_states()
        if states.get("habitat") == ["No trees nearby", "Mixed broadleaf"]
    )


def test_the_cap_surface_note_states_the_number_the_taxonomy_supports():
    n = len(_contradicted("cap_surface", "Slimy or greasy"))
    note = CHARACTERS["cap_surface"].safety_note
    assert f"contradicts {NUMBER_WORD[n]} of the deadly species" in note, (
        f"the note disagrees with the taxonomy ({n}): {note!r}"
    )


def test_the_ring_note_states_the_number_the_taxonomy_supports():
    # The two it opens on are the ones "no ring" rules out.
    n = len(_contradicted("ring", "No ring"))
    note = CHARACTERS["ring"].safety_note
    assert note.lower().startswith(f"{NUMBER_WORD[n]} of the deadliest"), (
        f"the note disagrees with the taxonomy ({n}): {note!r}"
    )


def test_the_habitat_note_states_the_number_the_taxonomy_supports():
    n = len(_grassland_deadly())
    note = CHARACTERS["habitat"].safety_note
    assert f"away from {NUMBER_WORD[n]} deadly species" in note, (
        f"the note disagrees with the taxonomy ({n}): {note!r}"
    )


def test_the_learn_post_states_the_same_numbers_as_the_notes():
    """The same four facts on a second surface, which is the half that gets
    missed. Rule 1's own scanner read `assess` and not `disclaimer.py`, then
    read `disclaimer.py` and not `scripts/try_it.py`. A Learn post that
    teaches a beginner which answers are dangerous is a safety surface, and
    it is the one furthest from the code that produces the numbers.
    """
    post = re.sub(r"\s+", " ", POSTS_TS.read_text())

    cobwebby = NUMBER_WORD[len(_contradicted("ring", "Cobwebby fibres"))]
    no_ring = NUMBER_WORD[len(_contradicted("ring", "No ring"))]
    slimy = NUMBER_WORD[len(_contradicted("cap_surface", "Slimy or greasy"))]
    grass = NUMBER_WORD[len(_grassland_deadly())]

    for fragment in (
        f"rules out {cobwebby} of the deadly species",
        f'"no ring" rules out {no_ring}',
        f"contradicts {slimy} deadly species",
        f"{grass.capitalize()} of the deadly species I know list only",
    ):
        assert fragment in post, f"the post does not say: {fragment!r}"
