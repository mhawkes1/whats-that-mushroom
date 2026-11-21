"""The slice of the character table a mycologist has to check before launch.

`docs/character-states-worksheet.csv` is 1,363 rows over 271 species and
nobody is going to read it. This cuts it to the rows where an error can
change whether a user is warned about something that can kill them, in the
order they should be worked.

    python scripts/review_pack.py --emit     # -> docs/review-pack.csv
    python scripts/review_pack.py --merge <returned.csv>

**Why these rows and not simply the dangerous species.** A state list is
used in both directions. For a DEADLY species, leaving a state off turns a
correct observation into a contradiction and pushes the lethal candidate
DOWN -- a false dismissal. For the harmless lookalike opposite it, the
error that matters is the mirror image: listing a state it does not show
means a user's answer fails to contradict it, so the safe species stays up
and the deadly one stays down. Both halves of a lethal pair therefore gate
the same warning, which is why tier 2 exists and is four times tier 1.

Tier 4 -- the 143 species with no dangerous neighbour at all -- is NOT in
the pack. An error there cannot change a hazard line, because rule 1
renders nothing for a species with no recorded toxicity: the worst case is
a wrong name on a harmless mushroom.

**The merge step is not optional, and the reason is a data-loss hazard.**
`character_states.py import` is authoritative: it wipes any state not
present in the sheet it is given. Feeding a 629-row pack to it would
silently delete the 734 rows that were left out. `--merge` reads the
returned pack, writes only the rows it covers back into the full
worksheet, and leaves every other row exactly as it was.
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TAXONOMY = ROOT / "data" / "taxonomy.seed.json"
WORKSHEET = ROOT / "docs" / "character-states-worksheet.csv"
PACK = ROOT / "docs" / "review-pack.csv"

DANGER = {"DEADLY", "SERIOUS"}

COLUMNS = [
    "PRIORITY", "WHY",
    "scientific_name", "common_name", "toxicity",
    "character_label", "question", "permitted_states",
    "RECORDED_states",
    "AGREE", "CORRECTED_states", "REVIEW_notes", "REVIEWER", "REVIEW_DATE",
    "species_key", "character",          # keys, last: needed by --merge, not by a reader
]


def tiers() -> dict[str, tuple[int, str]]:
    """species key -> (tier, why), for the species that gate a warning."""
    species = {s["key"]: s for s in json.loads(TAXONOMY.read_text())["species"]}
    deadly = {k for k, s in species.items() if s["toxicity"] == "DEADLY"}
    serious = {k for k, s in species.items() if s["toxicity"] == "SERIOUS"}

    facing: dict[str, set[str]] = {"DEADLY": set(), "SERIOUS": set()}
    for key, sp in species.items():
        for other in sp.get("lookalikes") or []:
            if other not in species:
                continue
            for a, b in ((key, other), (other, key)):
                if a in deadly:
                    facing["DEADLY"].add(b)
                elif a in serious:
                    facing["SERIOUS"].add(b)

    out: dict[str, tuple[int, str]] = {}
    for key in deadly | serious:
        out[key] = (1, "can kill or cause serious harm")
    for key in facing["DEADLY"] - deadly - serious:
        out[key] = (2, "confused in the field with a species that can kill")
    for key in facing["SERIOUS"] - deadly - serious - set(out):
        out[key] = (3, "confused with a species that causes serious harm")
    return out


def emit() -> int:
    priority = tiers()
    rows = list(csv.DictReader(WORKSHEET.open(encoding="utf-8")))
    kept = []
    for row in rows:
        if row["species_key"] not in priority:
            continue
        tier, why = priority[row["species_key"]]
        kept.append({
            "PRIORITY": tier,
            "WHY": why,
            "scientific_name": row["scientific_name"],
            "common_name": row["common_name"],
            "toxicity": row["toxicity"],
            "character_label": row["character_label"],
            "question": row["question"],
            "permitted_states": row["permitted_states"],
            "RECORDED_states": row["REVIEW_states"],
            "AGREE": "",
            "CORRECTED_states": "",
            "REVIEW_notes": "",
            "REVIEWER": "",
            "REVIEW_DATE": "",
            "species_key": row["species_key"],
            "character": row["character"],
        })

    # Deadliest first inside each tier, then species, then character, so the
    # sheet can be worked top to bottom and abandoned anywhere.
    order = {"DEADLY": 0, "SERIOUS": 1, "TOXIC": 2, "NO_RECORDED_TOXICITY": 3}
    kept.sort(key=lambda r: (r["PRIORITY"], order[r["toxicity"]],
                             r["scientific_name"], r["character_label"]))

    with PACK.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(kept)

    for tier in (1, 2, 3):
        rs = [r for r in kept if r["PRIORITY"] == tier]
        print(f"  tier {tier}: {len({r['species_key'] for r in rs}):>4} species "
              f"{len(rs):>5} rows   {rs[0]['WHY'] if rs else ''}")
    print(f"\n{PACK.relative_to(ROOT)}  --  {len(kept)} rows of {len(rows)}, "
          f"{len({r['species_key'] for r in kept})} species of "
          f"{len({r['species_key'] for r in rows})}")
    return 0


def merge(returned: pathlib.Path) -> int:
    """Write a returned pack back WITHOUT touching anything it omits."""
    if not returned.exists():
        print(f"REFUSING: no such file {returned}", file=sys.stderr)
        return 1

    given = {}
    for row in csv.DictReader(returned.open(encoding="utf-8")):
        agree = (row.get("AGREE") or "").strip().lower()
        corrected = (row.get("CORRECTED_states") or "").strip()
        if not agree and not corrected:
            continue                       # untouched: leave the row alone
        given[(row["species_key"], row["character"])] = (agree, corrected, row)

    rows = list(csv.DictReader(WORKSHEET.open(encoding="utf-8")))
    header = list(rows[0])
    changed = disagreed = 0
    # A correction that is not one of the character's own options would sit
    # in the worksheet looking fine and be refused later by
    # `character_states.py import`. Say so here, where the returned sheet is
    # still in front of whoever is merging it, rather than two steps on.
    suspect: list[str] = []
    for row in rows:
        hit = given.get((row["species_key"], row["character"]))
        if not hit:
            continue
        agree, corrected, source = hit
        if corrected and agree not in ("y", "yes"):
            allowed = set(row["permitted_states"].split(";"))
            unknown = [v for v in corrected.split(";") if v.strip() not in allowed]
            if unknown:
                suspect.append(
                    f"{row['scientific_name']} / {row['character_label']}: "
                    f"{unknown} not an option for this character"
                )
            row["REVIEW_states"] = corrected
            disagreed += 1
        row["REVIEW_notes"] = source.get("REVIEW_notes") or row["REVIEW_notes"]
        row["REVIEWER"] = source.get("REVIEWER") or row["REVIEWER"]
        row["REVIEW_DATE"] = source.get("REVIEW_DATE") or row["REVIEW_DATE"]
        changed += 1

    with WORKSHEET.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)

    print(f"  {changed} rows carried back, {disagreed} of them corrected")
    for line in suspect:
        print(f"  CHECK: {line}")
    print(f"  {len(rows) - changed} rows untouched -- the pack is a SLICE, and "
          f"`character_states.py import` would have wiped them")
    print(f"\nNext: python scripts/character_states.py import")
    return 0


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "--emit":
        return emit()
    if len(sys.argv) == 3 and sys.argv[1] == "--merge":
        return merge(pathlib.Path(sys.argv[2]))
    print(__doc__.strip().splitlines()[0], file=sys.stderr)
    print("\n  python scripts/review_pack.py --emit"
          "\n  python scripts/review_pack.py --merge <returned.csv>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
