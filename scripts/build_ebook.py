#!/usr/bin/env python3
"""Fill the companion ebook's field data from the taxonomy.

    python scripts/build_ebook.py --ebook path/to/ebook.html --out draft.html

The ebook is a designed shell: species pages, photographs, risk badges and
season bars are all in place, and every per-species field slot is empty. This
repository holds exactly the data those slots want -- character states,
lookalikes, field notes -- for every species the book teaches.

Generating one from the other is the point. The book and the app are two
user-facing artefacts making the same claims about the same species, and two
hand-maintained copies of the same claims drift. The app already applies this
rule internally: the field form is served rather than hardcoded in the client,
and the spore print chart sits beside the answer strings it has to match.

## What it will not do

**It never overwrites a slot that already has content.** The author's own
words win over anything generated, always, so this stays safe to re-run after
the book has been edited by hand.

**It marks everything it writes.** Generated values carry a `gen` class and
the page carries a banner. Every state in the taxonomy is flagged UNREVIEWED
-- compiled from the repository's own notes rather than by a mycologist -- and
a printed field guide carries no `taxonomy_reviewed: false` the way the app
does. The output is a draft to edit, not a book to publish.

**It leaves a slot empty rather than guessing.** Where the taxonomy describes
nothing, the slot stays blank, for the same reason the matcher treats an
undescribed character as no evidence. The run then reports which rows it left
empty, so the blanks read as a worksheet rather than as an oversight.

**It never prints a taste.** See `OMITTED_CHARACTERS`.
"""

from __future__ import annotations

import argparse
import collections
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "server"))

from app.characters import CHARACTERS  # noqa: E402
from app.taxonomy_service import TaxonomyService  # noqa: E402

TAXONOMY = ROOT / "data" / "taxonomy.seed.json"

# Names the book uses that the taxonomy records under a newer combination.
SYNONYMS = {
    "Polyporus squamosus": "Cerioporus squamosus",
    "Piptoporus betulinus": "Fomitopsis betulina",
}

# `taste` is deliberately never rendered into the book.
#
# The app asks for a taste only through the interrogation engine, which checks
# first that no deadly candidate still holds mass (rule 5 -- amatoxins are
# tasteless). A printed page cannot make that check: "Taste: mild" sitting
# under a bolete is an instruction to put a mushroom in your mouth, given to a
# reader whose specimen the book has never seen. The character stays in the
# taxonomy, where the engine can gate it; it does not go on paper.
OMITTED_CHARACTERS = frozenset({"taste"})

# Which characters answer which of the book's rows. A character absent from
# here appears only in the key points, which is the right home for whole-body
# characters like bruising that the book gives no row of its own.
ROW_CHARACTERS: dict[str, tuple[str, ...]] = {
    "Trees nearby": ("habitat",),
    "Growing from": ("substrate",),
    "Season": ("season",),
    "Growth habit": ("growth_form",),
    "Cap": (
        "size", "cap_colour", "cap_surface", "cap_shape", "cap_margin",
        "cap_cuticle", "cap_attachment", "skin_thickness",
        "interior_structure", "deliquescence",
    ),
    "Gills / Pores": (
        "gill_type", "hymenium_type", "gill_colour", "gill_attachment",
        "gill_spacing", "gill_texture", "pore_colour", "latex_colour",
    ),
    "Stem": ("stipe_presence", "stipe_surface", "ring", "cortina", "stipe_texture"),
    "Base": ("volva", "stipe_base"),
    "Spore print": ("spore_print_colour",),
    "Smell": ("smell",),
}

BANNER = (
    '<div style="background:#3d1518;color:#f2ece4;padding:14px 18px;'
    'font:600 14px/1.5 system-ui,sans-serif;border-bottom:3px solid #e5484d">'
    "DRAFT — the field data on these pages was generated from "
    "data/taxonomy.seed.json, which is compiled from reference notes and has "
    "<strong>not been reviewed by a mycologist</strong>. Generated values are "
    "shown in a different colour. Edit them before this goes anywhere."
    "</div>"
)

STYLE = (
    "<style>.v.gen,.kv.gen,.fnote.gen{color:#9a6b2f}"
    ".v.gen:after{content:' \\00b7 unreviewed';font-size:.72em;opacity:.55}"
    "</style>"
)


def _esc(text: str) -> str:
    return html.escape(str(text), quote=False)


def _join(items, conjunction: str = "or") -> str:
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} {conjunction} {items[-1]}"


