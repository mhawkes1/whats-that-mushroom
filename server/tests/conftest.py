"""Shared fixtures for the server tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))


@pytest.fixture(autouse=True)
def _reset_incident_rate_limiter():
    """Give every test a fresh quota on `POST /incident`.

    The limiter is process-wide by design, so without this the eighth test
    in a module to file a report starts failing because the third one used
    the allowance -- a failure that looks like a bug in whatever test
    happens to run last and moves whenever tests are reordered.

    Resetting rather than disabling: the limit stays live, so a test that
    files more reports than a real client would still meets it.
    """
    from app.main import incident_limiter

    incident_limiter.reset()
    yield
    incident_limiter.reset()
