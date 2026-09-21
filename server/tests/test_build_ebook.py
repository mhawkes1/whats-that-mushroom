"""Generating the companion ebook's field data from the taxonomy.

The book and the app make the same claims about the same species, and the
only way two copies of a claim stay in step is if one of them is generated.
What has to be true of the generator is not that it fills every slot -- the
taxonomy is sparse and silence is the honest output -- but that it never
overwrites the author, never invents, and never loses the book.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "ml"))

from app.characters import CHARACTERS  # noqa: E402
from app.taxonomy_service import TaxonomyService  # noqa: E402


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "build_ebook_script", ROOT / "scripts" / "build_ebook.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _load_script()


@pytest.fixture(scope="module")
def taxonomy():
    return TaxonomyService.load(ROOT / "data" / "taxonomy.seed.json")


ROW_LABELS = [
    "Habitat", "Trees nearby", "Growing from", "Season", "Growth habit",
    "Cap", "Gills / Pores", "Stem", "Base", "Spore print", "Smell",
    "Confused with", "How to tell them apart",
]


def page(latin: str, common: str = "Test", rows=ROW_LABELS, points=3) -> str:
    """One species page in the book's own markup."""
    body = "".join(
        f'<div class="row"><span class="k">{label}</span>'
        f'<span class="dots"></span><span class="v"></span></div>'
        for label in rows
    )
    kips = "".join(
        f'<div class="kip"><span class="kn">{n}</span><span class="kv"></span></div>'
        for n in range(1, points + 1)
    )
    return (
        f'<article class="sp" style="--band:#9E2B20">'
        f'<header class="sp-head"><div class="names"><h3>{common}</h3>'
        f'<p class="latin">{latin}</p></div></header>'
        f'<figure class="shot"><img src="data:image/jpeg;base64,AAAA"></figure>'
        f'<div class="fielddata">{body}{kips}'
        f'<div class="fnote"></div></div></article>'
    )


def book(*articles: str) -> str:
    return (
        "<html><head><title>A book</title></head><body>"
        + "".join(articles)
        + "</body></html>"
    )


def values(html_text: str) -> dict[str, str]:
    return {
        k: v
        for k, v in re.findall(
            r'<span class="k">(.*?)</span><span class="dots"></span>'
            r'<span class="v"[^>]*>(.*?)</span>',
            html_text,
            re.S,
        )
    }


# --- The promises ------------------------------------------------------------


def test_it_never_overwrites_a_slot_the_author_has_filled(taxonomy):
    """The author's words win, always. This is what makes it safe to re-run."""
    source = book(page("Amanita phalloides", "Death Cap")).replace(
        '<span class="k">Base</span><span class="dots"></span><span class="v"></span>',
        '<span class="k">Base</span><span class="dots"></span>'
        '<span class="v">A sac you must dig for.</span>',
    )
    filled, _ = script.fill(source, taxonomy)
    assert values(filled)["Base"] == "A sac you must dig for."


def test_running_it_twice_changes_nothing(taxonomy):
    """Once a slot is filled it is content, and content is never touched."""
    once, first = script.fill(book(page("Amanita phalloides")), taxonomy)
    twice, second = script.fill(once, taxonomy)
    assert values(twice) == values(once)
    assert second["rows"] == 0 and second["points"] == 0 and second["notes"] == 0
    assert first["rows"] > 0


def test_an_empty_slot_stays_empty_when_the_taxonomy_is_silent(taxonomy):
    """No description is not a reason to guess; it is a reason to say nothing.

    The same rule the evidence layer applies to an undescribed character.
    """
    filled, stats = script.fill(book(page("Amanita phalloides")), taxonomy)
    assert values(filled)["Season"] == ""
    assert stats["empty"]["Season"] == 1


def test_it_never_prints_a_taste(taxonomy):
    """Rule 5, on paper.

    The app gates the taste question on no deadly candidate holding mass.
    A printed page cannot check that, so the generator does not put a taste
    into a row or a key point at all.

    This is about what the generator writes, not about the author's own
    prose. A field note may well mention a bitter taste -- `notes` is
    rendered verbatim in the app for the same species -- and censoring the
    author is not this script's job.
    """
    assert "taste" in script.OMITTED_CHARACTERS
    tasted = [
        s for s in taxonomy.species.values() if s.character_states.get("taste")
    ]
    assert tasted, "fixture assumes some species declare a taste"
    for species in tasted:
        assert script._states(species, "taste") == []
        row_text = " ".join(script.field_values(species, taxonomy).values())
        point_text = " ".join(script.key_points(species, taxonomy))
        for state in species.character_states["taste"]:
            assert state.lower() not in (row_text + point_text).lower()
        assert CHARACTERS["taste"].label.lower() not in (row_text + point_text).lower()


