#!/usr/bin/env python3
"""What the label space is missing, measured against how often things are found.

    python scripts/frdbi_gap.py

The label space was assembled around danger: eleven species that can kill, and
the ordinary ones each of those is mistaken for. That is the right skeleton and
it says nothing about what a person on a walk actually points a phone at.

`data/frdbi-top-records.csv` is the other axis -- the most-recorded taxa in the
Fungal Records Database of Britain and Ireland. This compares the two.

## Three things the raw ranking is not

**It is not a list of fungi.** FRDBI records host associations, so beech,
oak and the grasses outrank every fungus in it. Thirty-six of the top rows
are plants.

**It is not a list of things this app can be asked about.** Tar spot, oak
mildew, coral spot and bramble rust are recorded in their thousands and are
blemishes on a leaf. A flow that asks about caps, gills and spore prints has
nothing to say to them, and the honest answer is out of scope.

**It is not a list of what a beginner photographs.** Every record was made by
somebody who already knew what they were looking at, and recorders log what
recorders find interesting. It is the best available proxy and it is a proxy.

## What an addition actually costs

A species is never added alone. The label space is a graph, and adding a
common species without the dangerous things it is confused with makes the app
*more* dangerous: it teaches a name the model will reach for and withholds the
one it should have refused over. So the report below prints, for each
candidate, the lookalikes that would have to come with it -- and whether they
are already known.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "ml"))

from app.taxonomy_service import TaxonomyService, Toxicity  # noqa: E402

RECORDS = ROOT / "data" / "frdbi-top-records.csv"
TAXONOMY = ROOT / "data" / "taxonomy.seed.json"

# FRDBI uses current combinations; the taxonomy does not always. Matching on
# the printed string alone would report a species as missing when it is
# already there under an older name, which is the one error that would make
# this report actively harmful.
#
# Only two entries here do that work today -- Collybia nuda and Polyporus
# squamosus. The rest name species the label space does not yet hold, where
# the older name is a note for whoever adds them: reference books are still
# full of Boletus badius and Hygrocybe virginea, and a search for images will
# need both strings.
SYNONYMS = {
    "Collybia nuda": "Lepista nuda",
    "Polyporus squamosus": "Cerioporus squamosus",
    "Imleria badia": "Boletus badius",
    "Apioperdon pyriforme": "Lycoperdon pyriforme",
    "Hymenopellis radicata": "Xerula radicata",
    "Cuphophyllus virgineus": "Hygrocybe virginea",
    "Cuphophyllus pratensis": "Hygrocybe pratensis",
    "Gliophorus psittacinus": "Hygrocybe psittacina",
    "Paralepista flaccida": "Lepista flaccida",
    "Rhodocollybia butyracea": "Collybia butyracea",
    "Collybiopsis peronata": "Gymnopus peronatus",
    "Collybiopsis confluens": "Gymnopus confluens",
    "Collybiopsis ramealis": "Gymnopus ramealis",
    "Chlorophyllum rhacodes": "Macrolepiota rhacodes",
    "Jackrogersella multiformis": "Annulohypoxylon multiforme",
    "Polyporus leptocephalus": "Polyporus varius",
}

# What a photograph of this is most likely to be confused with, where the
# dangerous partner is not obvious from the genus. Compiled from the same
# references as the rest of the taxonomy and UNREVIEWED, like everything else.
RISK_NOTE = {
    "Laccaria laccata": "the deceiver -- variable enough that beginners match it to almost anything",
    "Pluteus cervinus": "free pink gills; Volvopluteus and young Amanita both read similarly",
    "Armillaria mellea": "clustered on wood: the funeral bell's own habit",
    "Coprinellus micaceus": "clustered on wood, and Galerina marginata is too",
    "Gymnopilus penetrans": "orange, clustered, on conifer wood -- the Galerina situation again",
    "Clitocybe fragrans": "a small white Clitocybe; the muscarine species are small white Clitocybes",
    "Hygrocybe conica": "blackening waxcap",
    "Psathyrella candolleana": "clustered, pale, on buried wood",
    "Psathyrella piluliformis": "clustered on stumps, beside Hypholoma and Galerina",
    "Marasmius oreades": "grows in rings in grass, where Clitocybe rivulosa also rings",
    "Inocybe geophylla": "white Inocybe -- muscarine, and mistaken for small field species",
    "Cystoderma amianthinum": "granular Lepiota-like cap",
    "Chlorophyllum rhacodes": "shaggy parasol, confused with the deadly C. molybdites abroad and with brunneum here",
    "Flammulina velutipes": "clustered on wood in winter; Galerina fruits then too",
}


def load_records() -> list[dict]:
    lines = [l for l in RECORDS.read_text(encoding="utf-8").splitlines() if not l.startswith("#")]
    return list(csv.DictReader(lines))


def main() -> int:
    taxonomy = TaxonomyService.load(TAXONOMY)
    known = {s.scientific_name: s for s in taxonomy.species.values()}

    rows = load_records()
    fungi = [r for r in rows if r["kind"] == "fungus"]
    micro = [r for r in rows if r["kind"] == "micro"]
    plants = [r for r in rows if r["kind"] == "not-fungus"]

    def resolve(name: str):
        for candidate in (name, SYNONYMS.get(name, "")):
            if candidate in known:
                return known[candidate]
        return None

    covered = [(r, sp) for r in fungi if (sp := resolve(r["scientific_name"]))]
    missing = [r for r in fungi if resolve(r["scientific_name"]) is None]

    print(f"FRDBI rows transcribed   : {len(rows)}")
    print(f"  host plants / higher   : {len(plants)}  (FRDBI records associations)")
    print(f"  leaf spots, rusts      : {len(micro)}  (nothing this app can ask about)")
    print(f"  macrofungi             : {len(fungi)}")
    print()
    print(f"Already in the label space: {len(covered):3} of {len(fungi)}"
          f"   ({len(covered) / len(fungi):.0%})")
    print(f"Missing                   : {len(missing):3}")
    print()

    print("─" * 74)
    print("ALREADY COVERED, most-recorded first")
    print("─" * 74)
    for r, sp in covered[:20]:
        count = f"{int(r['records']):>7,}" if r["records"] else "      ?"
        print(f"  {count}  {sp.scientific_name:<32} {sp.toxicity.name}")
    if len(covered) > 20:
        print(f"  ... and {len(covered) - 20} more")
    print()

    print("─" * 74)
    print("MISSING, most-recorded first -- and what each would have to bring")
    print("─" * 74)
    for r in missing:
        name = r["scientific_name"]
        count = f"{int(r['records']):>7,}" if r["records"] else "      ?"
        genus = name.split()[0]
        siblings = [s for s in known.values() if s.genus == genus]
        dangerous = [s for s in siblings if s.toxicity in (Toxicity.DEADLY, Toxicity.SERIOUS)]

        print(f"  {count}  {name}")
        if dangerous:
            print(f"           same genus, already known and dangerous: "
                  f"{', '.join(s.scientific_name for s in dangerous)}")
        elif siblings:
            print(f"           genus already represented by "
                  f"{', '.join(s.scientific_name for s in siblings[:3])}")
        if name in RISK_NOTE:
            print(f"           ! {RISK_NOTE[name]}")
    print()

    print("─" * 74)
    print("EXCLUDED, and why")
    print("─" * 74)
    print("  Leaf spots, mildews, rusts and crusts -- recorded constantly, and")
    print("  invisible to a flow built around caps, gills and spore prints:")
    for r in micro:
        count = f"{int(r['records']):>7,}" if r["records"] else "      ?"
        print(f"    {count}  {r['scientific_name']}")
    print()
    print(f"  Host plants and higher taxa: {len(plants)} rows, led by "
          f"{plants[0]['scientific_name']} at {int(plants[0]['records']):,}.")
    print("  FRDBI records what a fungus was found on, so the trees outrank")
    print("  every fungus in the database. Ranking without filtering these out")
    print("  would put beech at the top of a mushroom app.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
