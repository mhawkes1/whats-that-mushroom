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
