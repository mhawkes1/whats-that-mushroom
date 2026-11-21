"""`taxonomy_reviewed` is the one flag that gates a public release.

It was `bool(reviewed_by)`. Every string below is truthy, so every one of
them used to turn it on -- including the worksheet's own machine tags,
which mark the rows a reviewer has NOT yet read.

The asymmetry is the whole point. False is the safe value and costs
nothing but a disclaimer; true asserts that a qualified mycologist has
read 1,363 rows of toxicity data and field characters, and it is what
stops the app saying so to a user. Nobody sets that deliberately by
accident. Somebody very easily types a note into the field.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from app.main import _is_a_reviewer, _taxonomy_reviewed  # noqa: E402
from app.config import settings  # noqa: E402


NOT_REVIEWERS = [
    "", "   ", "TODO", "to do", "tbd", "TBA", "pending", "none", "None",
    "null", "n/a", "N/A", "no", "not yet", "nobody", "unreviewed",
    "unknown", "someone", "test", "x", "xxx", "?", "-", "--", "false", "0",
    ".", " . ", "12", "   todo   ",
    # The worksheet's own tags for machine-filled rows. 165 of the 1,363
    # rows carry one of these, and they are the argument FOR the review,
    # not a record of one.
    "unreviewed-seed-fill", "claude-option-widening", "claude-top250-batch",
    # Not strings at all.
    True, 1, [], {}, 0.5,
]

REVIEWERS = [
    "Chris Knowles",
    "Dr C. Knowles, FBMS",
    "chris knowles",
    "  Chris Knowles  ",
    "Knowles",
]


@pytest.mark.parametrize("value", NOT_REVIEWERS)
def test_these_do_not_count_as_a_reviewer(value: object) -> None:
    assert _is_a_reviewer(value) is False, f"{value!r} must not read as a reviewer"


@pytest.mark.parametrize("value", REVIEWERS)
def test_a_name_counts(value: str) -> None:
    assert _is_a_reviewer(value) is True


def test_the_committed_taxonomy_is_not_reviewed() -> None:
    """The release blocker itself. If this ever passes by accident, the app
    stops telling users the data is unverified."""
    assert _taxonomy_reviewed() is False


def test_a_placeholder_is_refused_and_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Refusing in silence would read, to whoever typed it, as the check
    passing. The operator meant something to happen."""
    data = json.loads(settings.taxonomy_path.read_text(encoding="utf-8"))
    data["reviewed_by"] = "TODO"
    fake = tmp_path / "taxonomy.json"
    fake.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(settings, "taxonomy_path", fake)

    with caplog.at_level(logging.ERROR):
        assert _taxonomy_reviewed() is False
    assert "TODO" in caplog.text
    assert "not a reviewer" in caplog.text


def test_a_real_name_turns_it_on(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The check has to be passable, or it is theatre rather than a gate."""
    data = json.loads(settings.taxonomy_path.read_text(encoding="utf-8"))
    data["reviewed_by"] = "Chris Knowles"
    fake = tmp_path / "taxonomy.json"
    fake.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(settings, "taxonomy_path", fake)
    assert _taxonomy_reviewed() is True


def test_one_real_name_among_the_machine_tags_is_enough(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A taxonomy can be signed by more than one person, and the rows a
    machine filled are still rows a person then read."""
    data = json.loads(settings.taxonomy_path.read_text(encoding="utf-8"))
    data["reviewed_by"] = ["claude-top250-batch", "Chris Knowles"]
    fake = tmp_path / "taxonomy.json"
    fake.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(settings, "taxonomy_path", fake)
    assert _taxonomy_reviewed() is True


def test_a_list_of_only_machine_tags_is_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = json.loads(settings.taxonomy_path.read_text(encoding="utf-8"))
    data["reviewed_by"] = ["claude-top250-batch", "unreviewed-seed-fill"]
    fake = tmp_path / "taxonomy.json"
    fake.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(settings, "taxonomy_path", fake)
    assert _taxonomy_reviewed() is False
