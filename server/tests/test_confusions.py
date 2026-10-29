"""What this model gets wrong, as opposed to what people confuse.

`taxonomy.dangerous_pairs()` comes from field guides. It is what the
interrogation engine asks about, what the companion book prints, and what a
mycologist will review. It is a claim about mushrooms.

A classifier confuses different things. Measured on run one, 2026-10-28:
**seven of its eight dangerous confusions were not registered pairs** --
including its worst, *Galerina marginata* called *Crepidotus cesatii* at
0.850. Nobody picks a *Crepidotus* thinking it is a funeral bell; a network
looking at a small brown thing on wood does. So the lethal-pair refusal
never fired on almost every mistake the model actually made, and the whole
protection there was the 2% deadly-mass rule.

These pin the second graph, and especially the ways it must NOT behave like
the first one.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from app.confusions import ConfusionGraph  # noqa: E402
from app.safety import SafetyLayer, Verdict  # noqa: E402
from app.taxonomy_service import TaxonomyService  # noqa: E402

GALERINA = "galerina-marginata"        # DEADLY
CREPIDOTUS = "crepidotus-cesatii"      # not a field lookalike of it
WOODTUFT = "kuehneromyces-mutabilis"   # IS a registered lookalike


@pytest.fixture(scope="module")
def taxonomy() -> TaxonomyService:
    return TaxonomyService.load(ROOT / "data" / "taxonomy.seed.json")


def _graph(tmp_path, pairs, checkpoint="best.pt") -> Path:
    path = tmp_path / "model-confusions.json"
    path.write_text(json.dumps({
        "generated": "2026-10-28", "checkpoint": checkpoint,
        "split": "test", "pairs": pairs,
    }), encoding="utf-8")
    return path


def test_without_a_graph_the_behaviour_is_exactly_what_it_was(taxonomy):
    """Absent must mean "the taxonomy alone", not "no pairs at all"."""
    empty = ConfusionGraph()
    assert not empty.loaded
    assert empty.as_pairs() == frozenset()

    layer = SafetyLayer(taxonomy, confusions=empty)
    ranked = [(CREPIDOTUS, 0.60), (GALERINA, 0.30), ("stereum-hirsutum", 0.10)]
    assert layer.straddles_dangerous_pair(ranked) is None


def test_a_confusion_pair_triggers_the_refusal(taxonomy, tmp_path):
    """Run one's worst confusion, which the taxonomy could not catch."""
    graph = ConfusionGraph.load(_graph(tmp_path, [{
        "deadly": GALERINA, "mistaken_for": CREPIDOTUS, "count": 2,
        "max_confidence": 0.850, "max_deadly_mass": 0.05,
        "also_a_field_lookalike": False,
    }]))
    layer = SafetyLayer(taxonomy, confusions=graph, confidence_threshold=0.69)
    ranked = [(CREPIDOTUS, 0.85), (GALERINA, 0.05), ("stereum-hirsutum", 0.10)]

    assert layer.straddles_dangerous_pair(ranked) is not None
    assessment = layer.assess(ranked)
    assert assessment.verdict is Verdict.DANGEROUS_GROUP, (
        "the model's own worst confusion must not be named at 0.85"
    )
    assert assessment.deadly_in_play


def test_an_empirical_pair_is_never_called_a_lookalike(taxonomy, tmp_path):
    """The text has to differ, because the claim does.

    "These are confused with each other in the field" is true of a taxonomy
    pair and is a FALSE statement about this one. Saying it anyway would
    teach a user a resemblance that does not exist, which is the opposite
    of what the app is for.
    """
    graph = ConfusionGraph.load(_graph(tmp_path, [{
        "deadly": GALERINA, "mistaken_for": CREPIDOTUS, "count": 2,
        "max_confidence": 0.85, "max_deadly_mass": 0.05,
        "also_a_field_lookalike": False,
    }]))
    layer = SafetyLayer(taxonomy, confusions=graph)
    detail = layer.assess([(CREPIDOTUS, 0.85), (GALERINA, 0.05)]).detail

    assert "confused with each other in the field" not in detail
    assert "not lookalikes" in detail
    assert "can kill" in detail, "the hazard still has to be stated"