def _states(species, character: str) -> list[str]:
    """The described states of one character, escaped and ready to render."""
    if character in OMITTED_CHARACTERS:
        return []
    return [_esc(s) for s in species.character_states.get(character, ())]


def _lower(states: list[str]) -> list[str]:
    return [s[:1].lower() + s[1:] if s else s for s in states]


def _label(character: str) -> str:
    return _esc(CHARACTERS[character].label if character in CHARACTERS else character)


def _common_name(species) -> str:
    return _esc(species.common_names[0] if species.common_names else species.scientific_name)


def _sentence(species, characters, conjunction: str = "or") -> str:
    """Join the states of several characters into one readable phrase.

    A clause is named only when the row carries more than one, because a row
    can draw on several characters and "white or cream, yellow or olive" under
    *Gills / Pores* does not say it is describing pores. Where the row resolves
    to a single clause the label above it already says what is being described,
    and naming it again reads as a stutter.
    """
    parts = []
    for character in characters:
        states = _states(species, character)
        if states:
            parts.append((character, _join(_lower(states), conjunction)))
    if len(parts) == 1:
        return parts[0][1]
    return "; ".join(f"{_label(c).lower()}: {text}" for c, text in parts)


def _habitat(species) -> str:
    """The one row with no character behind it, restated from two that have.

    `habitat` records trees and `substrate` records what the fruit body sits
    on; between them they say whether the reader is in a wood or on a lawn,
    which is what this row asks. Nothing is added that neither character
    states -- where both are silent the row stays blank.
    """
    trees = species.character_states.get("habitat", ())
    substrate = species.character_states.get("substrate", ())
    named_trees = [t for t in trees if t != "No trees nearby"]

    if named_trees:
        return "Woodland" if len(named_trees) == len(trees) else "Woodland and open ground"
    if "Grass or lawn" in substrate:
        return "Grassland, lawns and pasture"
    if "Dung" in substrate:
        return "Pasture, on dung"
    if trees:  # only "No trees nearby"
        return "Open ground, away from trees"
    return ""


def _confused_with(species, taxonomy) -> str:
    names = [
        f"{_common_name(other)} (<i>{_esc(other.scientific_name)}</i>)"
        for other in (taxonomy.get(key) for key in species.lookalikes)
        if other is not None
    ]
    return _join(names, "and")


def _how_to_tell(species, taxonomy) -> str:
    """Prose from the characters whose states actually differ.

    Lookalikes separated the same way are named together. The death cap is
    told from the field mushroom, the horse mushroom and the charcoal burner
    by one thing -- the volva -- and writing that sentence out three times
    reads as three checks rather than the single one it is.
    """
    # (character, what the lookalike shows) -> the lookalikes showing it
    grouped: dict[tuple[str, tuple[str, ...]], list[str]] = {}
    order: list[tuple[str, tuple[str, ...]]] = []
    for key in species.lookalikes:
        other = taxonomy.get(key)
        if other is None:
            continue
        for character in taxonomy.separating_characters(species.key, other.key):
            mine, theirs = _states(species, character), _states(other, character)
            if not mine or not theirs or set(mine) == set(theirs):
                continue
            slot = (character, tuple(theirs))
            if slot not in grouped:
                grouped[slot] = []
                order.append(slot)
            grouped[slot].append(_common_name(other))
            break  # one separating character per lookalike keeps this readable

    return "; ".join(
        f"{_label(character).lower()}: "
        f"{_join(_lower(list(_states(species, character))))} here, "
        f"{_join(_lower(list(theirs)))} in {_join(grouped[(character, theirs)], 'and')}"
        for character, theirs in order
    )


def key_points(species, taxonomy) -> list[str]:
    """Up to three characters that most distinguish this species.

    Ordered by how many of its lookalikes each one separates it from, which is
    the same reasoning the interrogation engine uses when choosing a question.
    """
    described = [c for c in species.character_states if c not in OMITTED_CHARACTERS]
    scores: dict[str, int] = {}
    for key in species.lookalikes:
        other = taxonomy.get(key)
        if other is None:
            continue
        for character in described:
            mine, theirs = _states(species, character), _states(other, character)
            if mine and theirs and set(mine) != set(theirs):
                scores[character] = scores.get(character, 0) + 1

    ordered = sorted(scores, key=lambda c: (-scores[c], c))
    # Fall back to whatever is described, for species with no lookalikes.
    ordered += [c for c in described if c not in scores]

    return [
        f"{_label(c)}: {_join(_lower(_states(species, c)))}" for c in ordered[:3]
    ]


