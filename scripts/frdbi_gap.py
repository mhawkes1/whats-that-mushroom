#!/usr/bin/env python3
"""What the label space is missing, measured against how often things are found.

    python scripts/frdbi_gap.py [--top 100]

The label space was assembled around danger: eleven species that can kill, and
the ordinary ones each of those is mistaken for. That is the right skeleton and
it says nothing about what a person on a walk actually points a phone at.

`data/frdbi-records.csv` is the other axis -- every taxon in the Fungal Records
Database of Britain and Ireland with its record count, exported 2026-09-22.
This compares the two.

## Three things the raw ranking is not

**It is not a list of fungi.** FRDBI records host associations, so beech leads
the whole database at 124,946 and every fungus sits below it. Cattle, horses
and rabbits are in there too, because dung fungi are recorded against what
produced the dung.

**It is not a list of things this app can be asked about.** Tar spot, oak
mildew and bramble rust are recorded in their thousands and are blemishes on a
leaf. A flow built around caps, gills and spore prints has nothing to say to
them, and the honest answer is out of scope.

**It is not a list of what a beginner photographs.** Every record was made by
somebody who already knew what they were looking at, and recorders log what
recorders find interesting. It is the best available proxy and it is a proxy.

Filtering happens at genus (`data/frdbi-genera.csv`), because a genus is a
judgement somebody can check and eighteen thousand species is not. A taxon
whose genus is unclassified is reported rather than silently dropped -- a
missing genus would quietly shrink both halves of the coverage figure.

## Slime moulds are neither, and matter anyway

`Lycogala`, `Reticularia` and `Stemonitis` are not fungi. They are recorded in
FRDBI, they are conspicuous, and people photograph them. They can never be
identified here, so what the app owes them is the out-of-scope answer rather
than the nearest mushroom -- which makes them a free source of the negatives
`ood.py` is otherwise short of.

## What an addition actually costs

A species is never added alone. The label space is a graph, and adding a
common species without the dangerous things it is confused with makes the app
*more* dangerous: it teaches a name the model will reach for and withholds the
one it should have refused over. So the report prints, for each candidate, the
dangerous species already known in its genus.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "ml"))

from app.taxonomy_service import TaxonomyService, Toxicity  # noqa: E402

RECORDS = ROOT / "data" / "frdbi-records.csv"
GENERA = ROOT / "data" / "frdbi-genera.csv"
TAXONOMY = ROOT / "data" / "taxonomy.seed.json"

# FRDBI uses current combinations; the taxonomy does not always. Matching on
# the printed string alone would report a species as missing when it is
# already there under an older name -- the one error that would make this
# report actively harmful, because it sends somebody off to add a duplicate.
#
# Only a few entries do that work today. The rest name species the label space
# does not yet hold, where the older name is a note for whoever adds them:
# reference books are still full of Boletus badius and Hygrocybe virginea, and
# a search for training images will need both strings.
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
    "Ampulloclitocybe clavipes": "Clitocybe clavipes",
    "Infundibulicybe geotropa": "Clitocybe geotropa",
    "Mucidula mucida": "Oudemansiella mucida",
    "Atheniella adonis": "Mycena adonis",
    "Phloeomana speirea": "Mycena speirea",
}

# What a photograph of this is most likely to be confused with, where the
# danger is not obvious from the genus alone. Compiled from the same
# references as the rest of the taxonomy and UNREVIEWED, like all of it.
RISK_NOTE = {
    "Laccaria laccata": "the deceiver -- variable enough that beginners match it to almost anything",
    "Pluteus cervinus": "free pink gills; Volvopluteus and young Amanita both read similarly",
    "Armillaria mellea": "clustered on wood, which is the funeral bell's own habit",
    "Coprinellus micaceus": "clustered on wood, and Galerina marginata is too",
    "Gymnopilus penetrans": "orange, clustered, on conifer wood -- the Galerina situation again",
    "Clitocybe fragrans": "a small white Clitocybe; the muscarine species are small white Clitocybes",
    "Psathyrella candolleana": "clustered, pale, on buried wood",
    "Psathyrella piluliformis": "clustered on stumps, beside Hypholoma and Galerina",
    "Inocybe geophylla": "white Inocybe -- muscarine, and mistaken for small field species",
    "Cystoderma amianthinum": "granular Lepiota-like cap",
    "Chlorophyllum rhacodes": "shaggy parasol; confused with C. brunneum, already in the label space",
    "Flammulina velutipes": "clustered on wood in winter, when Galerina also fruits",
    "Hebeloma crustuliniforme": "poison pie -- a plain brown agaric in exactly the places beginners look",
    "Entoloma conferendum": "pink-spored Entoloma; the genus holds E. sinuatum, already known and SERIOUS",
    "Panaeolus papilionaceus": "small brown mushroom on dung, beside several Panaeolina and Psilocybe",
    "Lacrymaria lacrymabunda": "dark-gilled, clustered, in grass and paths",
    "Ampulloclitocybe clavipes": "a Clitocybe by any other name, and the genus contains the muscarine species",
    "Infundibulicybe geotropa": "likewise -- a big funnel Clitocybe",
    "Megacollybia platyphylla": "broad, pale, on buried wood",
    "Stropharia semiglobata": "dung, small, slimy, and Panaeolus territory",
}


def load_records() -> list[tuple[str, int]]:
    with RECORDS.open(encoding="utf-8") as fh:
        return [(r["name"], int(r["records"])) for r in csv.DictReader(fh)]


def load_genera() -> dict[str, str]:
    lines = [l for l in GENERA.read_text(encoding="utf-8").splitlines() if not l.startswith("#")]
    return {r["genus"]: r["kind"] for r in csv.DictReader(lines)}


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--top", type=int, default=100,
                    help="How many of the most-recorded macrofungi to report on.")
    args = ap.parse_args()

    taxonomy = TaxonomyService.load(TAXONOMY)
    known = {s.scientific_name: s for s in taxonomy.species.values()}
    genera = load_genera()
    records = load_records()

    kinds: dict[str, list[tuple[str, int]]] = {
        "fungus": [], "slime-mould": [], "micro": [], "host": [], "?": [],
    }
    for name, count in records:
        kinds[genera.get(name.split()[0], "?")].append((name, count))

    fungi = kinds["fungus"]
    wanted = fungi[: args.top]

    def resolve(name: str):
        for candidate in (name, SYNONYMS.get(name, "")):
            if candidate in known:
                return known[candidate]
        return None

    covered = [(n, c, sp) for n, c in wanted if (sp := resolve(n))]
    missing = [(n, c) for n, c in wanted if resolve(n) is None]

    print(f"FRDBI taxa, exported 2026-09-22 : {len(records):,}")
    print(f"  classified as macrofungi      : {len(fungi):,}")
    print(f"  hosts (plants, animals)       : {len(kinds['host']):,}")
    print(f"  leaf spots, mildews, rusts    : {len(kinds['micro']):,}")
    print(f"  slime moulds                  : {len(kinds['slime-mould']):,}")
    print(f"  genus not yet classified      : {len(kinds['?']):,}")
    print()

    # The quiet failure this report could have: a genus nobody classified,
    # holding a species common enough to belong in the answer, counted as
    # nothing and never mentioned. Prove it did not happen rather than assume.
    cutoff = wanted[-1][1]
    intruders = [(n, c) for n, c in kinds["?"] if c >= cutoff]
    if intruders:
        print(f"  !! {len(intruders)} unclassified taxa out-record the cutoff "
              f"of {cutoff:,}.")
        print("     The figures below are wrong until these are classified in")
        print("     data/frdbi-genera.csv:")
        for name, count in intruders[:15]:
            print(f"       {count:>7,}  {name}")
        print()

    print(f"Of the {args.top} most-recorded British macrofungi:")
    print(f"  already in the label space    : {len(covered):3}  "
          f"({len(covered) / len(wanted):.0%})")
    print(f"  missing                       : {len(missing):3}")
    print(f"  record-count cutoff           : {wanted[-1][1]:,} "
          f"({wanted[-1][0]})")
    print()

    print("─" * 76)
    print(f"MISSING FROM THE TOP {args.top}, most-recorded first")
    print("─" * 76)
    for name, count in missing:
        genus = name.split()[0]
        siblings = [s for s in known.values() if s.genus == genus]
        dangerous = [s for s in siblings
                     if s.toxicity in (Toxicity.DEADLY, Toxicity.SERIOUS)]
        print(f"  {count:>7,}  {name}")
        if dangerous:
            print("           ALREADY KNOWN IN THIS GENUS AND DANGEROUS: "
                  f"{', '.join(s.scientific_name for s in dangerous)}")
        elif siblings:
            print(f"           genus already represented by "
                  f"{', '.join(s.scientific_name for s in siblings[:3])}")
        if name in RISK_NOTE:
            print(f"           ! {RISK_NOTE[name]}")

    print()
    print("─" * 76)
    print("WHAT THE RANKING WOULD HAVE CONTAINED WITHOUT FILTERING")
    print("─" * 76)
    for label, key in (("hosts", "host"), ("leaf spots and rusts", "micro"),
                       ("slime moulds", "slime-mould")):
        rows = kinds[key][:4]
        if not rows:
            continue
        print(f"  {label}:")
        for name, count in rows:
            print(f"    {count:>7,}  {name}")
    print()
    print("  Beech alone outranks every fungus in the database. A 'top 100'")
    print("  taken from FRDBI without filtering is a list of trees.")

    if kinds["?"][:1]:
        print()
        print("─" * 76)
        print("UNCLASSIFIED, most-recorded first")
        print("─" * 76)
        print(f"  All below the cutoff of {cutoff:,}, so none of them belongs in")
        print(f"  the top {args.top}. Classify their genus in data/frdbi-genera.csv")
        print("  before running --top much deeper than this.")
        for name, count in kinds["?"][:8]:
            print(f"    {count:>7,}  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
