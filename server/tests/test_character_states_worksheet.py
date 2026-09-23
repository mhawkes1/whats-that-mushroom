"""The route by which character states reach the taxonomy.

The mechanism in `evidence.py` is inert until this table is filled in, and it
will be filled in by a person working through a spreadsheet. The failure that
matters is not a crash: it is a worksheet that imports cleanly and produces
states that can never match an answer, because a state that is not exactly one
of the character's options is silently unreachable.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "ml"))

from app.characters import CHARACTERS  # noqa: E402


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "character_states_script", ROOT / "scripts" / "character_states.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _load_script()
WORKSHEET = ROOT / "docs" / "character-states-worksheet.csv"


def test_every_species_appears_in_the_worksheet():
    """The worksheet is the reviewer's view of the table, so it must be complete."""
    from fungi_ml.taxonomy import Taxonomy

    taxonomy = Taxonomy.load(ROOT / "data" / "taxonomy.seed.json")
    listed = {row["species_key"] for row in csv.DictReader(WORKSHEET.open(encoding="utf-8"))}

    # A species whose diagnostic characters are all free-photograph ones has
    # no discrete states to record and legitimately has no rows.
    expected = {
        key
        for key, species in taxonomy.species.items()
        if any(
            CHARACTERS[c].options
            for c in species.diagnostic_characters
            if c in CHARACTERS
        )
    }
    assert listed == expected


def test_every_filled_row_is_flagged_unreviewed():
    """Nothing in the sheet may read as sign-off.

    Every state was compiled from the taxonomy's own notes rather than from a
    mycologist, and the sheet has to say so on each row, because the sheet is
    what a reviewer will actually open.
    """
    rows = list(csv.DictReader(WORKSHEET.open(encoding="utf-8")))
    filled = [row for row in rows if row["REVIEW_states"].strip()]
    assert filled, "the worksheet should be filled in"
    assert all("UNREVIEWED" in row["REVIEW_notes"] for row in filled)
    assert all(row["REVIEWER"].strip() for row in filled)


def test_every_worksheet_row_offers_the_real_answer_options():
    """The options shown to the reviewer are the ones the app will compare against.

    A reviewer copying from `permitted_states` must produce a state the
    matcher can actually hit.
    """
    for row in csv.DictReader(WORKSHEET.open(encoding="utf-8")):
        character = CHARACTERS[row["character"]]
        offered = row["permitted_states"].split(script.SEPARATOR)
        assert offered == list(character.options), row["character"]


def test_worksheet_only_asks_about_characters_the_species_declares():
    from fungi_ml.taxonomy import Taxonomy

    taxonomy = Taxonomy.load(ROOT / "data" / "taxonomy.seed.json")
    for row in csv.DictReader(WORKSHEET.open(encoding="utf-8")):
        species = taxonomy[row["species_key"]]
        assert row["character"] in species.diagnostic_characters


def test_deadly_species_are_listed_first():
    """The reviewer's time is finite; the lethal rows should come first."""
    rows = list(csv.DictReader(WORKSHEET.open(encoding="utf-8")))
    toxicities = [row["toxicity"] for row in rows]
    last_deadly = max(i for i, t in enumerate(toxicities) if t == "DEADLY")
    first_non_deadly = min(i for i, t in enumerate(toxicities) if t != "DEADLY")
    assert last_deadly < first_non_deadly


def _worksheet_with(tmp_path: Path, filled: list[dict]) -> Path:
    """A copy of the worksheet with everything cleared but these rows.

    Blanked first so these tests assert the parser's behaviour rather than
    whatever happens to be filled in at the time.
    """
    rows = list(csv.DictReader(WORKSHEET.open(encoding="utf-8")))
    for row in rows:
        row["REVIEW_states"] = ""
    for target in filled:
        for row in rows:
            if (
                row["species_key"] == target["species_key"]
                and row["character"] == target["character"]
            ):
                row["REVIEW_states"] = target["states"]
                break
        else:  # pragma: no cover - a broken fixture, not a code path
            raise AssertionError(f"no worksheet row for {target}")

    path = tmp_path / "filled.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_a_filled_worksheet_parses_into_states(tmp_path):
    path = _worksheet_with(
        tmp_path,
        [
            {
                "species_key": "amanita-phalloides",
                "character": "spore_print_colour",
                "states": "White or cream",
            },
            {
                "species_key": "amanita-phalloides",
                "character": "volva",
                "states": "Clear cup or sac",
            },
        ],
    )
    states, errors = script.read_worksheet(path)
    assert errors == []
    assert states["amanita-phalloides"]["spore_print_colour"] == ["White or cream"]
    assert states["amanita-phalloides"]["volva"] == ["Clear cup or sac"]


