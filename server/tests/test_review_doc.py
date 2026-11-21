"""`docs/REVIEW.md` is the first document an outside expert reads.

It stood for two months saying the taxonomy "covers 57 species", claiming
205 character rows and naming eight deadly species, against a real 271 /
1,363 / 10. It also listed *Clitocybe dealbata* in its critical tier -- a
species that had been dropped from the label space entirely. Every one of
those numbers was written once and never re-derived, which is the fault
this project keeps meeting.

So the document no longer owns its own figures. Each is recomputed here
from the taxonomy and the review pack, and no expected value is restated
below: add a species, drop one, or raise a toxicity, and the test that
owns the sentence fails.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from review_pack import tiers  # noqa: E402

DOC = ROOT / "docs" / "REVIEW.md"
TAXONOMY = ROOT / "data" / "taxonomy.seed.json"
PACK = ROOT / "docs" / "review-pack.csv"
WORKSHEET = ROOT / "docs" / "character-states-worksheet.csv"


@pytest.fixture(scope="module")
def doc() -> str:
    return DOC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def species() -> dict:
    return {s["key"]: s for s in json.loads(TAXONOMY.read_text(encoding="utf-8"))["species"]}


def _thousands(n: int) -> str:
    return f"{n:,}"


def test_it_states_the_size_of_the_label_space(doc: str, species: dict) -> None:
    assert _thousands(len(species)) in doc


@pytest.mark.parametrize("hazard", ["DEADLY", "SERIOUS", "TOXIC", "NO_RECORDED_TOXICITY"])
def test_it_states_each_hazard_count(doc: str, species: dict, hazard: str) -> None:
    n = sum(1 for s in species.values() if s["toxicity"] == hazard)
    assert re.search(rf"\|\s*{_thousands(n)}\s*\|", doc), (
        f"REVIEW.md does not state {n} anywhere in a table cell; "
        f"{hazard} is at {n}"
    )


def test_it_states_the_whole_table_and_the_slice(doc: str, species: dict) -> None:
    rows = sum(len(s.get("character_states") or {}) for s in species.values())
    worksheet = sum(1 for _ in csv.DictReader(WORKSHEET.open(encoding="utf-8")))
    pack = sum(1 for _ in csv.DictReader(PACK.open(encoding="utf-8")))
    # The worksheet emits a row per declared character; a handful carry no
    # state yet, so it is the larger number and the one a reviewer meets.
    assert worksheet >= rows
    assert _thousands(worksheet) in doc, f"the table is {worksheet} rows"
    assert _thousands(pack) in doc, f"the pack is {pack} rows"


@pytest.mark.parametrize("tier", [1, 2, 3])
def test_it_states_each_tier_correctly(doc: str, species: dict, tier: int) -> None:
    keys = [k for k, (n, _) in tiers().items() if n == tier]
    rows = sum(len(species[k].get("character_states") or {}) for k in keys)
    pack = [
        r for r in csv.DictReader(PACK.open(encoding="utf-8"))
        if int(r["PRIORITY"]) == tier
    ]
    assert f"{len(keys)} species" in doc, f"tier {tier} holds {len(keys)} species"
    assert f"{len(pack)} rows" in doc, f"tier {tier} is {len(pack)} rows in the pack"
    assert rows <= len(pack)


def test_it_states_what_the_pack_leaves_out(doc: str, species: dict) -> None:
    covered = {r["species_key"] for r in csv.DictReader(PACK.open(encoding="utf-8"))}
    rest = [s for k, s in species.items() if k not in covered]
    rows = sum(len(s.get("character_states") or {}) for s in rest)
    assert f"{len(rest)} species, {rows} rows" in doc


def test_every_species_it_names_is_in_the_label_space(doc: str, species: dict) -> None:
    """The old version listed *Clitocybe dealbata* among the species that
    can kill. It had been dropped from the label space months earlier, so
    the document sent a reviewer looking for something that is not there."""
    names = {s["scientific_name"] for s in species.values()}
    # Binomials in italics: *Genus species*, ignoring any trailing marks.
    cited = {
        m.group(1)
        for m in re.finditer(r"\*([A-Z][a-z]+ [a-z]+)\*", doc)
    }
    # Names the document discusses precisely because they are NOT held.
    absent_on_purpose = {"Clitocybe dealbata", "Inocybe lilacina", "Inosperma erubescens",
                         "Russula adusta"}
    missing = sorted(cited - names - absent_on_purpose)
    assert not missing, f"REVIEW.md names species the taxonomy does not hold: {missing}"


def test_it_states_who_filled_the_worksheet_in(doc: str) -> None:
    by = Counter(
        r["REVIEWER"].strip()
        for r in csv.DictReader(WORKSHEET.open(encoding="utf-8"))
        if r["REVIEWER"].strip()
    )
    for who, n in by.items():
        assert _thousands(n) in doc, f"{who} filled {n} rows; REVIEW.md does not say so"


def test_it_does_not_claim_the_taxonomy_is_reviewed(doc: str) -> None:
    head = doc[:600]
    assert "has been checked by a qualified mycologist" not in head
    assert "taxonomy_reviewed: false" in head
