"""The page is a recording, and its captions must not drift from it.

`docs/walkthrough.html` is the most-shared surface this project has: a link
somebody can open on a phone without running anything. It works by replaying
`docs/walkthrough.json` -- every verdict, warning, candidate row and question
on it came out of the real server -- rather than by reimplementing the safety
layer in JavaScript, because two copies of that logic would drift apart
silently and in the one place this project cannot afford it.

A recording cannot drift. Its *captions* can, and on 2026-10-29 they had.
The page said the leading candidate "leads at twenty-four per cent" when the
recording beside it said 44%, and it stated rule 3's trigger as two per cent
a day after the app moved to one. Nothing in the repository noticed, because
the prose is hand-written HTML and the recording is a JSON blob, and nothing
compared them.

These tests are the comparison. They are deliberately source-level: the page
has no build step, so what is in the file is what a reader gets.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "docs" / "walkthrough.html"
SAFETY = ROOT / "server" / "app" / "safety.py"


def _page() -> str:
    return PAGE.read_text(encoding="utf-8")


def _recording() -> dict:
    """The JSON the page replays, read out of the page itself."""
    match = re.search(
        r'<script id="walkthrough" type="application/json">(.*?)</script>',
        _page(), re.S,
    )
    assert match, "the page has lost its recording block"
    return json.loads(match.group(1).replace("<\\/", "</"))


def test_the_stated_threshold_is_the_one_the_app_uses():
    """Rule 3's number on the page against safety.py's own default.

    This is the figure a reader is most likely to quote back, and it moved
    from 2% to 1% on 2026-10-29 because run four's test split produced two
    photographs of deadly mushrooms shown with no hazard line at all, both
    just under the old line. The page kept saying two.
    """
    source = SAFETY.read_text(encoding="utf-8")
    match = re.search(r"dangerous_mass_threshold: float = ([0-9.]+)", source)
    assert match, "safety.py no longer declares dangerous_mass_threshold"
    threshold = float(match.group(1))

    stated = re.search(r'id="rule3-threshold">([^<]+)<', _page())
    assert stated, "the page no longer marks the threshold it states"
    assert stated.group(1).strip() == f"{threshold * 100:g}%", (
        f"the page says {stated.group(1)!r} and the app warns at "
        f"{threshold * 100:g}% -- rule 3 misquoted on the page most likely "
        f"to be read by somebody who will never run the app"
    )


def test_no_hazard_label_exists_for_the_category_that_renders_nothing():
    """Rule 1, on the page rather than in the app.

    `NO_RECORDED_TOXICITY` is never rendered: that species shows a name and
    nothing else. The page's hazard map therefore has no entry for it, and
    an edit adding one "for completeness" would break rule 1 on the most
    shared surface the project has.
    """
    page = _page()
    hazard = re.search(r"var HAZARD = \{(.*?)\};", page, re.S)
    assert hazard, "the page's hazard map has moved or gone"
    assert "NO_RECORDED_TOXICITY" not in hazard.group(1), (
        "the page would print a hazard line for a species the app says "
        "nothing about"
    )
    # The page's own prose, with the recording taken out: what the server
    # said is covered by the disclaimer's own tests, and quoting it here
    # would make this one fail on the app's correct refusals.
    prose = re.sub(
        r'<script id="walkthrough".*?</script>', "", page, flags=re.S
    )
    # It may NAME the phrases rule 1 forbids -- explaining the rule is half
    # its job -- but only inside quotation marks, as something the app
    # refuses to say. An unquoted one would be the page saying it.
    unquoted = re.sub(r"&ldquo;.*?&rdquo;", "", prose, flags=re.S)
    for banned in ("not assessed as safe", "inedible", "Inedible",
                   "is edible", "are edible"):
        assert banned not in unquoted, (
            f"the page states {banned!r} outside quotation marks, which is "
            f"rule 1 broken rather than explained"
        )


def test_the_captions_read_their_numbers_off_the_recording():
    """Rather than restating them, which is how they went stale.

    The three captions that quote a figure are functions of their own scene.
    A flat string here would compile and render and be wrong the first time
    anybody re-captured.
    """
    page = _page()
    notes = re.search(r"var NOTES = \{(.*?)\n  \};", page, re.S)
    assert notes, "the page's captions have moved or gone"
    block = notes.group(1)
    for verdict in ("species", "uncertain", "dangerous_group"):
        assert re.search(rf"\n    {verdict}: function", block), (
            f"the {verdict} caption is a flat string again -- it quotes a "
            f"figure from the recording and will go stale on the next capture"
        )
    for spelled in ("twenty-four per cent", "twenty-six per cent",
                    "Five of the eight"):
        assert spelled not in block, (
            f"{spelled!r} is written into a caption rather than read off the "
            f"recording"
        )


def test_the_page_stamps_the_capture_it_is_showing():
    """A recording can only go stale, and it has to say when it was made."""
    page = _page()
    assert "DATA.captured_at" in page, (
        "the capture date is no longer taken from the recording, so the page "
        "would date itself by whatever was last typed into the HTML"
    )
    assert _recording()["captured_at"], "the recording carries no timestamp"


def test_the_phone_mock_shows_the_header_the_app_actually_has():
    """It carried a red emergency cross until Martin asked for it off.

    A mock-up that keeps a control the app no longer has is a picture of
    something nobody can press, and this page's whole claim is that it is a
    recording rather than a drawing.
    """
    page = _page()
    head = re.search(r'<div class="phone-head">(.*?)</div>\s*</div>', page, re.S)
    assert head, "the phone header has moved or gone"
    assert 'class="sos"' not in head.group(1), (
        "the mock-up still draws the emergency cross that was removed from "
        "the app header on 2026-10-29"
    )


def test_the_genus_refusal_reads_as_english():
    """"a Amanita" was in the shipped copy, the recording and the ebook.

    Cosmetic, and with a reach out of proportion to that: every
    genus-level refusal runs through one f-string, and four of the label
    space's commonest genera begin with a vowel -- Amanita, Inocybe,
    Entoloma, Armillaria. The sentence that says "I will not name the
    species" is the wrong one to have a typo in.
    """
    import sys

    sys.path.insert(0, str(ROOT / "server"))
    from app.safety import _an

    assert _an("Amanita") == "an Amanita"
    assert _an("Russula") == "a Russula"
    assert _an("Inocybe") == "an Inocybe"
