"""Tests for the safety layer.

These are the tests that decide whether this app is safer than the ones it
competes with. Each encodes a scenario where a consumer app would confidently
say something that could get someone killed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from app.safety import SafetyLayer, Verdict  # noqa: E402
from app.taxonomy_service import TaxonomyService  # noqa: E402

SEED = ROOT / "data" / "taxonomy.seed.json"


@pytest.fixture(scope="module")
def taxonomy():
    return TaxonomyService.load(SEED)


@pytest.fixture
def layer(taxonomy):
    return SafetyLayer(taxonomy, confidence_threshold=0.80)


def test_confident_safe_identification_names_the_species(layer):
    ranked = [("hydnum-repandum", 0.94), ("cantharellus-cibarius", 0.04), ("boletus-edulis", 0.02)]
    result = layer.assess(ranked)
    assert result.verdict is Verdict.SPECIES
    assert "Hydnum repandum" in result.headline
    assert not result.deadly_in_play


def test_death_cap_versus_field_mushroom_refuses_to_choose(layer):
    """The textbook fatal confusion. A consumer app answers this; we must not."""
    ranked = [("agaricus-campestris", 0.72), ("amanita-phalloides", 0.24), ("agaricus-arvensis", 0.04)]
    result = layer.assess(ranked)

    assert result.verdict is Verdict.DANGEROUS_GROUP
    assert result.deadly_in_play
    assert "Agaricus campestris" not in result.headline, (
        "must not headline the edible candidate when a death cap is in play"
    )
    assert any("kill" in w.lower() for w in result.warnings)
    assert result.requested_evidence, "must ask for separating evidence"


def test_high_confidence_on_edible_still_warns_if_deadly_has_mass(layer):
    """Even at 90% on something harmless, a real death cap probability warns."""
    ranked = [("agaricus-campestris", 0.90), ("amanita-phalloides", 0.10)]
    result = layer.assess(ranked)
    assert result.deadly_in_play
    assert result.verdict is Verdict.DANGEROUS_GROUP


def test_tiny_deadly_probability_still_triggers_the_warning(layer):
    """2% on a death cap is not noise -- it is a 1-in-50 chance of death."""
    ranked = [("hydnum-repandum", 0.97), ("amanita-phalloides", 0.03)]
    result = layer.assess(ranked)
    assert result.deadly_in_play, "a 3% death cap probability must warn"


def test_funeral_bell_versus_woodtuft_refuses(layer):
    """Kills experienced foragers. Cannot be resolved from a photo."""
    ranked = [("kuehneromyces-mutabilis", 0.61), ("galerina-marginata", 0.33), ("armillaria-mellea", 0.06)]
    result = layer.assess(ranked)
    assert result.verdict is Verdict.DANGEROUS_GROUP
    assert "spore_print_colour" in result.requested_evidence


def test_false_morel_versus_true_morel_refuses(layer):
    ranked = [("morchella-esculenta", 0.70), ("gyromitra-esculenta", 0.28), ("morchella-elata", 0.02)]
    result = layer.assess(ranked)
    assert result.verdict is Verdict.DANGEROUS_GROUP
    assert result.deadly_in_play


def test_low_confidence_declines_to_name_anything(layer):
    ranked = [("russula-cyanoxantha", 0.22), ("russula-ochroleuca", 0.20), ("lepista-nuda", 0.19)]
    result = layer.assess(ranked)
    assert result.verdict in (Verdict.UNCERTAIN, Verdict.GROUP)
    assert "not sure" in result.headline.lower() or "looks like" in result.headline.lower()


def test_very_low_top_score_is_flagged_out_of_scope(layer):
    ranked = [("lepista-nuda", 0.11), ("russula-emetica", 0.10), ("boletus-edulis", 0.09)]
    result = layer.assess(ranked)
    assert result.verdict is Verdict.OUT_OF_SCOPE


def test_genus_confidence_without_species_confidence_reports_genus(layer):
    ranked = [("russula-cyanoxantha", 0.34), ("russula-ochroleuca", 0.30), ("russula-emetica", 0.14),
              ("hydnum-repandum", 0.12), ("boletus-edulis", 0.10)]
    result = layer.assess(ranked)
    assert result.verdict is Verdict.GROUP
    assert "Russula" in result.headline


def test_no_output_path_ever_asserts_edibility(layer, taxonomy):
    """No output may make an affirmative edibility claim.

    Scanning for the bare substring "safe to eat" is wrong: the standing
    disclaimer legitimately contains it inside a negation. What must never
    appear is an affirmative claim, so we scan for those patterns and check
    the negating context of any borderline phrase.
    """
    import re

    affirmative = [
        re.compile(r"\bis edible\b"),
        re.compile(r"\bare edible\b"),
        re.compile(r"\bedible\b(?!\s+lookalike)"),
        re.compile(r"\bgood to eat\b"),
        re.compile(r"\bchoice\b"),
        re.compile(r"\bsafe\b(?!ty)(?!r)"),
        re.compile(r"\byou can eat\b"),
        re.compile(r"\bfine to eat\b"),
    ]
    # Phrases allowed only inside an explicit negation.
    negated_ok = re.compile(
        r"(never|not|cannot|can't|does not|doesn't|whether)[^.]*\b(safe|edible|eat)\b"
    )

    scenarios = [
        [("hydnum-repandum", 0.95), ("boletus-edulis", 0.05)],
        [("agaricus-campestris", 0.88), ("agaricus-arvensis", 0.12)],
        [("amanita-phalloides", 0.60), ("agaricus-campestris", 0.40)],
        [("cantharellus-cibarius", 0.91), ("hygrophoropsis-aurantiaca", 0.09)],
        [("lepista-nuda", 0.15), ("russula-emetica", 0.14)],
        [("morchella-esculenta", 0.70), ("gyromitra-esculenta", 0.28)],
    ]
    for ranked in scenarios:
        result = layer.assess(ranked)
        for field_name, text in [
            ("headline", result.headline),
            ("detail", result.detail),
            *[("warning", w) for w in result.warnings],
        ]:
            lowered = text.lower()
            for pattern in affirmative:
                for match in pattern.finditer(lowered):
                    # Find the sentence containing the hit and require it to
                    # be a negation.
                    start = lowered.rfind(".", 0, match.start()) + 1
                    end = lowered.find(".", match.end())
                    sentence = lowered[start : end if end != -1 else len(lowered)]
                    assert negated_ok.search(sentence), (
                        f"affirmative edibility claim in {field_name}: {sentence.strip()!r}"
                    )


def test_species_notes_never_recommend_eating(taxonomy):
    """The seed taxonomy's own prose must not carry edibility advice either,
    since notes are surfaced verbatim as the detail text."""
    import re

    recommends = re.compile(r"\b(is edible|are edible|good edible|choice edible|safe to eat)\b")
    offenders = [
        (k, sp.notes) for k, sp in taxonomy.species.items() if recommends.search(sp.notes.lower())
    ]
    assert not offenders, f"species notes assert edibility: {[o[0] for o in offenders]}"


def test_every_assessment_carries_the_disclaimer(layer):
    scenarios = [
        [("hydnum-repandum", 0.99)],
        [("amanita-phalloides", 0.50), ("agaricus-campestris", 0.50)],
        [("lepista-nuda", 0.11), ("boletus-edulis", 0.10)],
        [],
    ]
    for ranked in scenarios:
        result = layer.assess(ranked)
        assert any("never eat" in w.lower() for w in result.warnings), (
            f"missing disclaimer for verdict {result.verdict}"
        )


def test_empty_candidate_list_is_handled(layer):
    result = layer.assess([])
    assert result.verdict is Verdict.OUT_OF_SCOPE
    assert result.candidates == []


def test_amanita_genus_mass_triggers_caution_even_without_a_named_deadly(layer):
    """A user cannot safely reason 'it's an Amanita, but a harmless one'."""
    ranked = [("amanita-rubescens", 0.55), ("amanita-muscaria", 0.40), ("boletus-edulis", 0.05)]
    result = layer.assess(ranked)
    assert result.verdict is Verdict.DANGEROUS_GROUP or result.deadly_in_play


