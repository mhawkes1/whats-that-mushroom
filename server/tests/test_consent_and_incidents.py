"""Onboarding consent, and the route for reporting that the app was wrong.

Both were blocking items in `docs/SAFETY.md`. What is tested here is not that
a form submits: it is that the consent cannot be satisfied without saying
what is currently untrue about the service, and that a report of someone
being unwell never comes back as a filed ticket.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "ml"))

from app import disclaimer as disclaimer_module  # noqa: E402
from app.config import settings  # noqa: E402
from app.incidents import (  # noqa: E402
    EMERGENCY_GUIDANCE,
    IncidentStore,
    Severity,
    triage,
)
from app.taxonomy_service import TaxonomyService  # noqa: E402


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    # The incident log is real user data. Never let a test run write into the
    # repository's own copy.
    settings.incident_log_path = tmp_path_factory.mktemp("incidents") / "incidents.jsonl"
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def taxonomy():
    return TaxonomyService.load(settings.taxonomy_path)


# --- The disclaimer ----------------------------------------------------------


def test_the_version_is_the_text(client):
    """A changed word must invalidate an acknowledgement of the old one.

    The version is derived from the content rather than maintained beside it,
    so it cannot be forgotten on the way past.
    """
    first = disclaimer_module.build(
        model_loaded=False, calibrated=False, taxonomy_reviewed=False
    )
    edited = disclaimer_module.build(
        model_loaded=False, calibrated=False, taxonomy_reviewed=False
    )
    assert first.version == edited.version

    original_body = disclaimer_module.BODY
    try:
        disclaimer_module.BODY = original_body + " One more sentence."
        assert (
            disclaimer_module.build(
                model_loaded=False, calibrated=False, taxonomy_reviewed=False
            ).version
            != first.version
        )
    finally:
        disclaimer_module.BODY = original_body


def test_what_is_currently_untrue_must_be_acknowledged(client):
    """While the model is a stub, the user is told so before their first result.

    Not in a settings screen they will never open. `/health` reports these
    three facts and the disclaimer states each one that is false.
    """
    health = client.get("/health").json()
    keys = {a["key"] for a in client.get("/disclaimer").json()["acknowledgements"]}

    assert ("no_trained_model" in keys) is not health["model_loaded"]
    assert ("uncalibrated" in keys) is not health["calibrated"]
    assert ("taxonomy_unreviewed" in keys) is not health["taxonomy_reviewed"]


def test_the_statements_that_never_go_away_are_always_there(client):
    keys = {a["key"] for a in client.get("/disclaimer").json()["acknowledgements"]}
    assert {
        "never_asserts_edibility",
        "photograph_cannot_rule_out",
        "not_a_substitute",
    } <= keys


def test_becoming_ready_changes_the_version_and_reasks(client):
    """Consent to an older set of statements is not consent to a newer one.

    When a model is trained, calibration fitted or the taxonomy reviewed, the
    statements a user agreed to stop being the statements that apply.
    """
    stub = disclaimer_module.build(
        model_loaded=False, calibrated=False, taxonomy_reviewed=False
    )
    ready = disclaimer_module.build(
        model_loaded=True, calibrated=True, taxonomy_reviewed=True
    )
    assert stub.version != ready.version
    assert len(ready.acknowledgements) < len(stub.acknowledgements)


def test_every_acknowledgement_is_a_separate_claim(client):
    """There is no "accept all".

    One blanket agreement is a formality that trains people to tap past
    safety text. Each of these is a distinct thing to know, so none of them
    may be a catch-all.
    """
    acks = client.get("/disclaimer").json()["acknowledgements"]
    assert len({a["key"] for a in acks}) == len(acks)
    for ack in acks:
        assert ack["statement"].strip()
        assert ack["because"].strip()
        assert not re.search(r"\ball of the above\b|\bterms\b", ack["statement"].lower())


def test_the_disclaimer_asserts_no_edibility(client):
    """Rule 1 covers this text too, and it is the text users read most carefully."""
    affirmative = [
        re.compile(r"\bis edible\b"),
        re.compile(r"\bedible\b"),
        re.compile(r"\bchoice\b"),
        re.compile(r"\bgood to eat\b"),
        re.compile(r"\byou can eat\b"),
        re.compile(r"\bsafe\b(?!ty)"),
    ]
    negated_ok = re.compile(
        r"(never|not|cannot|can't|does not|doesn't|whether|no such)[^.]*"
        r"\b(safe|edible|eat)\b"
    )

    body = client.get("/disclaimer").json()
    texts = [body["heading"], body["body"]] + [
        t for a in body["acknowledgements"] for t in (a["statement"], a["because"])
    ]
    for text in texts:
        lowered = text.lower()
        for pattern in affirmative:
            for match in pattern.finditer(lowered):
                start = lowered.rfind(".", 0, match.start()) + 1
                end = lowered.find(".", match.end())
                sentence = lowered[start : end if end != -1 else len(lowered)]
                assert negated_ok.search(sentence), f"affirmative claim: {sentence!r}"


# --- Triage ------------------------------------------------------------------


def a_report(**over):
    base = dict(
        verdict="species",
        reported_candidates=["agaricus-campestris"],
        believed_species_key=None,
        anyone_ate_it=False,
        anyone_unwell=False,
    )
    return {**base, **over}


def test_someone_unwell_outranks_everything(taxonomy):
    """Whatever else the report says, this is not a defect report."""
    for over in (
        {"anyone_ate_it": True},
        {"anyone_unwell": True},
        {"anyone_ate_it": True, "believed_species_key": "amanita-phalloides"},
    ):
        assert (
            triage(taxonomy=taxonomy, **a_report(**over)) is Severity.MEDICAL
        ), over


def test_a_missed_deadly_species_is_the_worst_defect(taxonomy):
    """The failure the whole app exists to avoid.

    It named something ordinary, warned about nothing, and the reporter says
    it was a death cap.
    """
    assert (
        triage(
            taxonomy=taxonomy,
            **a_report(believed_species_key="amanita-phalloides"),
        )
        is Severity.DANGEROUS_MISS
    )


def test_a_warning_the_reporter_says_was_wrong_is_still_recorded(taxonomy):
    """Lower priority, never zero. Warnings nobody believes protect nobody."""
    assert (
        triage(
            taxonomy=taxonomy,
            **a_report(
                verdict="dangerous_group",
                reported_candidates=["amanita-phalloides", "agaricus-campestris"],
                believed_species_key="agaricus-campestris",
            ),
        )
        is Severity.DANGEROUS_FALSE_ALARM
    )


def test_a_deadly_candidate_in_the_list_counts_as_a_warning(taxonomy):
    """The app does not have to refuse outright to have warned.

    A deadly species anywhere in the candidate list carries the full warning
    (rule 3), so a report against it is a false alarm, not a miss.
    """
    assert (
        triage(
            taxonomy=taxonomy,
            **a_report(
                verdict="uncertain",
                reported_candidates=["agaricus-campestris", "amanita-phalloides"],
                believed_species_key="agaricus-campestris",
            ),
        )
        is Severity.DANGEROUS_FALSE_ALARM
    )


def test_severity_comes_from_the_taxonomy_not_the_reporter(taxonomy):
    """An ordinary error stays ordinary however strongly it is reported."""
    assert (
        triage(taxonomy=taxonomy, **a_report(believed_species_key="boletus-edulis"))
        is Severity.ORDINARY
    )
    # A species the taxonomy does not know cannot be graded, and an ungraded
    # report is not promoted on the reporter's say-so.
    assert (
        triage(taxonomy=taxonomy, **a_report(believed_species_key="not-a-species"))
        is Severity.ORDINARY
    )


# --- The endpoint ------------------------------------------------------------


def test_a_report_of_illness_comes_back_as_an_emergency_not_a_ticket(client):
    """An incident form that files a medical emergency and says thank you is
    worse than no form at all."""
    body = client.post(
        "/incident",
        json={"account": "I ate some and feel unwell.", "anyone_unwell": True},
    ).json()

    assert body["medical_emergency"] is True
    assert body["severity"] == "medical"
    assert body["emergency_guidance"] == EMERGENCY_GUIDANCE
    assert "999" in body["emergency_guidance"]
    # The guidance must not be buried under a confirmation.
    assert "thank" not in body["acknowledgement"].lower()


def test_an_ordinary_report_carries_no_emergency_guidance(client):
    body = client.post(
        "/incident",
        json={
            "observation_id": "obs-1",
            "verdict": "species",
            "reported_candidates": ["lepista-nuda"],
            "believed_species_key": "boletus-edulis",
            "account": "Pretty sure this was a cep.",
        },
    ).json()
    assert body["medical_emergency"] is False
    assert body["emergency_guidance"] is None
    assert body["severity"] == "ordinary"


def test_a_report_changes_nothing_in_the_taxonomy(client):
    """A report is evidence for a reviewer, not a correction.

    The reporter may be wrong, and the data they would be editing is what
    every other user's warnings are derived from.
    """
    before = settings.taxonomy_path.read_bytes()
    client.post(
        "/incident",
        json={
            "believed_species_key": "amanita-phalloides",
            "reported_candidates": ["agaricus-campestris"],
            "account": "This was definitely a death cap and you said field mushroom.",
        },
    )
    assert settings.taxonomy_path.read_bytes() == before


def test_reports_are_appended_and_readable(client):
    store = IncidentStore(settings.incident_log_path)
    before = len(store.all())
    client.post("/incident", json={"account": "one"})
    client.post("/incident", json={"account": "two"})
    after = store.all()

    assert len(after) == before + 2
    assert [r.account for r in after[-2:]] == ["one", "two"]
    # Append-only: an incident log that can be edited in place is not evidence.
    lines = settings.incident_log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(after)
    assert all(json.loads(line)["incident_id"] for line in lines)


def test_a_report_records_what_the_app_said_not_what_it_says_now(client):
    """Sent by the client from its own log.

    The server forgets an observation; the report has to stay actionable
    afterwards, and it has to record the model that actually produced the
    answer rather than whichever one is running when a reviewer opens it.
    """
    client.post(
        "/incident",
        json={
            "observation_id": "obs-42",
            "verdict": "dangerous_group",
            "reported_candidates": ["amanita-phalloides", "agaricus-campestris"],
            "model_version": "0.0.1-old",
            "calibrated": False,
            "believed_species_key": "agaricus-campestris",
            "account": "It was a field mushroom.",
        },
    )
    report = IncidentStore(settings.incident_log_path).all()[-1]
    assert report.model_version == "0.0.1-old"
    assert report.calibrated is False
    assert report.observation_id == "obs-42"
    assert report.believed_species == "Agaricus campestris"


def test_an_empty_report_is_accepted_rather_than_refused(client):
    """The form must not argue with someone trying to report a problem.

    A report with nothing filled in is close to useless and still better than
    a user who gave up at a validation error.
    """
    response = client.post("/incident", json={})
    assert response.status_code == 200
    assert response.json()["severity"] == "ordinary"


def test_free_text_is_capped(client):
    """Bounded, because this endpoint takes unauthenticated input."""
    assert client.post("/incident", json={"account": "x" * 4001}).status_code == 422
