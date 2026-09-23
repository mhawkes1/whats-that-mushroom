#!/usr/bin/env python3
"""Where evidence about a dangerous species only works in one direction.

    python scripts/evidence_audit.py [--csv PATH]

`likelihood_for` returns 1.0 for a species that is *undescribed* for a
character. That is the right default -- silence is not a contradiction --
but it means a described/undescribed pair behaves asymmetrically, and the
two asymmetries are not equally bad.

## The one that matters

Dangerous species **described**, its lookalike **undescribed**, on the same
character. An answer can contradict the dangerous species and push it down;
nothing about that character can ever contradict the lookalike. So mass
moves *away* from the dangerous species and never toward it. A user
answering their way through the questions can talk themselves out of a
death cap and can never talk themselves into one.

## The other one

Dangerous species **undescribed**, lookalike **described**. Now the
dangerous species cannot be contradicted at all on that character: it is
immune, and it drifts upward every time a rival is ruled out. That
over-warns rather than under-warns, so it is the safer failure -- but it
is still a failure, because the app can never narrow away from it and the
refusal never lifts.

Entoloma sinuatum was the second kind, for `gill_colour`. Measured: before
it was described, a "brown gills" answer left it at 45.3%; after, the same
answer takes it to 24.9%. The confirming answer moved identically either
way, which is worth knowing -- describing a species does not make it
easier to confirm, only possible to dismiss. A consistent answer never
boosts.

## Neither described

No evidence path at all on that character. Reported last; it is a gap
rather than an asymmetry.

## What the first run found

Nothing critical. All 201 dangerous lookalike edges have at least one
character described on *both* sides, so the interrogation engine can
always separate them -- which is the property that actually matters and
is now pinned by a test. The 900-odd asymmetries below are a depth
backlog: more characters described on more species would each add a
second and third way to resolve a pair that is already resolvable.

That also puts Entoloma sinuatum's missing `gill_colour` in proportion.
It was one of five hundred cases of the same shape, not a unique hole.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from app.config import settings  # noqa: E402
from app.taxonomy_service import TaxonomyService, Toxicity  # noqa: E402

DANGEROUS = (Toxicity.DEADLY, Toxicity.SERIOUS)

ONE_WAY_AWAY = "one-way: can only move mass AWAY from the dangerous species"
ONE_WAY_STUCK = "one-way: dangerous species cannot be contradicted at all"
NO_PATH = "no evidence path: neither side is described"


def audit(taxonomy: TaxonomyService) -> list[dict]:
    findings: list[dict] = []
    for key, sp in taxonomy.species.items():
        if sp.toxicity not in DANGEROUS:
            continue

        # Both directions of the lookalike graph: a species that names this
        # one is just as confusable as one this one names.
        partners = set(sp.lookalikes)
        partners |= {k for k, o in taxonomy.species.items() if key in o.lookalikes}
        partners.discard(key)

        for other_key in sorted(partners):
            other = taxonomy.species[other_key]
            characters = set(sp.diagnostic_characters) | set(
                other.diagnostic_characters
            )
            for character in sorted(characters):
                here = bool(sp.character_states.get(character))
                there = bool(other.character_states.get(character))
                if here and there:
                    continue
                if here and not there:
                    verdict, severity = ONE_WAY_AWAY, 1
                elif there and not here:
                    verdict, severity = ONE_WAY_STUCK, 2
                else:
                    verdict, severity = NO_PATH, 3
                findings.append(
                    {
                        "severity": severity,
                        "dangerous": sp.scientific_name,
                        "dangerous_key": key,
                        "toxicity": sp.toxicity.name,
                        "lookalike": other.scientific_name,
                        "lookalike_key": other_key,
                        "character": character,
                        "dangerous_described": "yes" if here else "no",
                        "lookalike_described": "yes" if there else "no",
                        "verdict": verdict,
                    }
                )
    findings.sort(
        key=lambda f: (f["severity"], -Toxicity[f["toxicity"]], f["dangerous"],
                       f["lookalike"], f["character"])
    )
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--csv", default=None, metavar="PATH",
                    help="Also write the findings for a human to work through.")
    ap.add_argument("--show", type=int, default=25,
                    help="How many of each kind to print.")
    args = ap.parse_args()

    taxonomy = TaxonomyService.load(settings.taxonomy_path)
    findings = audit(taxonomy)

    dangerous = [s for s in taxonomy.species.values() if s.toxicity in DANGEROUS]
    print(f"Audited {len(dangerous)} DEADLY and SERIOUS species "
          f"against their lookalikes, both directions.\n")

    # The headline, and the only part of this that is pass/fail. An edge with
    # no character described on both sides cannot be resolved by any answer;
    # everything below is a matter of having fewer ways to resolve one that
    # already can be.
    stranded = []
    edges = 0
    for key, sp in taxonomy.species.items():
        if sp.toxicity not in DANGEROUS:
            continue
        partners = set(sp.lookalikes)
        partners |= {k for k, o in taxonomy.species.items() if key in o.lookalikes}
        partners.discard(key)
        for other_key in sorted(partners):
            edges += 1
            if not taxonomy.separating_characters(key, other_key):
                stranded.append((sp, taxonomy.species[other_key]))

    print("─" * 76)
    print("CAN THE ENGINE SEPARATE THEM AT ALL?")
    print("─" * 76)
    print(f"  dangerous lookalike edges           : {edges}")
    print(f"  resolvable by at least one character: {edges - len(stranded)}")
    print(f"  NO separating character at all      : {len(stranded)}")
    if stranded:
        print("\n  These cannot be resolved by any answer. Fix these first:")
        for sp, other in stranded:
            print(f"    {sp.toxicity.name:<8} {sp.scientific_name:<26} vs "
                  f"{other.scientific_name}")
    else:
        print("\n  None stranded. Everything below is depth, not a hole.")
    print()

    # Which dangerous species would gain most from another described
    # character -- the backlog, ordered so it can be worked.
    by_species: dict[str, int] = {}
    for f in findings:
        if f["severity"] <= 2:
            by_species[f["dangerous"]] = by_species.get(f["dangerous"], 0) + 1
    print("─" * 76)
    print("ONE-WAY CHARACTERS PER DANGEROUS SPECIES, worst first")
    print("─" * 76)
    for name, count in sorted(by_species.items(), key=lambda kv: -kv[1])[:12]:
        print(f"  {count:>4}  {name}")
    print()

    for severity, title in (
        (1, "MOVES MASS AWAY ONLY — the dangerous species can be ruled out, "
            "its lookalike cannot"),
        (2, "IMMUNE — the dangerous species cannot be contradicted on this "
            "character"),
        (3, "NO EVIDENCE PATH — neither side is described"),
    ):
        group = [f for f in findings if f["severity"] == severity]
        print("─" * 76)
        print(f"{title}  ({len(group)})")
        print("─" * 76)
        for f in group[: args.show]:
            print(f"  {f['toxicity']:<8} {f['dangerous']:<26} vs "
                  f"{f['lookalike']:<26} {f['character']}")
        if len(group) > args.show:
            print(f"  ... and {len(group) - args.show} more")
        print()

    if args.csv:
        out = Path(args.csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "severity", "toxicity", "dangerous", "dangerous_key",
                    "lookalike", "lookalike_key", "character",
                    "dangerous_described", "lookalike_described", "verdict",
                    "REVIEW_states_for_undescribed_side", "REVIEW_notes",
                    "REVIEWER",
                ],
            )
            writer.writeheader()
            for f in findings:
                writer.writerow({**f, "REVIEW_states_for_undescribed_side": "",
                                 "REVIEW_notes": "", "REVIEWER": ""})
        print(f"  Wrote {len(findings)} rows to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
