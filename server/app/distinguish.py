"""How to tell a named species from the things it is confused with.

The one piece of reference content this app can offer that the
PictureMushroom-class apps cannot, and it falls out of data that already
exists for a different reason.

**Why not a characteristics table.** Measured 2026-10-29, across all 244
species: notes and common names are complete, `lookalikes` is 92% complete,
and everything else is thin -- cap colour 66%, substrate 62%, spore print
51%, smell 15%, with a median of five described characters per species. The
taxonomy holds nothing at all for cap diameter, height, nutrient mode,
associated plants, family or order. A table of those would be two-thirds
empty rows, and `build_ebook.py` already demonstrates exactly that: 114 of
338 field rows fill.

The reason is structural rather than an oversight. `character_states` was
built as a classifier tiebreaker -- it holds only what separates a species
from its lookalikes -- so it is thin as a description and dense as a
comparison. This renders it as the second thing, which is what it is.

**And it is more useful that way.** Somebody holding a white mushroom is
not helped by "cap 4-10 cm". They are helped by knowing that the thing in
their hand could be two species, and which single feature tells them apart.

**Rule 1 is the live risk here and is handled in one place.** A comparison
invites a judgement the app does not make: put a TOXIC species beside one
with no recorded hazard and a reader supplies "so the other one is fine".
So this returns the recorded hazard and nothing else, exactly as the
candidate list does -- `NO_RECORDED_TOXICITY` renders as nothing at all --
and the framing is only ever how to TELL THEM APART. It never says which to
prefer, because the app has no view on that and saying so would be an
edibility claim wearing a comparison's clothes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .characters import CHARACTERS
from .taxonomy_service import TaxonomyService, Toxicity

# Enough to be useful, few enough to read standing up. The list is ordered
# by how well the pair is separated, so a cut here loses the weakest rows.
MAX_LOOKALIKES = 4
MAX_DIFFERENCES = 3


@dataclass(frozen=True)
class Difference:
    """One character, split into what it can and cannot settle.

    NOT "this shows A, that shows B". The list-width convention makes the
    two sides routinely overlap: a deadly species lists its states
    GENEROUSLY, so that a contradiction cannot falsely dismiss something
    lethal, while the safe half of the pair lists them tightly. The funeral
    bell therefore declares all four ring states and honey fungus declares
    one, and rendering that as "funeral bell: four things / honey fungus:
    firm skirt" invites a reader to check the ring, see a firm skirt, and
    conclude honey fungus -- when a firm skirt is exactly the state both
    can show.

    So the states are split three ways and the shared ones are SHOWN. A
    feature that cannot settle the question is the single most important
    thing to say on a page headed "how to tell them apart", because it is
    the one a user will otherwise settle it with.
    """

    character: str
    label: str
    #: States only this species shows. Seeing one rules the other out.
    this_only: tuple[str, ...]
    #: States only the lookalike shows. Seeing one rules THIS out.
    other_only: tuple[str, ...]
    #: States both can show. Decides nothing, and must be said so.
    shared: tuple[str, ...]

    @property
    def decides_both_ways(self) -> bool:
        return bool(self.this_only) and bool(self.other_only)


@dataclass(frozen=True)
class Comparison:
    species_key: str
    scientific_name: str
    common_names: tuple[str, ...]
    toxicity: str
    differences: tuple[Difference, ...] = field(default_factory=tuple)

    @property
    def separable(self) -> bool:
        return bool(self.differences)


def _difference(
    taxonomy: TaxonomyService, this_key: str, other_key: str, character: str
) -> Difference | None:
    """One row, or None where the character cannot carry one.

    A character both species declare identically is dropped: it reads as a
    check and is not one. The funeral bell and the sheathed woodtuft both
    grow on dead wood, and a row saying so under "how to tell them apart"
    is worse than no row, because somebody will use it.
    """
    this_sp, other_sp = taxonomy.get(this_key), taxonomy.get(other_key)
    if this_sp is None or other_sp is None:
        return None
    mine = set(this_sp.character_states.get(character, ()))
    theirs = set(other_sp.character_states.get(character, ()))
    if not mine or not theirs:
        return None
    this_only, other_only = mine - theirs, theirs - mine
    if not this_only and not other_only:
        # Identical lists. Reads as a check and is not one.
        return None
    spec = CHARACTERS.get(character)
    order = list(spec.options) if spec and spec.options else []

    def tidy(states: set[str]) -> tuple[str, ...]:
        """In the catalogue's own order, so rows read consistently."""
        return tuple(sorted(states, key=lambda s: (order.index(s) if s in order else 99, s)))

    return Difference(
        character=character,
        label=spec.label if spec else character.replace("_", " ").capitalize(),
        this_only=tidy(this_only),
        other_only=tidy(other_only),
        shared=tidy(mine & theirs),
    )


def comparisons(taxonomy: TaxonomyService, species_key: str) -> list[Comparison]:
    """What this species is confused with, and what separates them.

    Deliberately includes a lookalike with NO usable difference, carrying an
    empty `differences`. That is a true and useful thing to be told -- these
    two are confused in the field and nothing recorded here separates them
    from a photograph -- and dropping it would quietly turn a gap in the
    data into an absence of risk. The client says so in words.

    Dangerous lookalikes come first regardless of how well separated they
    are, because the ordering question is which one it hurts to miss.
    """
    species = taxonomy.get(species_key)
    if species is None:
        return []

    out: list[Comparison] = []
    for other_key in species.lookalikes:
        other = taxonomy.get(other_key)
        if other is None:
            # A lookalike outside the label space. A test forbids this, so
            # reaching here means the taxonomy changed under us; skip it
            # rather than render a name with nothing behind it.
            continue
        rows = []
        for character in taxonomy.separating_characters(species_key, other_key):
            row = _difference(taxonomy, species_key, other_key, character)
            if row is not None:
                rows.append(row)
            if len(rows) == MAX_DIFFERENCES:
                break
        # A character that settles the question from either direction beats
        # one that can only rule in. Both are kept; the better one leads.
        rows.sort(key=lambda d: (not d.decides_both_ways, len(d.shared)))
        out.append(
            Comparison(
                species_key=other_key,
                scientific_name=other.scientific_name,
                common_names=tuple(other.common_names),
                toxicity=other.toxicity.name,
                differences=tuple(rows),
            )
        )

    out.sort(key=lambda c: (-_hazard_rank(c.toxicity), -len(c.differences)))
    return out[:MAX_LOOKALIKES]


def _hazard_rank(name: str) -> int:
    try:
        return int(Toxicity[name])
    except KeyError:
        return 0
