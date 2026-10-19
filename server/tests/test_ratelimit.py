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
