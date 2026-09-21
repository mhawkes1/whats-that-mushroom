"""The QA pass, run as a test so data defects fail CI rather than shipping.

The bug this suite exists to prevent: the seed taxonomy once recorded
*Boletus edulis* -- the Penny Bun -- as INEDIBLE, because the bottom of the
toxicity scale had been named after a claim instead of an absence of one.
It was structurally valid, passed every test, and was obviously wrong to
anyone who had ever picked one.

That class of defect is not caught by schema validation. It needs checks
that compare a field against what the rest of the record implies.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml"))

from fungi_ml.taxonomy import Taxonomy, Toxicity  # noqa: E402

SEED = ROOT / "data" / "taxonomy.seed.json"


@pytest.fixture(scope="module")
def raw() -> dict:
    return json.loads(SEED.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def taxonomy() -> Taxonomy:
    return Taxonomy.load(SEED)


def test_qa_script_reports_no_errors():
    """The full QA pass must be clean. Warnings are allowed; errors are not."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "qa_taxonomy.py")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"QA reported errors:\n{result.stdout}\n{result.stderr}"


def test_scale_contains_no_edibility_claim():
    """Neither direction. 'Edible' would be permission; 'inedible' would be
    a false statement about half the label space."""
    names = {t.name for t in Toxicity}
    assert "EDIBLE" not in names
    assert "INEDIBLE" not in names
    assert "NONE_RECORDED" in names


def test_known_choice_edibles_are_not_labelled_harmful(taxonomy):
    """Species widely collected and eaten must not carry a harm label.

    If one of these ever reads DEADLY/SERIOUS/TOXIC it is either a genuine
    reclassification that needs a source, or -- far more likely -- a data
    entry error. Either way a human should look."""
    well_known = [
        "boletus-edulis", "cantharellus-cibarius", "hydnum-repandum",
        "morchella-esculenta", "craterellus-cornucopioides", "pleurotus-ostreatus",
        "calvatia-gigantea", "macrolepiota-procera", "coprinus-comatus",
        "fistulina-hepatica", "sparassis-crispa", "marasmius-oreades",
    ]
    offenders = []
    for key in well_known:
        sp = taxonomy.get(key)
        if sp is None:
            continue
        if sp.toxicity >= Toxicity.TOXIC:
            offenders.append((key, sp.toxicity.name))
    assert not offenders, f"widely-eaten species carrying a harm label: {offenders}"


def test_lookalike_graph_is_symmetric(taxonomy):
    """If A can be confused with B, B can be confused with A.

    Asymmetry is a data gap with a user-visible consequence: the species
    lookup returns only the declared lookalikes, so a one-directional link
    means one of the two pages omits a dangerous relative."""
    asymmetric = []
    for key, sp in taxonomy.species.items():
        for other_key in sp.lookalikes:
            other = taxonomy.get(other_key)
            if other is not None and key not in other.lookalikes:
                asymmetric.append((key, other_key))
    assert not asymmetric, f"one-directional lookalike links: {asymmetric}"


def test_every_deadly_species_is_reachable_from_its_lookalikes(taxonomy):
    """Each deadly species must be discoverable from the species people
    actually go looking for."""
    for key in taxonomy.deadly_keys():
        referenced_by = [
            k for k, s in taxonomy.species.items() if key in s.lookalikes
        ]
        assert referenced_by, (
            f"{key} is deadly but no other species lists it as a lookalike, "
            "so a user browsing its safe counterpart would never see it"
        )


def test_genus_matches_scientific_name(taxonomy):
    mismatched = [
        (k, s.genus, s.scientific_name)
        for k, s in taxonomy.species.items()
        if s.genus != s.scientific_name.split()[0]
    ]
    assert not mismatched, f"genus does not match binomial: {mismatched}"


def test_no_species_is_left_unassessed(taxonomy):
    unassessed = [
        k for k, s in taxonomy.species.items() if s.toxicity is Toxicity.UNASSESSED
    ]
    assert not unassessed, f"species with no toxicity assessment: {unassessed}"


def test_notes_are_substantive(taxonomy):
    """Notes are rendered to users as the explanation, so a stub is a defect."""
    thin = [k for k, s in taxonomy.species.items() if len(s.notes) < 40]
    assert not thin, f"species with inadequate notes: {thin}"


def test_internal_notes_are_never_part_of_user_facing_notes(raw):
    for entry in raw["species"]:
        note = entry.get("notes", "").lower()
        for leak in ("policy", "docs/safety.md", "do not relax", "review"):
            assert leak not in note, (
                f"{entry['key']}: internal language leaked into user-facing notes"
            )


def test_policy_statement_is_present_and_current(raw):
    policy = raw.get("$policy", "")
    assert policy, "the data file must carry its own policy statement"
    assert "NONE_RECORDED" in policy
    assert "never rendered as a recommendation" in policy


def test_amatoxin_lepiotas_are_present(taxonomy):
    """Small amatoxin-containing Lepiota species occur in the UK and kill.

    A species the model has never seen cannot be flagged as dangerous: it is
    forced into the nearest class it knows, which may be something harmless.
    Their absence was the most significant gap in the first label space.
    """
    for key in ("lepiota-brunneoincarnata", "lepiota-subincarnata"):
        sp = taxonomy.get(key)
        assert sp is not None, f"{key} is missing from the label space"
        assert sp.toxicity is Toxicity.DEADLY


def test_lepiotas_are_reachable_from_lawn_and_parasol_species(taxonomy):
    """The deadly dapperlings must be discoverable from what people actually
    look up: the Fairy Ring Champignon and the Parasol."""
    for entry_point in ("marasmius-oreades", "macrolepiota-procera"):
        sp = taxonomy[entry_point]
        assert any(la.startswith("lepiota-") for la in sp.lookalikes), (
            f"{entry_point} does not reference any Lepiota, so a user browsing "
            "it would never be shown the deadly small dapperlings"
        )


def test_amanita_pantherina_is_present_and_linked_to_the_blusher(taxonomy):
    sp = taxonomy.get("amanita-pantherina")
    assert sp is not None
    assert sp.toxicity is Toxicity.SERIOUS
    assert "amanita-rubescens" in sp.lookalikes
    assert "amanita-pantherina" in taxonomy["amanita-rubescens"].lookalikes