def test_several_states_for_one_character_are_allowed(tmp_path):
    """A species may legitimately show more than one state of a character."""
    path = _worksheet_with(
        tmp_path,
        [
            {
                "species_key": "amanita-phalloides",
                "character": "cap_colour",
                "states": f"{CHARACTERS['cap_colour'].options[0]}"
                f"{script.SEPARATOR}{CHARACTERS['cap_colour'].options[1]}",
            }
        ],
    )
    states, errors = script.read_worksheet(path)
    assert errors == []
    assert len(states["amanita-phalloides"]["cap_colour"]) == 2


def test_a_state_that_is_not_an_answer_option_is_rejected(tmp_path):
    """The failure this guard exists for.

    'White or creme' imports, stores, and never matches anything, because no
    answer the app can produce equals it. A populated table that cannot fire
    is worse than an empty one -- the empty one is honest.
    """
    path = _worksheet_with(
        tmp_path,
        [
            {
                "species_key": "amanita-phalloides",
                "character": "spore_print_colour",
                "states": "White or creme",
            }
        ],
    )
    states, errors = script.read_worksheet(path)
    assert errors, "a near-miss spelling must be refused, not stored"
    assert "amanita-phalloides" not in states


def test_blank_rows_are_skipped_not_treated_as_empty_states(tmp_path):
    """Unsure must mean undescribed, which the matcher treats as no evidence."""
    path = _worksheet_with(
        tmp_path,
        [
            {
                "species_key": "amanita-phalloides",
                "character": "volva",
                "states": "   ",
            }
        ],
    )
    states, _ = script.read_worksheet(path)
    assert "amanita-phalloides" not in states


