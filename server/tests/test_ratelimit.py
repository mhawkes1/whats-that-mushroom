"""Rate limiting on the one unauthenticated write route.

The property that matters most here is the exemption, not the limit. A
limiter that quietly discards a report saying someone has eaten something
would turn the route that must always work into the one that fails under
exactly the conditions that produce a flood -- so most of this file is
about the ways that could happen.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from app.incidents import IncidentStore  # noqa: E402
from app.main import app, incident_limiter  # noqa: E402
from app.ratelimit import RateLimiter, client_key  # noqa: E402


# The limiter is reset between tests by the autouse fixture in conftest.py.


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _report(**overrides) -> dict:
    body = {
        "observation_id": "obs-1",
        "verdict": "species",
        "reported_candidates": ["amanita-phalloides"],
        "model_version": "0.1.0",
        "calibrated": False,
        "believed_species_key": "agaricus-campestris",
        "account": "The app said death cap and I think it was a field mushroom.",
        "anyone_ate_it": False,
        "anyone_unwell": False,
        "contact": None,
    }
    body.update(overrides)
    return body


# --- The exemption ----------------------------------------------------------


def test_a_medical_report_is_never_rate_limited(client):
    """The whole reason this file is longer than the module it tests.

    Someone whose child has eaten something may submit repeatedly, from a
    bad signal, in a panic. Every one of those must land.
    """
    for _ in range(incident_limiter.limit + 5):
        r = client.post("/incident", json=_report())
    assert r.status_code == 429, "precondition: the ordinary limit is reached"

    for i in range(20):
        r = client.post("/incident", json=_report(anyone_ate_it=True))
        assert r.status_code == 200, f"medical report {i} was refused"
        assert r.json()["medical_emergency"] is True
        assert r.json()["emergency_guidance"]


def test_unwell_alone_is_also_exempt(client):
    """Both flags, not just the one about eating.

    Somebody can be unwell without anyone admitting to a meal.
    """
    for _ in range(incident_limiter.limit + 2):
        client.post("/incident", json=_report())

    r = client.post("/incident", json=_report(anyone_unwell=True))
    assert r.status_code == 200
    assert r.json()["medical_emergency"] is True


def test_a_medical_report_does_not_consume_the_ordinary_quota(client):
    """The exemption must not be a loophole in the other direction either.

    If medical reports counted toward the limit, a genuine emergency would
    lock the reporter out of filing the ordinary defect report afterwards.
    """
    for _ in range(incident_limiter.limit + 3):
        client.post("/incident", json=_report(anyone_ate_it=True))

    r = client.post("/incident", json=_report())
    assert r.status_code == 200


# --- The limit --------------------------------------------------------------


def test_ordinary_reports_are_limited(client):
    ok = 0
    for _ in range(incident_limiter.limit + 3):
        if client.post("/incident", json=_report()).status_code == 200:
            ok += 1
    assert ok == incident_limiter.limit


def test_a_refusal_says_when_to_come_back_and_how_to_get_through(client):
    for _ in range(incident_limiter.limit):
        client.post("/incident", json=_report())
    r = client.post("/incident", json=_report())

    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) >= 1
    # The refusal must not leave a frightened person believing the route is
    # shut. It names the way through.
    assert "unwell" in r.json()["detail"].lower()


def test_the_limit_is_per_client(client):
    for _ in range(incident_limiter.limit):
        client.post("/incident", json=_report())
    assert client.post("/incident", json=_report()).status_code == 429

    # A different peer is a different bucket. TestClient does not vary the
    # peer address, so this exercises the limiter directly.
    assert incident_limiter.allow("198.51.100.7")


# --- The limiter itself -----------------------------------------------------


def test_a_refused_attempt_is_not_counted():
    """Otherwise a client that keeps retrying can never recover.

    A buggy client in a retry loop would hold itself out forever, which
    punishes the broken caller far harder than the malicious one -- the
    malicious one changes address.
    """
    limiter = RateLimiter(limit=2, window_seconds=100)
    assert limiter.allow("a", now=0)
    assert limiter.allow("a", now=1)
    for t in range(2, 50):
        assert not limiter.allow("a", now=t)
    # The window is measured from the two accepted hits, not from the
    # fiftieth refusal.
    assert limiter.allow("a", now=101)


def test_hits_expire_out_of_the_window():
    limiter = RateLimiter(limit=2, window_seconds=10)
    assert limiter.allow("a", now=0)
    assert limiter.allow("a", now=1)
    assert not limiter.allow("a", now=5)
    assert limiter.allow("a", now=10.1)   # the first has aged out
    assert limiter.allow("a", now=11.1)   # and then the second


def test_retry_after_is_whole_seconds_and_never_zero_while_blocked():
    limiter = RateLimiter(limit=1, window_seconds=60)
    limiter.allow("a", now=0)
    assert limiter.retry_after("a", now=0.5) == 60
    assert limiter.retry_after("a", now=59.9) == 1
    assert limiter.retry_after("unseen", now=0) == 0


def test_a_degenerate_limiter_is_refused():
    with pytest.raises(ValueError):
        RateLimiter(limit=0, window_seconds=60)
    with pytest.raises(ValueError):
        RateLimiter(limit=5, window_seconds=0)


# --- Which address is counted ----------------------------------------------


def test_a_forwarded_header_is_ignored_unless_the_deployment_trusts_it():
    """A limiter anyone can opt out of is worse than none.

    `X-Forwarded-For` is caller-supplied. Honouring it by default would
    hand an attacker a fresh quota per request while reading, to anyone
    looking at the config, as protection.
    """
    spoofed = "203.0.113.9"
    assert client_key("10.0.0.1", spoofed, trust_forwarded_for=False) == "10.0.0.1"
    assert client_key("10.0.0.1", spoofed, trust_forwarded_for=True) == spoofed


def test_the_first_forwarded_entry_is_the_client():
    chain = "203.0.113.9, 70.41.3.18, 150.172.238.178"
    assert client_key("10.0.0.1", chain, trust_forwarded_for=True) == "203.0.113.9"


def test_a_missing_peer_shares_one_bucket_rather_than_being_waved_through():
    assert client_key(None, None, trust_forwarded_for=False) == "unknown"
    assert client_key(None, "   ", trust_forwarded_for=True) == "unknown"


# --- Telling a reporter what happened ---------------------------------------


def test_a_reporter_can_look_up_their_own_report(client):
    """`docs/INCIDENTS.md` listed this as blocking for release.

    The id is the whole credential: no account, no email, no contact
    address. That is the privacy answer as much as the engineering one --
    the alternative was storing an address in order to write to it later,
    which means holding personal data on somebody whose only involvement
    was telling us we were wrong.
    """
    filed = client.post("/incident", json=_report()).json()
    r = client.get(f"/incident/{filed['incident_id']}")

    assert r.status_code == 200
    body = r.json()
    assert body["incident_id"] == filed["incident_id"]
    assert body["outcome"] == "received"
    assert body["closed"] is False
    assert body["public_note"]


def test_the_status_discloses_nothing_about_the_reporter(client):
    """Written for a reader who may not be the person who filed it.

    A uuid4 is not guessable, but it is exactly the sort of string someone
    pastes into a forum thread. So the response carries an outcome and a
    note a person wrote, and none of: the reporter's own free text, their
    contact details, the species they named, or what the app said.
    """
    secret_account = "I am Martin and my number is 07700 900000"
    filed = client.post(
        "/incident",
        json=_report(
            account=secret_account,
            contact="martin@example.com",
            believed_species_key="amanita-phalloides",
        ),
    ).json()

    body = client.get(f"/incident/{filed['incident_id']}").text

    assert "07700" not in body
    assert "martin@example.com" not in body
    assert "Martin" not in body
    assert "phalloides" not in body
    assert "amanita" not in body.lower()


def test_an_unknown_reference_is_a_plain_404(client):
    assert client.get("/incident/not-a-real-id").status_code == 404
    assert client.get("/incident/" + "0" * 32).status_code == 404


def test_a_medical_report_is_never_shown_a_ticket_state(client):
    """It is not a defect report, so it does not get a defect status.

    `docs/INCIDENTS.md`: nothing is owed to the codebase here and
    everything is owed to the person. A status page reading "investigating"
    at somebody who said their child had eaten something would be the same
    mistake as the confirmation text that thanks people for their feedback.
    """
    filed = client.post("/incident", json=_report(anyone_ate_it=True)).json()
    body = client.get(f"/incident/{filed['incident_id']}").json()

    assert body["medical"] is True
    assert body["closed"] is True
    assert "not being tracked as a defect" in body["public_note"]
    assert "investigating" not in body["public_note"].lower()


def test_an_outcome_is_appended_and_never_overwrites_the_report(tmp_path):
    """The log is evidence, and that applies to the outcome too.

    A status silently changed from "fixed" to "no change" is precisely the
    record nobody could trust, so both lines survive and the history stays
    readable.
    """
    from datetime import datetime, timezone

    from app.incidents import IncidentStore, IncidentUpdate, Outcome, build_report
    from app.taxonomy_service import TaxonomyService

    taxonomy = TaxonomyService.load(ROOT / "data" / "taxonomy.seed.json")
    store = IncidentStore(tmp_path / "incidents.jsonl")
    report = store.append(
        build_report(
            taxonomy=taxonomy, observation_id="obs-1", verdict="species",
            reported_candidates=["agaricus-campestris"], model_version="0.1.0",
            calibrated=False, believed_species_key="amanita-phalloides",
            account="wrong", anyone_ate_it=False, anyone_unwell=False,
            contact=None,
        )
    )

    def answer(outcome: Outcome, note: str) -> None:
        store.append_update(
            IncidentUpdate(
                incident_id=report.incident_id,
                recorded_at=datetime.now(timezone.utc).isoformat(),
                outcome=outcome.value,
                public_note=note,
            )
        )

    answer(Outcome.INVESTIGATING, "Looking at this now.")
    answer(Outcome.FIXED, "You were right. The lookalike edge was missing.")

    # Both updates survive, and the report is untouched.
    assert len(store.updates()) == 2
    assert len(store.all()) == 1
    assert store.all()[0].account == "wrong"

    status = store.status(report.incident_id)
    assert status.outcome == "fixed"
    assert status.closed is True
    assert "lookalike edge" in status.public_note


def test_updates_do_not_contaminate_the_report_listing(tmp_path):
    """`all()` filters on the update marker, not on a report one.

    Reports written before updates existed carry no `record_type` at all,
    so a test for a *report* marker would have silently dropped every
    historical line.
    """
    import json

    path = tmp_path / "incidents.jsonl"
    legacy = {
        "incident_id": "old", "received_at": "2026-01-01T00:00:00+00:00",
        "severity": "ordinary", "observation_id": None, "verdict": None,
        "reported_candidates": [], "model_version": None, "calibrated": None,
        "believed_species": None, "believed_species_key": None,
        "account": "from before updates existed", "anyone_ate_it": False,
        "anyone_unwell": False, "contact": None, "notes": {},
    }
    path.write_text(json.dumps(legacy) + "\n")

    store = IncidentStore(tmp_path / "incidents.jsonl")
    assert len(store.all()) == 1
    assert store.all()[0].incident_id == "old"
    assert store.updates() == []