def test_candidates_are_returned_with_toxicity_labels(layer):
    ranked = [("amanita-phalloides", 0.55), ("agaricus-campestris", 0.45)]
    result = layer.assess(ranked)
    toxicities = {c.species_key: c.toxicity for c in result.candidates}
    assert toxicities["amanita-phalloides"] == "DEADLY"


# --- species added after the first review pass ---------------------------


def test_small_lepiota_on_a_lawn_is_refused(layer):
    """The deadly dapplerlings grow in grass alongside the Fairy Ring
    Champignon, and both are small, pale and scaly. This is the confusion
    that makes the small Lepiota species worth carrying at all."""
    ranked = [
        ("marasmius-oreades", 0.51),
        ("lepiota-brunneoincarnata", 0.28),
        ("lepiota-cristata", 0.13),
        ("agaricus-campestris", 0.08),
    ]
    result = layer.assess(ranked)
    assert result.verdict is Verdict.DANGEROUS_GROUP
    assert result.deadly_in_play
    assert "Marasmius" not in result.headline, (
        "must not headline the harmless candidate when a deadly Lepiota is in play"
    )


def test_small_parasol_confusion_is_refused(layer):
    """Someone who knows Parasols are collected may assume a small one is
    the same thing. It is the single most plausible route into a deadly
    Lepiota."""
    ranked = [
        ("macrolepiota-procera", 0.58),
        ("lepiota-brunneoincarnata", 0.31),
        ("chlorophyllum-rhacodes", 0.11),
    ]
    result = layer.assess(ranked)
    assert result.verdict is Verdict.DANGEROUS_GROUP
    assert result.deadly_in_play
    assert result.requested_evidence