def field_values(species, taxonomy) -> dict[str, str]:
    """Everything the book's field rows ask for, keyed by its own labels."""
    values = {
        label: _sentence(species, characters)
        for label, characters in ROW_CHARACTERS.items()
    }
    values["Habitat"] = _habitat(species)
    values["Confused with"] = _confused_with(species, taxonomy)
    values["How to tell them apart"] = _how_to_tell(species, taxonomy)
    return values


ARTICLE = re.compile(r'<article class="sp".*?</article>', re.S)
LATIN = re.compile(r'<p class="latin">(.*?)</p>', re.S)
ROW = re.compile(
    r'(<span class="k">(.*?)</span><span class="dots"></span><span class="v")(></span>)'
)
KIP = re.compile(r'(<span class="kn">(\d+)</span><span class="kv")(></span>)')
FNOTE = re.compile(r'(<div class="fnote")(></div>)')


def species_for(latin: str, taxonomy: TaxonomyService):
    latin = SYNONYMS.get(latin, latin)
    return next(
        (s for s in taxonomy.species.values() if s.scientific_name == latin), None
    )


def fill(ebook_html: str, taxonomy: TaxonomyService) -> tuple[str, dict]:
    stats = {
        "pages": 0, "matched": 0, "rows": 0, "points": 0, "notes": 0,
        "unmatched": [], "empty": collections.Counter(),
    }

    def one_article(match: re.Match) -> str:
        article = match.group(0)
        stats["pages"] += 1

        latin_match = LATIN.search(article)
        if not latin_match:
            return article
        latin = html.unescape(re.sub(r"<[^>]+>", "", latin_match.group(1))).strip()

        species = species_for(latin, taxonomy)
        if species is None:
            stats["unmatched"].append(latin)
            return article
        stats["matched"] += 1

        values = field_values(species, taxonomy)
        points = key_points(species, taxonomy)

        def one_row(row: re.Match) -> str:
            label = html.unescape(row.group(2)).strip()
            value = values.get(label, "")
            if not value:
                stats["empty"][label] += 1
                return row.group(0)
            stats["rows"] += 1
            return f'{row.group(1)} class="gen">{value}</span>'

        def one_point(point: re.Match) -> str:
            index = int(point.group(2)) - 1
            if index >= len(points):
                stats["empty"]["(key point)"] += 1
                return point.group(0)
            stats["points"] += 1
            return f'{point.group(1)} class="gen">{points[index]}</span>'

        def one_note(note: re.Match) -> str:
            # `notes` is the field already written for a reader -- the same
            # string the app renders verbatim. `internal_note` is not, and
            # never appears here.
            if not species.notes:
                stats["empty"]["(field note)"] += 1
                return note.group(0)
            stats["notes"] += 1
            return f'{note.group(1)} class="gen">{_esc(species.notes)}</div>'

        article = ROW.sub(one_row, article)
        article = KIP.sub(one_point, article)
        article = FNOTE.sub(one_note, article)
        return article

    filled = ARTICLE.sub(one_article, ebook_html)
    filled = filled.replace("</head>", STYLE + "</head>", 1)
    filled = re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + BANNER, filled, count=1)
    return filled, stats


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--ebook", type=Path, required=True, help="The ebook HTML to fill.")
    ap.add_argument("--out", type=Path, required=True, help="Where to write the draft.")
    ap.add_argument("--taxonomy", type=Path, default=TAXONOMY)
    args = ap.parse_args()

    if not args.ebook.exists():
        print(f"No ebook at {args.ebook}", file=sys.stderr)
        return 1

    taxonomy = TaxonomyService.load(args.taxonomy)
    filled, stats = fill(args.ebook.read_text(encoding="utf-8"), taxonomy)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(filled, encoding="utf-8")

    print(f"species pages       : {stats['pages']}")
    print(f"matched to taxonomy : {stats['matched']}")
    print(f"field rows filled   : {stats['rows']}")
    print(f"key points filled   : {stats['points']}")
    print(f"field notes filled  : {stats['notes']}")
    if stats["unmatched"]:
        print(f"NOT in the taxonomy : {', '.join(stats['unmatched'])}")

    if stats["empty"]:
        print("\nLeft empty -- the taxonomy describes nothing here:")
        for label, count in stats["empty"].most_common():
            print(f"  {label:24} {count}")
        print("These are the rows worth a forager's attention first.")

    print(f"\nWrote {args.out} ({args.out.stat().st_size / 1_000_000:.1f} MB)")
    print("Every generated value is marked and the page carries a draft banner.")
    print("The states behind them are UNREVIEWED. Edit before publishing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