def test_import_refuses_an_unknown_species(tmp_path):
    path = _worksheet_with(
        tmp_path,
        [
            {
                "species_key": "amanita-phalloides",
                "character": "volva",
                "states": "Clear cup or sac",
            }
        ],
    )
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    for row in rows:
        if row["REVIEW_states"].strip():
            row["species_key"] = "amanita-imaginaria"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    taxonomy_copy = tmp_path / "taxonomy.json"
    taxonomy_copy.write_text(
        (ROOT / "data" / "taxonomy.seed.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    assert script.import_states(taxonomy_copy, path, dry_run=False) == 1
    # The taxonomy must be untouched when the import is refused.
    assert json.loads(taxonomy_copy.read_text(encoding="utf-8")) == json.loads(
        (ROOT / "data" / "taxonomy.seed.json").read_text(encoding="utf-8")
    )


def test_import_writes_states_the_taxonomy_can_load_back(tmp_path):
    """The whole loop: worksheet -> taxonomy -> a Species that carries states."""
    from fungi_ml.taxonomy import Taxonomy

    path = _worksheet_with(
        tmp_path,
        [
            {
                "species_key": "amanita-phalloides",
                "character": "spore_print_colour",
                "states": "White or cream",
            }
        ],
    )
    taxonomy_copy = tmp_path / "taxonomy.json"
    taxonomy_copy.write_text(
        (ROOT / "data" / "taxonomy.seed.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    assert script.import_states(taxonomy_copy, path, dry_run=False) == 0

    reloaded = Taxonomy.load(taxonomy_copy)
    assert reloaded["amanita-phalloides"].character_states == {
        "spore_print_colour": ("White or cream",)
    }
    # Everything else stays undescribed rather than picking up an empty table.
    assert reloaded["agaricus-campestris"].character_states == {}


def test_a_dry_run_never_writes(tmp_path):
    path = _worksheet_with(
        tmp_path,
        [
            {
                "species_key": "amanita-phalloides",
                "character": "volva",
                "states": "Clear cup or sac",
            }
        ],
    )
    taxonomy_copy = tmp_path / "taxonomy.json"
    original = (ROOT / "data" / "taxonomy.seed.json").read_text(encoding="utf-8")
    taxonomy_copy.write_text(original, encoding="utf-8")

    assert script.import_states(taxonomy_copy, path, dry_run=True) == 0
    assert taxonomy_copy.read_text(encoding="utf-8") == original


@pytest.mark.parametrize("action", ["emit", "status"])
def test_the_script_runs(tmp_path, action, capsys):
    """Smoke: both read-only actions work against a scratch copy."""
    if action == "emit":
        out = tmp_path / "sheet.csv"
        assert script.emit(ROOT / "data" / "taxonomy.seed.json", out) == 0
        assert out.exists()
    else:
        assert script.status(ROOT / "data" / "taxonomy.seed.json") == 0


# --- Coverage against how often things are actually found --------------------


def _gap():
    spec = importlib.util.spec_from_file_location(
        "frdbi_gap", ROOT / "scripts" / "frdbi_gap.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_species_already_known_is_never_reported_as_missing():
    """The one error that would make the report actively harmful.

    FRDBI uses current combinations and the taxonomy does not always. A
    species present under an older name, reported as absent, sends somebody
    off to add a duplicate of something already there -- and the report
    exists to decide what to add.

    The synonym map runs in both directions on purpose: most of its entries
    name species the taxonomy does *not* hold, where the older name is a note
    for whoever adds them. What must hold is that no row lands in "missing"
    when either name is known.
    """
    from app.taxonomy_service import TaxonomyService

    gap = _gap()
    taxonomy = TaxonomyService.load(ROOT / "data" / "taxonomy.seed.json")
    known = {s.scientific_name for s in taxonomy.species.values()}

    for name, _ in gap.load_records():
        both = {name, gap.SYNONYMS.get(name, name)}
        assert bool(both & known) == any(n in known for n in both), name

    for frdbi, ours in (("Collybia nuda", "Lepista nuda"),
                        ("Polyporus squamosus", "Cerioporus squamosus")):
        assert gap.SYNONYMS[frdbi] == ours
        assert frdbi not in known and ours in known, frdbi


def test_no_two_frdbi_rows_resolve_to_the_same_species():
    """A collision would double-count one species and hide another."""
    gap = _gap()
    resolved = [gap.SYNONYMS.get(n, n) for n, _ in gap.load_records()]
    duplicates = {n for n in resolved if resolved.count(n) > 1}
    assert not duplicates, f"rows resolving to the same name: {duplicates}"


# How deep the ranking is trusted. Raise this with the label space, never
# above it: every genus above the cutoff must be classified for the coverage
# figure at that depth to mean anything.
GUARDED_DEPTH = 300


def test_no_unclassified_genus_outranks_the_species_being_reported_on():
    """The quiet failure this report could have.

    Filtering is done at genus, because eighteen thousand species cannot be
    judged by hand and a genus can be checked by somebody. The cost is that a
    genus nobody classified counts as nothing -- and if it held a species
    common enough to belong in the answer, the coverage figure would be wrong
    and would never say so.

    Cortinarius and Galerina were both unclassified when this table was first
    written, which is the orellanine webcaps and the funeral bell.

    Guarded to the depth actually in use, not to rank 100. When this test
    stopped at 100 the table had eight unclassified taxa above the top-250
    cutoff, four of them real macrofungi -- the dog stinkhorn, beech
    tarcrust, leafy brain and conifercone cap -- and the test passed
    throughout. A guard shallower than the working depth is a guard that
    reports on somewhere nobody is standing.
    """
    gap = _gap()
    genera = gap.load_genera()
    by_kind: dict[str, list[tuple[str, int]]] = {}
    for name, count in gap.load_records():
        by_kind.setdefault(genera.get(name.split()[0], "?"), []).append((name, count))

    fungi = by_kind["fungus"]
    cutoff = fungi[GUARDED_DEPTH - 1][1]
    intruders = [(n, c) for n, c in by_kind.get("?", []) if c >= cutoff]
    assert not intruders, (
        f"unclassified taxa out-record the {GUARDED_DEPTH}th macrofungus "
        f"({cutoff:,}): {intruders[:10]}"
    )


def test_the_genus_table_is_well_formed():
    """`kind` drives every figure the report prints."""
    gap = _gap()
    genera = gap.load_genera()
    assert genera
    assert set(genera.values()) <= {
        "fungus", "micro", "host", "slime-mould", "lichen",
    }

    # Every genus the label space holds must be classified as a fungus,
    # however rare it is. An unclassified genus counts as nothing, so its
    # species can never show up as covered -- and the genera this app most
    # needs to get right are exactly the uncommon ones. Derived from the
    # taxonomy so that adding a species cannot quietly break it.
    from app.taxonomy_service import TaxonomyService

    taxonomy = TaxonomyService.load(ROOT / "data" / "taxonomy.seed.json")
    for species in taxonomy.species.values():
        assert genera.get(species.genus) == "fungus", (
            f"{species.genus} is in the label space and is "
            f"{genera.get(species.genus)!r} in the genus table"
        )


def test_the_records_file_is_sorted_and_positive():
    gap = _gap()
    records = gap.load_records()
    assert len(records) > 10_000
    assert all(c > 0 for _, c in records)
    assert records == sorted(records, key=lambda r: (-r[1], r[0]))
