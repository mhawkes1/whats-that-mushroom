"""The slice of the character table that goes to a mycologist.

1,363 rows over 271 species is not a thing anybody reviews. The pack cuts
it to the rows where an error can change whether a user is warned about
something that can kill, which is 629 rows over 128 species -- and the
cutting is the part that can go wrong in a way nobody notices.
"""

from __future__ import annotations

import csv
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PACK = ROOT / "docs" / "review-pack.csv"
WORKSHEET = ROOT / "docs" / "character-states-worksheet.csv"
TAXONOMY = ROOT / "data" / "taxonomy.seed.json"

DANGER = {"DEADLY", "SERIOUS"}


def _species() -> dict:
    return {s["key"]: s for s in json.loads(TAXONOMY.read_text(encoding="utf-8"))["species"]}


def _pack() -> list[dict]:
    return list(csv.DictReader(PACK.open(encoding="utf-8")))


def test_every_dangerous_species_is_in_the_pack():
    dangerous = {k for k, s in _species().items() if s["toxicity"] in DANGER}
    covered = {r["species_key"] for r in _pack()}
    assert dangerous <= covered, f"not sent for review: {sorted(dangerous - covered)}"


def test_both_halves_of_every_dangerous_pair_are_in_the_pack():
    """The reason tier 2 is four times the size of tier 1.

    A state list is read in both directions. Leaving a state off a DEADLY
    species turns a correct observation into a contradiction and pushes the
    lethal candidate down. The mirror error on the harmless lookalike --
    listing a state it does not show -- means the answer fails to
    contradict it, so the safe species stays up and the deadly one stays
    down. Both halves gate the same warning, so reviewing one is reviewing
    half a safeguard.
    """
    species = _species()
    covered = {r["species_key"] for r in _pack()}
    missing = []
    for key, sp in species.items():
        for other in sp.get("lookalikes") or []:
            if other not in species:
                continue
            if species[key]["toxicity"] in DANGER or species[other]["toxicity"] in DANGER:
                for half in (key, other):
                    if half not in covered:
                        missing.append(f"{half} (opposite {other if half == key else key})")
    assert not missing, f"half a lethal pair left out of the pack: {sorted(set(missing))[:5]}"


def test_the_pack_leaves_out_what_cannot_change_a_warning():
    """It has to be smaller than the whole sheet or it is not a priority.

    A species with no dangerous neighbour cannot move mass toward or away
    from something lethal, and rule 1 renders nothing for a species with no
    recorded toxicity -- so the worst case is a wrong name with no hazard
    line either way.
    """
    rows = list(csv.DictReader(WORKSHEET.open(encoding="utf-8")))
    pack = _pack()
    assert len(pack) < len(rows) * 0.6, (
        f"the pack is {len(pack)} of {len(rows)} rows, which is not a triage"
    )
    assert {r["PRIORITY"] for r in pack} == {"1", "2", "3"}


def test_the_pack_is_sorted_deadliest_first():
    order = {"DEADLY": 0, "SERIOUS": 1, "TOXIC": 2, "NO_RECORDED_TOXICITY": 3}
    keys = [(int(r["PRIORITY"]), order[r["toxicity"]]) for r in _pack()]
    assert keys == sorted(keys), "a reviewer must be able to stop anywhere and have done the worst"


def test_merging_a_returned_pack_never_clears_a_row_it_does_not_cover(tmp_path):
    """The data-loss hazard this script exists to avoid.

    `character_states.py import` is authoritative -- it wipes any state not
    in the sheet it is handed. The pack is 629 of 1,363 rows, so feeding it
    to `import` would silently delete the other 734. `--merge` writes only
    the rows the pack covers.
    """
    before = WORKSHEET.read_text(encoding="utf-8")
    rows = _pack()
    rows[0]["AGREE"] = "Y"
    rows[0]["REVIEWER"] = "A Mycologist"
    returned = tmp_path / "returned.csv"
    with returned.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    try:
        out = subprocess.run(
            [sys.executable, "scripts/review_pack.py", "--merge", str(returned)],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        after = list(csv.DictReader(WORKSHEET.open(encoding="utf-8")))
        original = list(csv.DictReader(before.splitlines()))
        assert len(after) == len(original), "the merge changed the number of rows"
        emptied = [r for r in after if not (r["REVIEW_states"] or "").strip()]
        assert len(emptied) <= 4, (
            f"{len(emptied)} rows have no state after merging; the pack covers "
            "629 of 1,363 and must not touch the rest"
        )
        assert "untouched" in out.stdout
    finally:
        WORKSHEET.write_text(before, encoding="utf-8")
