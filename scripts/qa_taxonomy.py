#!/usr/bin/env python3
"""Quality assurance pass over the taxonomy.

Catches internal contradictions, broken references and -- most usefully --
semantic mismatches between a species' name and its recorded toxicity.

Run before any commit that touches data/taxonomy.seed.json:

    python scripts/qa_taxonomy.py

Exits non-zero if any ERROR-level finding is present. WARN findings are for
human judgement and do not fail the run.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "server"))

VALID_TOXICITY = {"DEADLY", "SERIOUS", "TOXIC", "NONE_RECORDED", "UNASSESSED"}

# Latin epithets that assert edibility or palatability. A species carrying
# one of these while recorded as harmful, or vice versa, is worth a human
# look -- this is exactly the class of error that put "Boletus edulis" and
# "INEDIBLE" in the same row.
EDIBLE_EPITHETS = {
    "edulis": "edible",
    "esculenta": "edible",
    "esculentus": "edible",
    "comestibilis": "edible",
    "deliciosus": "delicious",
    "deliciosa": "delicious",
    "cibarius": "for food",
    "sapidus": "tasty",
    "gambosa": None,
}
TOXIC_EPITHETS = {
    "venenata": "poisonous",
    "venenosus": "poisonous",
    "toxica": "toxic",
    "phalloides": None,
    "virosa": "poisonous/slimy",
    "necator": "killer",
    "sardonia": None,
    "emetica": "causing vomiting",
    "satanas": "satanic",
}

findings: list[tuple[str, str, str]] = []


def error(species: str, message: str) -> None:
    findings.append(("ERROR", species, message))


def warn(species: str, message: str) -> None:
    findings.append(("WARN", species, message))


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def main() -> int:
    path = ROOT / "data" / "taxonomy.seed.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    species = data["species"]
    by_key = {s["key"]: s for s in species}

    try:
        from app.characters import CHARACTERS
        catalogue = set(CHARACTERS)
    except Exception as exc:  # noqa: BLE001
        catalogue = None
        warn("-", f"Could not load the character catalogue ({exc}); skipping that check.")

    # --- structural ---------------------------------------------------
    for key, count in Counter(s["key"] for s in species).items():
        if count > 1:
            error(key, f"duplicate species key ({count} entries)")

    for name, count in Counter(s["scientific_name"] for s in species).items():
        if count > 1:
            error(name, f"duplicate scientific name ({count} entries)")

    common_owners: dict[str, list[str]] = defaultdict(list)
    for s in species:
        for common in s.get("common_names", []):
            common_owners[common.lower()].append(s["key"])
    for common, owners in common_owners.items():
        if len(owners) > 1:
            warn(", ".join(owners), f"common name {common!r} is shared between species")

    for s in species:
        key, name = s["key"], s["scientific_name"]

        for field in ("key", "scientific_name", "toxicity", "notes"):
            if not s.get(field):
                error(key, f"missing or empty required field {field!r}")

        tox = s.get("toxicity")
        if tox and tox not in VALID_TOXICITY:
            error(key, f"invalid toxicity {tox!r} (expected one of {sorted(VALID_TOXICITY)})")

        expected_key = slugify(name)
        if key != expected_key:
            warn(key, f"key does not match scientific name (expected {expected_key!r})")

        genus = s.get("genus")
        first_word = name.split()[0]
        if genus and genus != first_word:
            error(key, f"genus {genus!r} does not match scientific name {name!r}")

        # --- reference integrity --------------------------------------
        for la in s.get("lookalikes", []):
            if la not in by_key:
                error(key, f"lookalike {la!r} is not in the label space")
            elif la == key:
                error(key, "lists itself as a lookalike")

        if catalogue is not None:
            for char in s.get("diagnostic_characters", []):
                if char not in catalogue:
                    error(key, f"diagnostic character {char!r} has no entry in the catalogue")

        if tox in {"DEADLY", "SERIOUS"} and not s.get("diagnostic_characters"):
            error(key, f"{tox} species has no diagnostic characters to interrogate on")

        # --- content --------------------------------------------------
        notes = s.get("notes", "")
        if re.search(r"\b(is edible|are edible|edible only|safe to eat|good to eat)\b", notes, re.I):
            error(key, "notes assert edibility, which is shown verbatim to users")
        if len(notes) < 40:
            warn(key, "notes are very short; users see this as the explanation")

        # --- semantic: name versus recorded toxicity ------------------
        epithet = name.split()[-1].lower()
        if epithet in EDIBLE_EPITHETS and tox in {"DEADLY", "SERIOUS", "TOXIC"}:
            meaning = EDIBLE_EPITHETS[epithet]
            if meaning:
                warn(key, f"epithet {epithet!r} means {meaning!r} but toxicity is {tox} — verify (this is legitimate for some species)")
        if epithet in TOXIC_EPITHETS and tox in {"NONE_RECORDED"}:
            meaning = TOXIC_EPITHETS[epithet]
            if meaning:
                warn(key, f"epithet {epithet!r} means {meaning!r} but no toxicity is recorded — verify")

    # --- lookalike symmetry ---------------------------------------------
    for s in species:
        for la in s.get("lookalikes", []):
            other = by_key.get(la)
            if other is not None and s["key"] not in other.get("lookalikes", []):
                warn(
                    s["key"],
                    f"lists {la!r} as a lookalike, but {la!r} does not list it back "
                    "(asymmetric confusion is usually a data gap)",
                )

    # --- risk-model sanity ----------------------------------------------
    from fungi_ml.taxonomy import Taxonomy, Toxicity

    tax = Taxonomy.load(path)
    for a, b in tax.dangerous_pairs():
        if tax[a].toxicity is Toxicity.DEADLY and tax[b].toxicity is Toxicity.DEADLY:
            error(f"{a}/{b}", "dangerous pair contains two deadly species, which is not a safety event")

    deadly_genera = {tax[k].genus for k in tax.deadly_keys()}
    for key, sp in tax.species.items():
        if sp.genus in deadly_genera and sp.toxicity is Toxicity.NONE_RECORDED:
            warn(key, f"no toxicity recorded, but genus {sp.genus} contains a deadly species — confirm this is right")

    # --- review status ---------------------------------------------------
    if not data.get("reviewed_by"):
        warn("-", "taxonomy has not been signed off by a mycologist (reviewed_by is null)")

    # --- report ------------------------------------------------------------
    errors = [f for f in findings if f[0] == "ERROR"]
    warns = [f for f in findings if f[0] == "WARN"]

    print(f"QA over {len(species)} species\n")
    for level, name in (("ERROR", "ERRORS"), ("WARN", "WARNINGS")):
        rows = [f for f in findings if f[0] == level]
        if not rows:
            continue
        print(f"{name} ({len(rows)})")
        for _, subject, message in rows:
            print(f"  [{subject}] {message}")
        print()

    if not findings:
        print("No findings.")
    print(f"Summary: {len(errors)} error(s), {len(warns)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
