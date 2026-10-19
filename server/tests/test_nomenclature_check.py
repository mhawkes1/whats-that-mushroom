"""Offline tests for `scripts/nomenclature_check.py`.

The script's job is to take the nomenclature half of the review sheet away
from a human, so the thing that matters is that it does not hand back a
false all-clear. Every payload here is a real GBIF response shape, trimmed;
nothing in this file touches the network.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "nomenclature_check", ROOT / "scripts" / "nomenclature_check.py"
    )
    module = importlib.util.module_from_spec(spec)
    # `Finding` is a dataclass with a `field(default_factory=...)`, and
    # dataclasses resolves that through sys.modules. Loading the script by
    # path without registering it raises AttributeError on NoneType.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script():
    return _script()


def _finding(script, name, toxicity="DEADLY"):
    return script.Finding(key="k", scientific_name=name, toxicity=toxicity)


def _stub(script, monkeypatch, responses):
    """Replace the one network call with a lookup table keyed on path."""

    def fake_get(_session, path, **params):
        for pattern, payload in responses.items():
            if pattern in path:
                return payload
        raise AssertionError(f"unexpected request: {path} {params}")

    monkeypatch.setattr(script, "get", fake_get)


# --- The failure nothing downstream could detect ----------------------------


def test_a_pinned_key_pointing_at_the_wrong_taxon_is_the_worst_flag(
    script, monkeypatch
):
    """A hand-set `gbif_key` is an override of the check that caught a problem.

    So the key itself has to be verified. If it names a different species,
    every image fetched under it carries the wrong label and the images
    really are mushrooms -- no accuracy figure, no loss curve and no
    eyeball on a sample would reveal it. This is the only flag ranked above
    the two sources disagreeing.
    """
    f = _finding(script, "Clitocybe dealbata")
    _stub(
        script,
        monkeypatch,
        {
            "/species/2531056": {
                "canonicalName": "Clitocybe rivulosa",
                "rank": "SPECIES",
            }
        },
    )
    script.check_pinned_key(None, {"gbif_key": 2531056}, f)

    assert f.flag == "PINNED_KEY_WRONG"
    assert "wrong label" in f.notes[-1]
    assert script.SEVERITY["PINNED_KEY_WRONG"] < script.SEVERITY["SOURCES_DISAGREE"]


def test_a_pinned_key_above_species_rank_is_refused(script, monkeypatch):
    """The *Helvella crispa* failure, had the key been pinned carelessly.

    Its name matched `usageKey: 5` -- the Fungi kingdom -- at confidence 99.
    A key pinned to that would fetch the entire kingdom under one label.
    """
    f = _finding(script, "Helvella crispa", toxicity="TOXIC")
    _stub(
        script,
        monkeypatch,
        {"/species/5": {"canonicalName": "Fungi", "rank": "KINGDOM"}},
    )
    script.check_pinned_key(None, {"gbif_key": 5}, f)

    assert f.flag == "PINNED_KEY_WRONG"
    assert "KINGDOM" in f.pinned_resolves_to


def test_a_sound_pinned_key_clears_a_complaint_about_the_name(script, monkeypatch):
    """*Helvella crispa* as it actually stands.

    Its name resolves to the kingdom, so the name check rightly objects --
    and the pinned key is the fix for exactly that. Leaving the objection
    standing would put a solved problem on the reviewer's sheet, which is
    the thing this script exists to avoid.
    """
    f = _finding(script, "Helvella crispa", toxicity="TOXIC")
    f.flag = "NOT_SPECIES_RANK"
    f.notes.append("backbone matched at rank KINGDOM, not SPECIES")
    _stub(
        script,
        monkeypatch,
        {"/species/2554614": {"canonicalName": "Helvella crispa", "rank": "SPECIES"}},
    )
    script.check_pinned_key(None, {"gbif_key": 2554614}, f)

    assert f.flag == "OK"
    assert "pinned by hand and resolves correctly" in f.notes[-1]


def test_a_sound_pinned_key_does_not_clear_a_synonym(script, monkeypatch):
    """A pinned key fixes a *resolution* failure, not a naming question.

    The name still being a synonym is an editorial decision about what the
    app displays, and the key resolving correctly says nothing about it.
    """
    f = _finding(script, "Inocybe erubescens")
    f.flag = "SYNONYM"
    f.backbone_accepted = "Inosperma erubescens"
    _stub(
        script,
        monkeypatch,
        {"/species/1": {"canonicalName": "Inocybe erubescens", "rank": "SPECIES"}},
    )
    script.check_pinned_key(None, {"gbif_key": 1}, f)

    assert f.flag == "SYNONYM"


# --- What the backbone check must refuse ------------------------------------


def test_a_match_above_species_rank_is_flagged_not_accepted(script, monkeypatch):
    f = _finding(script, "Helvella crispa", toxicity="TOXIC")
    _stub(
        script,
        monkeypatch,
        {
            "/species/match": {
                "usageKey": 5,
                "scientificName": "Fungi",
                "canonicalName": "Fungi",
                "rank": "KINGDOM",
                "status": "ACCEPTED",
                "confidence": 99,
                "matchType": "HIGHERRANK",
            }
        },
    )
    script.check_backbone(None, f.scientific_name, f)

    assert f.flag == "NOT_SPECIES_RANK"
    assert "no training data" in f.note or "no training data" in f.notes[-1]


def test_high_confidence_never_rescues_a_bad_match(script, monkeypatch):
    """Confidence 99 on the Fungi kingdom is the reason rank is checked first.

    `ml/fungi_ml/data/sources.py` learned this on the first live run. A
    second tool that trusted confidence would re-introduce the hole.
    """
    f = _finding(script, "Helvella crispa", toxicity="TOXIC")
    _stub(
        script,
        monkeypatch,
        {
            "/species/match": {
                "usageKey": 5,
                "canonicalName": "Fungi",
                "rank": "KINGDOM",
                "status": "ACCEPTED",
                "confidence": 99,
                "matchType": "EXACT",
            }
        },
    )
    script.check_backbone(None, f.scientific_name, f)
    assert f.flag != "OK"


def test_a_synonym_reports_the_accepted_name(script, monkeypatch):
    """*Inocybe erubescens*, DEADLY, EXACT at confidence 100 to a synonym."""
    f = _finding(script, "Inocybe erubescens")
    _stub(
        script,
        monkeypatch,
        {
            "/species/match": {
                "usageKey": 7574662,
                "acceptedUsageKey": 11100233,
                "canonicalName": "Inocybe erubescens",
                "rank": "SPECIES",
                "status": "SYNONYM",
                "confidence": 100,
                "matchType": "EXACT",
                "synonym": True,
            },
            "/species/11100233": {
                "canonicalName": "Inosperma erubescens",
                "rank": "SPECIES",
            },
        },
    )
    script.check_backbone(None, f.scientific_name, f)

    assert f.flag == "SYNONYM"
    assert f.backbone_accepted == "Inosperma erubescens"


# --- The only flag that needs a specialist ----------------------------------


def test_sources_disagreeing_outranks_a_plain_synonym(script):
    """Where both nomenclators agree, the row has its own answer.

    A disagreement does not, which is why it sorts above everything but a
    bad pinned key: it is the subset worth a reviewer's time.
    """
    f = _finding(script, "Example species")
    f.backbone_accepted = "Alpha beta"
    f.nomenclator_accepted = "Gamma delta"
    script.reconcile(f)

    assert f.flag == "SOURCES_DISAGREE"
    assert script.SEVERITY["SOURCES_DISAGREE"] < script.SEVERITY["SYNONYM"]


def test_a_backbone_merge_the_nomenclator_rejects_is_a_disagreement(script):
    """The shape of the *Clitocybe dealbata* argument.

    The backbone merges two names the nomenclator keeps apart. That is a
    taxonomic question, and the script must not quietly pick a side.
    """
    f = _finding(script, "Example species")
    f.backbone_accepted = "Alpha beta"
    f.nomenclator_status = "ACCEPTED"
    script.reconcile(f)

    assert f.flag == "SOURCES_DISAGREE"
    assert "still" in f.notes[-1]


def test_findings_sort_deadliest_first_within_a_flag(script):
    deadly = _finding(script, "Zeta zeta", toxicity="DEADLY")
    harmless = _finding(script, "Alpha alpha", toxicity="NO_RECORDED_TOXICITY")
    for f in (deadly, harmless):
        f.flag = "SYNONYM"

    assert sorted([harmless, deadly], key=script.Finding.sort_key)[0] is deadly


def test_canonical_drops_authorship(script):
    assert script.canonical("Amanita phalloides (Vaill. ex Fr.) Link") == (
        "Amanita phalloides"
    )
    assert script.canonical("Russula adusta (Pers.) Fr.") == "Russula adusta"
