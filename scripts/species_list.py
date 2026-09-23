#!/usr/bin/env python3
"""Write `docs/SPECIES.md` — the label space, for a human to read.

    python scripts/species_list.py

Generated rather than maintained, for the same reason the ebook's field data
is: a hand-kept second copy of 235 species drifts from the taxonomy within a
week, and the first sign of the drift is somebody quoting a toxicity that is
no longer what the app would say.

Ordered deadliest first, as the worksheet is. A reader scanning this should
meet the eleven species that can kill before anything else.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "ml"))

from app.taxonomy_service import TaxonomyService, Toxicity  # noqa: E402

OUT = ROOT / "docs" / "SPECIES.md"
TAXONOMY = ROOT / "data" / "taxonomy.seed.json"

# The user-facing wording, copied from the client's HAZARD_LABEL. There is
# no entry for NO_RECORDED_TOXICITY because the app shows none: a species
# with no recorded hazard gets a name and nothing else.
LABEL = {
    "DEADLY": ("Can kill", "Eating this can be fatal."),
    "SERIOUS": ("Causes serious illness", "Hospital treatment is usual."),
    "TOXIC": ("Causes illness", "Poisoning is reported."),
    "NO_RECORDED_TOXICITY": (
        "No recorded toxicity",
        "The references used record no toxicity for these. That is a "
        "statement about records, not about a meal: the app makes no "
        "edibility claim and shows no label at all for this group.",
    ),
}


def main() -> int:
    taxonomy = TaxonomyService.load(TAXONOMY)
    species = list(taxonomy.species.values())
    pairs = taxonomy.dangerous_pairs()

    lines = [
        "# The label space",
        "",
        "Every species this app can name, generated from `data/taxonomy.seed.json`",
        "by `python scripts/species_list.py`. Do not edit it by hand.",
        "",
        f"**{len(species)} species · {len(pairs)} lethal lookalike pairs.**",
        "",
        "It holds all 200 of the most-recorded British macrofungi "
        "(`python scripts/frdbi_gap.py --top 200`) plus the dangerous species "
        "each of those is confused with.",
        "",
        "> **None of this has been reviewed by a mycologist.** Toxicity, lookalike",
        "> relationships and diagnostic characters are compiled from standard",
        "> references and are unverified. `/health` reports",
        "> `taxonomy_reviewed: false`. See `REVIEW.md`.",
        "",
        "> **This is an identification app. It makes no edibility claim.** There",
        "> is no category meaning edible and none meaning inedible. Where a",
        "> species carries a recorded hazard the app says so; where it does not,",
        "> the app says nothing, which is neither an endorsement nor a warning.",
        "",
    ]

    for tox in (Toxicity.DEADLY, Toxicity.SERIOUS, Toxicity.TOXIC, Toxicity.NO_RECORDED_TOXICITY):
        group = sorted(
            (s for s in species if s.toxicity is tox), key=lambda s: s.scientific_name
        )
        heading, gloss = LABEL[tox.name]
        lines += [
            f"## {heading} — `{tox.name}` ({len(group)})",
            "",
            gloss,
            "",
            "| Species | Also known as | Confused with |",
            "| --- | --- | --- |",
        ]
        for sp in group:
            common = ", ".join(sp.common_names) or "—"
            looks = [
                taxonomy[k].scientific_name for k in sp.lookalikes if k in taxonomy.species
            ]
            deadly_looks = [
                f"**{n}**" if taxonomy.species[k].toxicity is Toxicity.DEADLY else n
                for k, n in zip(
                    [k for k in sp.lookalikes if k in taxonomy.species], looks
                )
            ]
            shown = ", ".join(f"*{n}*" for n in deadly_looks[:4]) or "—"
            if len(deadly_looks) > 4:
                shown += f" (+{len(deadly_looks) - 4})"
            lines.append(f"| ***{sp.scientific_name}*** | {common} | {shown} |")
        lines.append("")

    lines += [
        "---",
        "",
        "Species in **bold** under *Confused with* can kill. A row naming one is a",
        "pair the app refuses to resolve from a photograph.",
    ]

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} — {len(species)} species, {len(pairs)} lethal pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
