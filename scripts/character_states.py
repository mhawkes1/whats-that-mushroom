#!/usr/bin/env python3
"""Get character states out to a reviewer, and back into the taxonomy.

    python scripts/character_states.py emit    # write the blank worksheet
    python scripts/character_states.py import  # read a filled one back in
    python scripts/character_states.py status  # how much is described

`character_states` is what makes a user's answer mean something: without it
the app knows spore print colour separates a death cap from a field mushroom,
but not which colour belongs to which, so an answer cannot rule either out.
The mechanism that consumes it is `server/app/evidence.py`; it is a
deliberate no-op while the table is empty.

The table is empty because it encodes claims users act on, and the taxonomy
has not been reviewed. `docs/REVIEW.md` separates field-character review --
which an experienced forager can do, and which unblocks development -- from
toxicity and nomenclature review, which needs qualified sign-off and blocks
release. This is the mechanism for the first.

The worksheet is one row per (species, character) pair, restricted to the
characters that species already declares as diagnostic, with the permitted
answers spelled out. `import` refuses any state that is not one of them:
a state that does not match an answer option exactly can never fire, and
would look like a filled-in table that does nothing.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "server"))

from app.characters import CHARACTERS  # noqa: E402
from fungi_ml.taxonomy import Taxonomy  # noqa: E402

TAXONOMY = ROOT / "data" / "taxonomy.seed.json"
WORKSHEET = ROOT / "docs" / "character-states-worksheet.csv"

COLUMNS = [
    "species_key",
    "scientific_name",
    "common_name",
    "toxicity",
    "character",
    "character_label",
    "question",
    "permitted_states",
    "REVIEW_states",
    "REVIEW_notes",
    "REVIEWER",
    "REVIEW_DATE",
]

SEPARATOR = ";"


def emit(taxonomy_path: Path, out_path: Path) -> int:
    """Write a blank worksheet, deadliest species first."""
    taxonomy = Taxonomy.load(taxonomy_path)

    def priority(key: str) -> tuple:
        sp = taxonomy[key]
        return (-int(sp.toxicity), sp.scientific_name)

    rows = []
    for key in sorted(taxonomy.species, key=priority):
        sp = taxonomy[key]
        for character_key in sp.diagnostic_characters:
            character = CHARACTERS.get(character_key)
            if character is None or not character.options:
                # A free-photograph character has no discrete states to record.
                continue
            rows.append(
                {
                    "species_key": sp.key,
                    "scientific_name": sp.scientific_name,
                    "common_name": sp.common_names[0] if sp.common_names else "",
                    "toxicity": sp.toxicity.name,
                    "character": character_key,
                    "character_label": character.label,
                    "question": character.prompt,
                    "permitted_states": SEPARATOR.join(character.options),
                    "REVIEW_states": "",
                    "REVIEW_notes": "",
                    "REVIEWER": "",
                    "REVIEW_DATE": "",
                }
            )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {out_path}")
    print()
    print("For each row, put the state(s) that species actually shows into")
    print(f"REVIEW_states, copied exactly from permitted_states, {SEPARATOR!r}-separated")
    print("for more than one. Leave a row blank if you are not sure -- a blank")
    print("row is treated as 'not described', which is safe. A wrong row is not.")
    return 0


def read_worksheet(path: Path) -> tuple[dict[str, dict[str, list[str]]], list[str]]:
    """Parse a filled worksheet into {species: {character: [states]}}, plus errors."""
    states: dict[str, dict[str, list[str]]] = {}
    errors: list[str] = []

    with path.open(newline="", encoding="utf-8") as handle:
        for line, row in enumerate(csv.DictReader(handle), start=2):
            raw = (row.get("REVIEW_states") or "").strip()
            if not raw:
                continue

            species_key = (row.get("species_key") or "").strip()
            character_key = (row.get("character") or "").strip()

            character = CHARACTERS.get(character_key)
            if character is None:
                errors.append(f"line {line}: unknown character {character_key!r}")
                continue

            chosen = [part.strip() for part in raw.split(SEPARATOR) if part.strip()]
            # Exact-match only. A near-miss produces a table that looks
            # populated and never fires, which is worse than an empty one.
            unknown = [c for c in chosen if c not in character.options]
            if unknown:
                errors.append(
                    f"line {line}: {species_key}/{character_key}: "
                    f"{unknown!r} not in permitted_states"
                )
                continue

            states.setdefault(species_key, {})[character_key] = chosen

    return states, errors


def import_states(taxonomy_path: Path, worksheet_path: Path, dry_run: bool) -> int:
    if not worksheet_path.exists():
        print(f"No worksheet at {worksheet_path}. Run `emit` first.", file=sys.stderr)
        return 1

    states, errors = read_worksheet(worksheet_path)

    blob = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    known = {entry["key"] for entry in blob["species"]}
    for species_key in states:
        if species_key not in known:
            errors.append(f"unknown species {species_key!r}")

    if errors:
        print(f"Refusing to import: {len(errors)} problem(s).", file=sys.stderr)
        for error in errors[:20]:
            print(f"  {error}", file=sys.stderr)
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more", file=sys.stderr)
        return 1

    described = 0
    for entry in blob["species"]:
        table = states.get(entry["key"])
        if table:
            entry["character_states"] = table
            described += 1
        else:
            entry.pop("character_states", None)

    entries = sum(len(t) for t in states.values())
    print(f"{described} species described, {entries} character entries.")

    if dry_run:
        print("Dry run: taxonomy not written.")
        return 0

    taxonomy_path.write_text(
        json.dumps(blob, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {taxonomy_path}")
    print("Run the tests: python -m pytest ml/tests server/tests -q")
    return 0


def status(taxonomy_path: Path) -> int:
    taxonomy = Taxonomy.load(taxonomy_path)
    total = len(taxonomy.species)
    described = [s for s in taxonomy.species.values() if s.character_states]
    entries = sum(len(s.character_states) for s in described)

    print(f"  species described : {len(described)}/{total}")
    print(f"  character entries : {entries}")

    deadly = [s for s in taxonomy.species.values() if s.toxicity.name == "DEADLY"]
    deadly_done = [s for s in deadly if s.character_states]
    print(f"  deadly described  : {len(deadly_done)}/{len(deadly)}")

    if not described:
        print()
        print("  Nothing described, so answers to diagnostic questions do not")
        print("  re-weight anything. That is by design, not a fault -- see")
        print("  server/app/evidence.py.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["emit", "import", "status"])
    ap.add_argument("--taxonomy", type=Path, default=TAXONOMY)
    ap.add_argument("--worksheet", type=Path, default=WORKSHEET)
    ap.add_argument("--dry-run", action="store_true", help="Validate without writing.")
    args = ap.parse_args()

    if args.action == "emit":
        return emit(args.taxonomy, args.worksheet)
    if args.action == "import":
        return import_states(args.taxonomy, args.worksheet, args.dry_run)
    return status(args.taxonomy)


if __name__ == "__main__":
    raise SystemExit(main())
