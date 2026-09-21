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
    ranked = [("morchella-esculenta", 0.70), ("gyromitra-esculenta", 0.28), ("verpa-bohemica", 0.02)]
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


def test_field_notes_cannot_talk_the_safety_layer_into_naming_a_species():
    """CLAUDE.md rule 2, under pressure from the evidence mechanism.

    Describing the safe half of a lethal pair gave a user's answers the power
    to push mass toward the harmless lookalike. That is the point of it, but
    it also creates the route by which a run of favourable answers might talk
    the app into a species-level answer on a confusion it has no business
    resolving.

    Galerina marginata and Kuehneromyces mutabilis are the worst case: the
    taxonomy's own notes call them the single most dangerous confusion for
    experienced foragers. However far the answers favour the woodtuft, the
    verdict must stay a refusal.
    """
    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(ROOT / "server"))

    from app.config import settings
    from app.evidence import reweight
    from app.taxonomy_service import TaxonomyService

    taxonomy = TaxonomyService.load(settings.taxonomy_path)
    safety = SafetyLayer(taxonomy, confidence_threshold=0.80)

    funeral_bell, woodtuft = "galerina-marginata", "kuehneromyces-mutabilis"
    ranked = [(woodtuft, 0.5), (funeral_bell, 0.5)] + [
        (key, 0.0) for key in taxonomy.species if key not in (woodtuft, funeral_bell)
    ]

    for _ in range(4):
        for character, answer in [
            ("stipe_surface", "Scaly or shaggy"),
            ("cap_surface", "Smooth and dry"),
        ]:
            ranked = reweight(ranked, character, answer, taxonomy)
        assessment = safety.assess(ranked)
        assert assessment.verdict is not Verdict.SPECIES, (
            f"named a species with a funeral bell still at "
            f"{dict(ranked)[funeral_bell]:.3f}"
        )