def test_a_real_field_pair_keeps_its_own_wording(taxonomy):
    """And the honest sentence survives for the case it is true of."""
    layer = SafetyLayer(taxonomy)
    ranked = [(WOODTUFT, 0.55), (GALERINA, 0.40)]
    assessment = layer.assess(ranked)
    assert assessment.verdict is Verdict.DANGEROUS_GROUP
    assert "confused with each other in the field" in assessment.detail


def test_a_graph_from_another_checkpoint_is_ignored(taxonomy, tmp_path, caplog):
    """Worse than none: it would refuse pairs this model does not confuse
    while missing the ones it does, and read as though protection were live."""
    path = _graph(tmp_path, [{
        "deadly": GALERINA, "mistaken_for": CREPIDOTUS, "count": 9,
        "max_confidence": 0.9, "max_deadly_mass": 0.5,
        "also_a_field_lookalike": False,
    }], checkpoint="runs/old-run/best.pt")

    graph = ConfusionGraph.load(path, expected_checkpoint="runs/new-run/model.onnx")
    assert graph.as_pairs() == frozenset()
    assert not graph.loaded, "an ignored graph must not report itself loaded"


def test_a_matching_checkpoint_is_accepted(tmp_path):
    """Compared on the file name, so model.onnx and best.pt from the same
    run do not read as different models."""
    path = _graph(tmp_path, [], checkpoint="/pod/runs/baseline/model.onnx")
    graph = ConfusionGraph.load(path, expected_checkpoint="ml/runs/baseline/model.onnx")
    assert graph.loaded


def test_an_empty_graph_and_a_missing_one_are_different_claims(tmp_path):
    """A model with no dangerous confusions is a result. A model whose
    graph was never generated is an absence. Collapsing them would let an
    ungenerated graph read as a clean bill of health."""
    generated_but_clean = ConfusionGraph.load(_graph(tmp_path, []))
    never_generated = ConfusionGraph.load(tmp_path / "nothing-here.json")

    assert generated_but_clean.loaded and not generated_but_clean.pairs
    assert not never_generated.loaded and not never_generated.pairs


def test_the_graph_is_not_written_into_the_taxonomy():
    """The whole point of the second graph.

    `lookalikes` is a mycological claim a reviewer reads and the ebook
    prints from. If run one's confusions appear there, the safety layer was
    mended by making the mushroom data wrong.
    """
    taxonomy = json.loads(
        (ROOT / "data" / "taxonomy.seed.json").read_text(encoding="utf-8")
    )
    by_key = {s["key"]: s for s in taxonomy["species"]}
    assert CREPIDOTUS not in (by_key[GALERINA].get("lookalikes") or []), (
        "a model confusion has been written into the field-lookalike graph"
    )


def test_a_silent_confusion_is_kept_however_rare():
    """The whole point of the second graph, and it was wrong at first.

    `safety.py` warns when the deadly species hold 2% of the mass. A SILENT
    confusion is one below that line -- the case the mass rule cannot see,
    and the one this graph's rank-based pair rule is the only cover for.

    The first version kept a single occurrence only if its deadly mass
    cleared `--min-mass 0.10`, which keeps what the mass rule already
    handles and drops what nothing handles. Measured on run four: all three
    pairs it kept were single high-mass confusions, and **both silent ones
    were filtered out**.

    Read from source because running it needs numpy, a taxonomy and a
    predictions file; what is pinned is that `silent` short-circuits the
    thresholds rather than being one more term they can outvote.
    """
    source = (ROOT / "scripts" / "confusion_graph.py").read_text(encoding="utf-8")
    block = source.split("kept = (")[1].split(")")[0]
    assert block.strip().startswith("silent"), (
        "a silent confusion must be kept before any count or mass threshold "
        "is consulted -- it is the case nothing else catches"
    )
    assert "min_count" in block and "min_mass" in block, (
        "the ordinary thresholds must still apply to non-silent confusions"
    )


def test_the_graph_records_how_many_were_silent():
    """A reader has to be able to tell which pairs are there because the
    mass rule would have missed them."""
    source = (ROOT / "scripts" / "confusion_graph.py").read_text(encoding="utf-8")
    assert '"silent": stats["silent"]' in source, (
        "the written graph must carry the silent count per pair"
    )
    assert "DEADLY_MASS_THRESHOLD" in source, (
        "silence must be judged against safety.py's own 2%, not a local copy"
    )