def test_everything_it_writes_is_marked_as_generated(taxonomy):
    filled, stats = script.fill(book(page("Amanita phalloides")), taxonomy)
    assert filled.count('class="gen"') == stats["rows"] + stats["points"] + stats["notes"]
    assert "not been reviewed by a mycologist" in filled
    assert filled.index("DRAFT") < filled.index('<article class="sp"')


def test_the_field_note_is_the_public_note_and_never_the_internal_one(taxonomy):
    """`notes` is written for a reader; `internal_note` carries policy.

    `internal_note` cannot leak because the loaded `Species` never carries
    it -- which is the right shape, and worth pinning so that adding the
    field for some other purpose does not quietly put review flags and
    toxicity rationale on a printed page.
    """
    raw = json.loads((ROOT / "data" / "taxonomy.seed.json").read_text())
    internal = {
        s["scientific_name"]: s["internal_note"]
        for s in raw["species"]
        if s.get("internal_note")
    }
    assert internal, "fixture assumes some species carry one"
    assert not hasattr(taxonomy.get("amanita-phalloides"), "internal_note")

    filled, _ = script.fill(
        book(*(page(latin) for latin in internal)), taxonomy
    )
    for latin, hidden in internal.items():
        assert hidden not in filled, latin

    notes = re.findall(r'<div class="fnote"[^>]*>(.*?)</div>', filled, re.S)
    assert notes == [
        script.species_for(latin, taxonomy).notes for latin in internal
    ]


def test_the_book_survives_the_pass(taxonomy):
    """Photographs, structure and prose come through untouched.

    Everything outside the slots is the author's design, including seventy
    megabytes of base64 photograph that a careless rewrite would mangle.
    """
    source = book(page("Amanita phalloides"), page("Boletus edulis"))
    filled, _ = script.fill(source, taxonomy)
    assert filled.count('<article class="sp"') == source.count('<article class="sp"')
    assert filled.count("data:image/jpeg;base64,AAAA") == 2
    for fragment in ('<div class="dots"></div>', "<h3>", '<p class="latin">'):
        assert source.count(fragment) == filled.count(fragment)


def test_a_species_the_taxonomy_does_not_know_is_reported_not_filled(taxonomy):
    filled, stats = script.fill(book(page("Amanita notarealensis")), taxonomy)
    assert stats["unmatched"] == ["Amanita notarealensis"]
    assert stats["matched"] == 0
    assert 'class="gen"' not in filled


def test_the_synonyms_resolve(taxonomy):
    """The book names two species by an older combination."""
    for old, new in script.SYNONYMS.items():
        assert script.species_for(old, taxonomy) is not None, old
        assert script.species_for(old, taxonomy).scientific_name == new


# --- Drift guards ------------------------------------------------------------


def test_every_row_the_book_asks_for_has_an_answer(taxonomy):
    """A label the generator does not know is a row silently left blank."""
    produced = set(script.field_values(taxonomy.get("amanita-phalloides"), taxonomy))
    assert set(ROW_LABELS) <= produced


def test_every_mapped_character_is_a_real_character(taxonomy):
    for label, characters in script.ROW_CHARACTERS.items():
        for character in characters:
            assert character in CHARACTERS, f"{label} maps unknown {character!r}"


def test_no_character_is_mapped_into_two_rows():
    seen = [c for characters in script.ROW_CHARACTERS.values() for c in characters]
    assert len(seen) == len(set(seen))


def test_every_described_character_reaches_the_page_somehow(taxonomy):
    """Nothing the taxonomy says is quietly dropped, except by decision.

    A character in no row and never surfacing as a key point would be data
    the book cannot show, which is worth noticing rather than discovering in
    print.
    """
    described = {
        character
        for species in taxonomy.species.values()
        for character in species.character_states
    }
    in_rows = {c for characters in script.ROW_CHARACTERS.values() for c in characters}
    unreachable = described - in_rows - script.OMITTED_CHARACTERS
    # These have no row of their own and appear as key points instead.
    assert unreachable == {
        "bruising_reaction", "flesh_colour", "texture",
    }, f"unexpected homeless characters: {sorted(unreachable)}"


def test_key_points_prefer_what_separates_a_species_from_its_lookalikes(taxonomy):
    """The same reasoning the interrogation engine uses to choose a question.

    The death cap's volva is the character that tells it from three of its
    lookalikes at once, so it leads.
    """
    points = script.key_points(taxonomy.get("amanita-phalloides"), taxonomy)
    assert points[0].startswith(CHARACTERS["volva"].label)
    assert len(points) <= 3


def test_lookalikes_separated_the_same_way_are_named_together(taxonomy):
    """One check, written once.

    Repeating "no volva in X; no volva in Y; no volva in Z" reads as three
    things to do in the field when it is one.
    """
    prose = script.field_values(
        taxonomy.get("amanita-phalloides"), taxonomy
    )["How to tell them apart"]
    assert prose.count(CHARACTERS["volva"].label.lower()) == 1
    assert "Field Mushroom" in prose and "Horse Mushroom" in prose