def test_all_deadly_lepiota_candidates_still_warn(layer):
    """When every candidate is a deadly Lepiota the app may name one.

    Naming a deadly species is the cautious direction, not the fatal one, and
    the warning is what carries the meaning. Refusing here would add no
    safety. Note the separate honesty question recorded in docs/ROADMAP.md:
    the small Lepiota species cannot actually be separated from a photograph,
    so a species-level headline claims more precision than exists.
    """
    ranked = [
        ("lepiota-brunneoincarnata", 0.88),
        ("lepiota-subincarnata", 0.09),
        ("lepiota-castanea", 0.03),
    ]
    result = layer.assess(ranked)
    assert result.deadly_in_play
    assert any("kill" in w.lower() for w in result.warnings)
    # Whatever the verdict, the named species must itself be a deadly one --
    # never a harmless neighbour.
    assert result.candidates[0].toxicity == "DEADLY"


def test_panther_cap_versus_blusher_warns(layer):
    """Amanita pantherina and A. rubescens are a classic and serious
    confusion. The app need not refuse outright -- pantherina is SERIOUS
    rather than DEADLY -- but it must warn and must not name a species."""
    ranked = [
        ("amanita-rubescens", 0.55),
        ("amanita-pantherina", 0.40),
        ("amanita-muscaria", 0.05),
    ]
    result = layer.assess(ranked)
    assert result.verdict is not Verdict.SPECIES
    assert result.deadly_in_play, "any Amanita ambiguity must carry the warning"


def test_genus_headline_uses_the_correct_article(layer):
    """'a Amanita' on the one screen the user must trust reads as carelessness."""
    ranked = [
        ("amanita-rubescens", 0.35), ("amanita-pantherina", 0.30),
        ("amanita-muscaria", 0.20), ("boletus-edulis", 0.15),
    ]
    headline = layer.assess(ranked).headline
    if "species" in headline and "looks like" in headline:
        assert "a Amanita" not in headline
        assert "an Amanita" in headline


def test_new_species_carry_toxicity_labels(layer):
    ranked = [("lepiota-brunneoincarnata", 0.6), ("marasmius-oreades", 0.4)]
    by_key = {c.species_key: c.toxicity for c in layer.assess(ranked).candidates}
    assert by_key["lepiota-brunneoincarnata"] == "DEADLY"


def test_orellanus_chanterelle_confusion_is_refused(layer):
    """Both orellanine webcaps are orange-brown and grow where people hunt
    chanterelles. Orellanine destroys the kidneys two to three weeks later,
    by which point the victim no longer connects the illness to the meal."""
    ranked = [
        ("cantharellus-cibarius", 0.56),
        ("cortinarius-orellanus", 0.27),
        ("hygrophoropsis-aurantiaca", 0.12),
        ("cortinarius-rubellus", 0.05),
    ]
    result = layer.assess(ranked)
    assert result.verdict is Verdict.DANGEROUS_GROUP
    assert result.deadly_in_play
    assert "Cantharellus" not in result.headline, (
        "must not headline the chanterelle when a webcap is in play"
    )
    # The decisive check is what is under the cap: true gills, or the blunt
    # forking ridges of a chanterelle.
    assert "gill_type" in result.requested_evidence


def test_both_orellanine_webcaps_together_still_warn(layer):
    ranked = [
        ("cortinarius-orellanus", 0.52),
        ("cortinarius-rubellus", 0.44),
        ("cortinarius-violaceus", 0.04),
    ]
    result = layer.assess(ranked)
    assert result.deadly_in_play
    assert result.candidates[0].toxicity == "DEADLY"