def test_the_graph_never_claims_cover_it_does_not_provide():
    """Recording a silent confusion is not the same as covering it.

    `straddles_dangerous_pair` reads `ranked[:5]`. A pair whose deadly
    species sits below that window is written into the graph and never
    consulted, so the entry protects nobody.

    The summary used to print "N silent confusion(s) are covered by this
    graph" from the recorded count alone. On run four that line said 2 and
    the true figure was **0**: *Inocybe erubescens* was at rank 40 and
    *Lepiota subincarnata* at rank 21. Simulated through the real
    `SafetyLayer`, the graph changed neither verdict.

    Same shape as `frdbi_gap.py` printing its intruder warning and then a
    hardcoded all-clear forty lines later. A report must not reassure past
    its own warning.
    """
    source = (ROOT / "scripts" / "confusion_graph.py").read_text(encoding="utf-8")
    assert "are covered by this graph" not in source, (
        "the old unconditional claim is back -- cover must be measured "
        "against the rank window, not assumed from the recorded count"
    )
    assert "silent_in_reach" in source, (
        "the script must count how many silent confusions are actually "
        "inside the window the pair rule reads"
    )
    assert "NOT COVERED BY ANYTHING" in source, (
        "a silent confusion outside the rank window is covered by neither "
        "the mass rule nor the pair rule, and must be reported as such"
    )


def test_the_scripts_rank_window_matches_the_safety_layers():
    """The pair rule's `top_n` is duplicated in the script, like the 2%.

    `ml/` and `server/` are separate packages with no import path between
    them, so the script carries its own copy. If `safety.py` widens the
    window and the copy does not, the graph reports pairs as uncovered that
    are now reached -- or, worse, the reverse.
    """
    import re

    safety = (ROOT / "server" / "app" / "safety.py").read_text(encoding="utf-8")
    match = re.search(r"def straddles_dangerous_pair\([^)]*top_n: int = (\d+)",
                      safety, re.S)
    assert match, "could not find the pair rule's rank window in safety.py"

    script = (ROOT / "scripts" / "confusion_graph.py").read_text(encoding="utf-8")
    copy = re.search(r"PAIR_RULE_TOP_N = (\d+)", script)
    assert copy, "the script must name the rank window it is reasoning about"
    assert int(copy.group(1)) == int(match.group(1)), (
        f"safety.py reads the top {match.group(1)} but confusion_graph.py "
        f"assumes {copy.group(1)} -- the coverage report is measuring a "
        f"window the app does not use"
    )


def test_a_graph_survives_the_export_of_its_own_checkpoint():
    """best.pt and model.onnx from one run are ONE model.

    A run trains `best.pt` and exports `model.onnx` from it. The graph is
    generated from the first and the server is handed the second, so a
    comparison that calls them different models discards the graph exactly
    when a real model is first installed -- every pair the safety layer had
    been given withdrawn, logged as if a stale graph had been caught.

    That is what `Path(...).name` did, and the test meant to pin it passed
    because it compared `model.onnx` against `model.onnx`. Measured on run
    four before it could happen: loaded=False, pairs=0.
    """
    graph = ConfusionGraph.load(
        ROOT / "data" / "model-confusions.json",
        expected_checkpoint="ml/runs/run4-b32/model.onnx",
    )
    assert graph.loaded, (
        "the graph was generated from this run's best.pt and must be "
        "accepted for the model.onnx exported from it"
    )
    assert graph.pairs, "a graph that loads with no pairs is not this one"


def test_the_served_run_is_the_one_whose_graph_was_generated():
    """The three installed files and the graph must name one run.

    `config.py` points at a run directory; `data/model-confusions.json`
    records the checkpoint it was built from. If they drift the graph is
    refused at startup and `/health` reports `confusions_loaded: false`
    while everything else looks healthy.
    """
    import json as _json
    import sys as _sys

    _sys.path.insert(0, str(ROOT / "server"))
    from app.config import Settings

    blob = _json.loads(
        (ROOT / "data" / "model-confusions.json").read_text(encoding="utf-8")
    )
    served = Path(Settings().model_path).parent.name
    generated = Path(blob["checkpoint"]).parent.name
    assert served == generated, (
        f"the server is configured to serve run {served!r} but the confusion "
        f"graph was generated from run {generated!r} -- regenerate the graph "
        f"from the served run's predictions.npz, or repoint config.py"
    )
