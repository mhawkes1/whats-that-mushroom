"""Turning a sentence into field notes.

The tests that matter are the ones about what the translator *cannot* do. It
sits in front of the safety layer, and anything it can smuggle past the
catalogue arrives at `reweight` as though the user had said it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "ml"))

from app.characters import CHARACTERS  # noqa: E402
from app.translate import (  # noqa: E402
    TRANSLATABLE,
    KeywordTranslator,
    Translation,
    response_schema,
    validate,
)


@pytest.fixture(scope="module")
def client():
    from app.config import settings

    settings.incident_log_path = ROOT / "data" / "unused-incidents.jsonl"
    from app.main import app

    with TestClient(app) as c:
        yield c


# --- What it cannot do -------------------------------------------------------


def test_the_schema_has_nowhere_to_name_a_species():
    """Not discouraged. Absent.

    A model asked to fill in `substrate` and `ring` cannot answer
    "Galerina marginata", because the response shape does not admit the
    string anywhere.
    """
    schema = response_schema()
    for name, prop in schema["properties"].items():
        if name == "not_understood":
            continue
        assert prop["type"] == ["string", "null"]
        assert set(prop["enum"]) == {*CHARACTERS[name].options, None}
    assert schema["additionalProperties"] is False
    # `not_understood` takes free strings, and is the only place one can go.
    assert schema["properties"]["not_understood"]["items"] == {"type": "string"}


def test_naming_a_species_produces_no_field_notes(client):
    """The whole argument, end to end."""
    for text in ("I think it is a death cap",
                 "this is Galerina marginata",
                 "identify this as a field mushroom"):
        body = client.post("/describe", json={"description": text}).json()
        assert body["field_notes"] == {}, text


def test_every_enum_is_read_from_the_catalogue_at_call_time():
    """The options cannot drift from the ones the server validates against.

    They are the same objects, not a copy -- so a character gaining an option
    gains it here in the same breath.
    """
    schema = response_schema()
    for key in TRANSLATABLE:
        assert [o for o in schema["properties"][key]["enum"] if o is not None] == list(
            CHARACTERS[key].options
        )


def test_it_never_extracts_a_taste():
    """Rule 5, at the door.

    The interrogation engine may ask for a taste only when no deadly candidate
    holds mass. A free-text box has no such gate, so the translator does not
    pull one out unprompted.
    """
    assert "taste" not in TRANSLATABLE
    assert "taste" not in response_schema()["properties"]
    result = KeywordTranslator().translate("small brown mushroom, tasted very peppery")
    assert "taste" not in result.field_notes


def test_a_state_that_is_not_an_option_is_dropped_and_recorded():
    """`strict` is a promise from the API. This is a safety path.

    If a constrained decode ever fails to constrain, the value must not reach
    the evidence engine -- and the failure must be visible rather than
    silently swallowed.
    """
    result = validate({
        "substrate": "Dead wood or a stump",   # real
        "cap_colour": "brownish",              # not an option
        "ring": None,                          # nothing said
        "not_understood": [],
    })
    assert result.field_notes == {"substrate": "Dead wood or a stump"}
    assert result.rejected == {"cap_colour": "brownish"}


def test_an_unknown_character_key_is_dropped():
    result = validate({"not_a_character": "anything", "not_understood": []})
    assert result.field_notes == {}


# --- What it does ------------------------------------------------------------


def test_the_worked_example(client):
    body = client.post("/describe", json={
        "description": "small brown mushroom, tuft on a rotten stump, "
                       "ring on the stem, no smell",
    }).json()
    assert body["field_notes"] == {
        "substrate": "Dead wood or a stump",
        "growth_form": "In a tight cluster",
        "ring": "Firm skirt-like ring",
        "smell": "Nothing much",
        "cap_colour": "Brown",
    }


def test_no_smell_is_an_observation_not_an_absence():
    """"Nothing much" is a catalogue option. A user who says they smelled
    nothing has told us something, and it should not read as a blank."""
    result = KeywordTranslator().translate("brown cap, no smell")
    assert result.field_notes["smell"] == "Nothing much"


def test_what_it_could_not_place_comes_back(client):
    """A dropped phrase the user cannot see is a gap they cannot close."""
    body = client.post("/describe", json={
        "description": "it had a weird papery skirt thing halfway up",
    }).json()
    assert body["not_understood"]


def test_every_answer_is_submittable_to_identify_unchanged(client):
    """The output is field notes, so it has to pass the same validation.

    /identify rejects a character it does not know and an answer outside the
    character's options -- which is exactly what a translator is at risk of
    producing.
    """
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (320, 240), (120, 90, 60)).save(buffer, "JPEG")

    notes = client.post("/describe", json={
        "description": "brown cap, tuft on a stump, ring on the stem, white gills",
    }).json()["field_notes"]
    assert notes

    import json as _json

    response = client.post(
        "/identify",
        files={"image": ("m.jpg", buffer.getvalue(), "image/jpeg")},
        data={"field_notes": _json.dumps(notes)},
    )
    assert response.status_code == 200, response.text


# --- Reporting ---------------------------------------------------------------


def test_the_response_always_says_which_backend_ran(client):
    """The same honesty /health applies to model_loaded.

    The offline stand-in finds much less and invents nothing; what it must
    never do is let itself be mistaken for the model.
    """
    body = client.post("/describe", json={"description": "brown cap"}).json()
    assert body["backend"] == "keywords"
    assert KeywordTranslator.name == "keywords"


def test_a_failed_translation_degrades_to_the_form(client, monkeypatch):
    """Losing the shortcut is not losing the app.

    The eight-question form is still there, so a translator that falls over
    costs a convenience and must never produce an error page.
    """
    from app import main

    class Broken:
        def translate(self, description):
            raise RuntimeError("no key, no network, no luck")

    monkeypatch.setitem(main.state, "translator", Broken())
    response = client.post("/describe", json={"description": "brown cap on a stump"})
    assert response.status_code == 200
    body = response.json()
    assert body["field_notes"] == {}
    assert body["backend"] == "unavailable"


def test_free_text_is_capped(client):
    assert client.post("/describe", json={"description": "x" * 2001}).status_code == 422


def test_an_empty_description_is_refused(client):
    assert client.post("/describe", json={"description": "   "}).status_code == 400


def test_a_translation_is_a_suggestion_not_a_submission():
    """Pinned by shape: /describe returns notes, it does not identify.

    The client pre-fills the form and the user confirms, which is the rule the
    spore print matcher already follows.
    """
    from app.schemas import DescribeOut

    fields = set(DescribeOut.model_fields)
    assert fields == {"field_notes", "not_understood", "rejected", "backend"}
    assert not fields & {"candidates", "verdict", "species", "headline"}


def test_the_translation_dataclass_defaults_to_saying_nothing():
    empty = Translation()
    assert empty.field_notes == {} and empty.backend == "none"


# --- The offline stand-in's own failure mode ---------------------------------


def test_a_colour_word_is_not_lifted_out_of_the_phrase_it_belongs_to():
    """The keyword matcher's characteristic way of being wrong.

    "spore print came out rust brown" says nothing about the cap. A bare
    colour cue that grabs the word anyway hands the evidence engine an
    observation the user never made, which is worse than handing it nothing.

    Two rules keep it honest, and both are about ordering: a cue that names
    what it describes is tried before a bare one, and a match may not claim
    text another cue already took.
    """
    translate = KeywordTranslator().translate

    assert translate("spore print came out rust brown").field_notes == {
        "spore_print_colour": "Rust or cinnamon brown"
    }
    assert translate("brown cap with a white spore print").field_notes == {
        "cap_colour": "Brown",
        "spore_print_colour": "White or cream",
    }
    assert translate("white gills").field_notes == {"gill_colour": "White"}


def test_the_bare_colour_cues_are_tried_last():
    """Pinned as an ordering property, not just by example.

    The list is read top to bottom and the first match claims the text, so a
    bare `\\bbrown\\b` sitting above `spore print ... brown` silently changes
    what the matcher means.
    """
    from app.translate import CUES

    bare = [i for i, (pattern, key, _) in enumerate(CUES)
            if key == "cap_colour" and "cap" not in pattern]
    specific = [i for i, (_, key, _) in enumerate(CUES) if key != "cap_colour"]
    assert bare, "expected some bare colour cues"
    assert min(bare) > max(specific), "a bare colour cue outranks a specific one"
