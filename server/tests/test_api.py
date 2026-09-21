"""End-to-end API tests against the real app, using the stub backend."""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def a_photo(colour=(120, 90, 60), size=(640, 480)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, "JPEG")
    return buffer.getvalue()


def test_health_reports_readiness(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["n_classes"] > 0
    # The seed taxonomy has not been through mycological review, and the
    # service must say so rather than implying it is authoritative.
    assert body["taxonomy_reviewed"] is False


def test_identify_returns_a_full_assessment(client):
    response = client.post(
        "/identify",
        files={"image": ("m.jpg", a_photo(), "image/jpeg")},
        data={"month": "10", "latitude": "51.5", "longitude": "-0.12"},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["verdict"] in (
        "species", "group", "uncertain", "dangerous_group", "out_of_scope",
    )
    assert body["headline"]
    assert body["warnings"], "every response must carry a warning block"
    assert body["observation_id"]


def test_every_response_carries_the_never_eat_disclaimer(client):
    for colour in [(10, 10, 10), (200, 200, 200), (140, 60, 30), (90, 140, 70)]:
        body = client.post(
            "/identify", files={"image": ("m.jpg", a_photo(colour), "image/jpeg")}
        ).json()
        assert any("never eat" in w.lower() for w in body["warnings"]), (
            f"missing disclaimer for verdict {body['verdict']}"
        )


def test_response_never_claims_edibility(client):
    import re

    affirmative = re.compile(r"\b(is edible|are edible|good to eat|you can eat)\b", re.I)
    for colour in [(30, 30, 30), (210, 205, 190), (160, 40, 40), (70, 110, 60)]:
        body = client.post(
            "/identify", files={"image": ("m.jpg", a_photo(colour), "image/jpeg")}
        ).json()
        blob = " ".join([body["headline"], body["detail"], *body["warnings"]])
        assert not affirmative.search(blob), f"edibility claim in response: {blob[:150]}"


def test_uncalibrated_service_advertises_the_fact(client):
    """Without a fitted calibration the confidence numbers are not
    trustworthy, and the API must not pretend otherwise."""
    body = client.post(
        "/identify", files={"image": ("m.jpg", a_photo(), "image/jpeg")}
    ).json()
    assert body["calibrated"] is False


def test_answer_flow_updates_the_assessment(client):
    first = client.post(
        "/identify", files={"image": ("m.jpg", a_photo(), "image/jpeg")}
    ).json()

    if not first["questions"]:
        pytest.skip("stub prediction produced no questions for this image")

    question = first["questions"][0]
    second = client.post(
        "/answer",
        json={
            "observation_id": first["observation_id"],
            "character_key": question["key"],
            "answer": question["options"][0] if question["options"] else "yes",
        },
    ).json()

    assert second["observation_id"] == first["observation_id"]
    # The answered question must not be asked again.
    assert question["key"] not in [q["key"] for q in second["questions"]]


def test_answer_for_unknown_observation_is_rejected(client):
    response = client.post(
        "/answer",
        json={"observation_id": "nope", "character_key": "volva", "answer": "yes"},
    )
    assert response.status_code == 404


def test_rejects_a_non_image_upload(client):
    response = client.post(
        "/identify", files={"image": ("x.txt", b"definitely not a jpeg", "text/plain")}
    )
    assert response.status_code == 400


def test_rejects_an_empty_upload(client):
    response = client.post("/identify", files={"image": ("x.jpg", b"", "image/jpeg")})
    assert response.status_code == 400


def test_rejects_an_out_of_range_month(client):
    response = client.post(
        "/identify",
        files={"image": ("m.jpg", a_photo(), "image/jpeg")},
        data={"month": "13"},
    )
    assert response.status_code == 422


def test_species_lookup_returns_lookalikes_with_toxicity(client):
    body = client.get("/species/amanita-phalloides").json()
    assert body["scientific_name"] == "Amanita phalloides"
    assert body["toxicity"] == "DEADLY"
    assert body["lookalikes"], "the death cap must list its lookalikes"
    assert "volva" in body["diagnostic_characters"]


def test_species_notes_do_not_leak_internal_policy(client):
    """internal_note must never reach a client."""
    body = client.get("/species/agaricus-campestris").json()
    assert "policy" not in body["notes"].lower()
    assert "internal_note" not in body


def test_unknown_species_is_404(client):
    assert client.get("/species/not-a-real-species").status_code == 404


# --- Capture flow: multiple views plus field notes ---------------------------


def test_field_form_is_served_rather_than_hardcoded(client):
    """The client must not invent its own answer strings.

    Every option the form offers has to be one `/identify` will accept, or a
    user's answer is silently discarded.
    """
    from app.characters import CHARACTERS

    body = client.get("/field-form").json()
    assert body["fields"], "the capture form must offer something"

    for field in body["fields"]:
        character = CHARACTERS[field["key"]]
        assert field["options"] == list(character.options)
        assert field["label"] and field["prompt"]


def test_identify_accepts_three_views(client):
    response = client.post(
        "/identify",
        files={
            "image": ("top.jpg", a_photo((150, 120, 90)), "image/jpeg"),
            "side": ("side.jpg", a_photo((140, 115, 85)), "image/jpeg"),
            "underside": ("under.jpg", a_photo((210, 205, 195)), "image/jpeg"),
        },
    )
    assert response.status_code == 200
    assert response.json()["warnings"]


def test_a_single_photograph_still_works(client):
    """The extra views are optional; one photo must remain a complete request."""
    response = client.post(
        "/identify", files={"image": ("m.jpg", a_photo(), "image/jpeg")}
    )
    assert response.status_code == 200


def test_extra_views_change_the_assessment(client):
    """Averaging over views must actually use them.

    If the side and underside made no difference, the two extra taps we ask
    of the user would be for nothing.
    """
    one = client.post(
        "/identify", files={"image": ("t.jpg", a_photo((150, 120, 90)), "image/jpeg")}
    ).json()
    three = client.post(
        "/identify",
        files={
            "image": ("t.jpg", a_photo((150, 120, 90)), "image/jpeg"),
            "side": ("s.jpg", a_photo((40, 40, 40)), "image/jpeg"),
            "underside": ("u.jpg", a_photo((230, 225, 215)), "image/jpeg"),
        },
    ).json()

    one_top = [(c["species_key"], round(c["confidence"], 6)) for c in one["candidates"]]
    three_top = [(c["species_key"], round(c["confidence"], 6)) for c in three["candidates"]]
    assert one_top != three_top


def test_field_notes_are_accepted_and_not_asked_again(client):
    """A fact volunteered on the form must count as answered."""
    import json

    from app.characters import CHARACTERS

    # Taken from the catalogue rather than typed out, so the test cannot
    # drift away from the options the server actually accepts.
    habitat = CHARACTERS["habitat"].options[0]

    body = client.post(
        "/identify",
        files={"image": ("m.jpg", a_photo(), "image/jpeg")},
        data={"field_notes": json.dumps({"habitat": habitat})},
    ).json()

    assert body["observation_id"]
    assert "habitat" not in [q["key"] for q in body["questions"]]


def test_blank_field_notes_are_skipped_not_rejected(client):
    """Every field is optional, and an empty one must not fail the request."""
    import json

    response = client.post(
        "/identify",
        files={"image": ("m.jpg", a_photo(), "image/jpeg")},
        data={"field_notes": json.dumps({"habitat": "", "smell": None})},
    )
    assert response.status_code == 200


def test_an_unknown_character_is_rejected_not_ignored(client):
    """Dropping it silently would let the user think they had told us something."""
    import json

    response = client.post(
        "/identify",
        files={"image": ("m.jpg", a_photo(), "image/jpeg")},
        data={"field_notes": json.dumps({"vibes": "good"})},
    )
    assert response.status_code == 400
    assert "vibes" in response.json()["detail"]


def test_an_answer_outside_the_option_list_is_rejected(client):
    import json

    response = client.post(
        "/identify",
        files={"image": ("m.jpg", a_photo(), "image/jpeg")},
        data={"field_notes": json.dumps({"habitat": "on the moon"})},
    )
    assert response.status_code == 400


def test_malformed_field_notes_are_rejected(client):
    response = client.post(
        "/identify",
        files={"image": ("m.jpg", a_photo(), "image/jpeg")},
        data={"field_notes": "not json at all"},
    )
    assert response.status_code == 400


def test_a_broken_second_view_names_which_photo_failed(client):
    """Three uploads means the error has to say which one was wrong."""
    response = client.post(
        "/identify",
        files={
            "image": ("t.jpg", a_photo(), "image/jpeg"),
            "underside": ("u.txt", b"not a jpeg", "text/plain"),
        },
    )
    assert response.status_code == 400
    assert "underside" in response.json()["detail"]


def test_field_notes_never_unlock_a_species_verdict(client):
    """Answers feed the ranking; they must not bypass the safety layer.

    This is the rule that makes the form safe to add: whatever the user
    volunteers, the verdict still comes from `SafetyLayer.assess`.
    """
    import json

    from app.characters import CHARACTERS

    notes = {
        key: CHARACTERS[key].options[0]
        for key in ("habitat", "substrate", "growth_form", "gill_colour", "ring")
    }
    for colour in [(20, 20, 20), (200, 195, 185), (150, 60, 40)]:
        body = client.post(
            "/identify",
            files={"image": ("m.jpg", a_photo(colour), "image/jpeg")},
            data={"field_notes": json.dumps(notes)},
        ).json()
        assert any("never eat" in w.lower() for w in body["warnings"])
        if body["deadly_in_play"]:
            assert body["verdict"] != "species"


def test_health_reports_the_same_model_version_identify_stamps(client):
    """A stored result has to be comparable to a current one.

    The client keeps an observation log, and a confidence recorded by an
    earlier model is not the same quantity as one recorded by this one. It
    can only say so if it can ask which model is running without performing
    an identification to find out -- and the two strings have to be the same
    string, or the comparison is noise.
    """
    health = client.get("/health").json()
    identified = client.post(
        "/identify", files={"image": ("m.jpg", a_photo(), "image/jpeg")}
    ).json()

    assert health["model_version"]
    assert health["model_version"] == identified["model_version"]


def test_health_reports_character_state_coverage(client):
    """How much of the table is filled in, so an operator can tell.

    Answers only re-weight species that have states. Without this number,
    a ranking that does not move looks identical to a broken update.
    """
    from app.config import settings
    from app.evidence import described_coverage
    from app.taxonomy_service import TaxonomyService

    taxonomy = TaxonomyService.load(settings.taxonomy_path)
    body = client.get("/health").json()

    assert body["character_states_described"] == described_coverage(taxonomy)["described"]
    assert body["character_states_described"] > 0


def test_field_notes_now_change_the_assessment(client):
    """The deadly species are described, so an answer about them must bite.

    This is the end of the loop the capture form started: something the user
    saw, submitted on the form, reaching the ranking.
    """
    import json

    photo = a_photo((150, 120, 90))
    # Spore print is described for every deadly species, so whichever ones the
    # stub ranks, this answer is evidence about them.
    notes = {"spore_print_colour": "Black"}

    without = client.post(
        "/identify", files={"image": ("m.jpg", photo, "image/jpeg")}
    ).json()
    with_notes = client.post(
        "/identify",
        files={"image": ("m.jpg", photo, "image/jpeg")},
        data={"field_notes": json.dumps(notes)},
    ).json()

    rank = lambda body: [  # noqa: E731
        (c["species_key"], round(c["confidence"], 9)) for c in body["candidates"]
    ]
    assert rank(without) != rank(with_notes)


# --- Spore print matching ----------------------------------------------------


def a_spore_card(deposit=(38, 35, 34), white=(243, 243, 243)) -> bytes:
    """Half deposit, half white reference card, as the instructions describe."""
    buffer = io.BytesIO()
    image = Image.new("RGB", (400, 200), white)
    image.paste(Image.new("RGB", (200, 200), deposit), (0, 0))
    image.save(buffer, "PNG")  # lossless: JPEG artefacts would move the colours
    return buffer.getvalue()


SAMPLE_REGION = "0.05,0.2,0.35,0.6"
WHITE_REGION = "0.6,0.2,0.35,0.6"


def test_matching_a_photographed_spore_print(client):
    response = client.post(
        "/spore-print/match",
        files={"image": ("print.png", a_spore_card(), "image/png")},
        data={"sample_region": SAMPLE_REGION, "white_region": WHITE_REGION},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["confident"] is True
    assert body["option"] == "Black"
    assert body["ranked"][0]["option"] == "Black"
    assert body["corrected_rgb"]


def test_a_matched_colour_is_submittable_to_answer(client):
    """The loop this closes: the engine asks, the camera reads, /answer takes it."""
    from app.characters import CHARACTERS

    body = client.post(
        "/spore-print/match",
        files={"image": ("print.png", a_spore_card(), "image/png")},
        data={"sample_region": SAMPLE_REGION, "white_region": WHITE_REGION},
    ).json()

    assert body["option"] in CHARACTERS["spore_print_colour"].options


def test_an_ambiguous_print_returns_no_option_but_still_ranks(client):
    """White against pink is the boundary that matters, and it must decline."""
    white = REFERENCE_WHITE = (245, 240, 228)
    pink = (226, 186, 180)
    midpoint = tuple((a + b) // 2 for a, b in zip(white, pink))

    body = client.post(
        "/spore-print/match",
        files={"image": ("print.png", a_spore_card(deposit=midpoint), "image/png")},
        data={"sample_region": SAMPLE_REGION, "white_region": WHITE_REGION},
    ).json()

    assert body["confident"] is False
    assert body["option"] is None
    assert len(body["ranked"]) > 1, "the manual picker still needs an ordering"
    assert body["reason"]


def test_a_malformed_region_is_rejected(client):
    for bad in ["0.1,0.2", "a,b,c,d", ""]:
        response = client.post(
            "/spore-print/match",
            files={"image": ("print.png", a_spore_card(), "image/png")},
            data={"sample_region": bad, "white_region": WHITE_REGION},
        )
        assert response.status_code in (400, 422), bad


def test_a_region_off_the_edge_of_the_image_is_rejected(client):
    response = client.post(
        "/spore-print/match",
        files={"image": ("print.png", a_spore_card(), "image/png")},
        data={"sample_region": "0.8,0.0,0.5,0.5", "white_region": WHITE_REGION},
    )
    assert response.status_code == 400


def test_a_broken_upload_names_the_spore_print(client):
    response = client.post(
        "/spore-print/match",
        files={"image": ("x.txt", b"not an image", "text/plain")},
        data={"sample_region": SAMPLE_REGION, "white_region": WHITE_REGION},
    )
    assert response.status_code == 400
    assert "spore print" in response.json()["detail"]


def test_matching_never_asserts_edibility(client):
    """Rule 1, on a path that returns free text."""
    import re

    affirmative = re.compile(r"\b(edible|safe to eat|good to eat)\b", re.I)
    for deposit in [(38, 35, 34), (245, 240, 228), (166, 104, 56)]:
        body = client.post(
            "/spore-print/match",
            files={"image": ("print.png", a_spore_card(deposit=deposit), "image/png")},
            data={"sample_region": SAMPLE_REGION, "white_region": WHITE_REGION},
        ).json()
        assert not affirmative.search(body["reason"]), body["reason"]
