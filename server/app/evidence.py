"""Turning a user's answer into evidence.

When a user says "the gills are white", that should change which species are
still plausible. Doing it properly needs two things: a table saying which
states each species actually shows, and a model of how much to trust the
observation. This module is the second. The first is `character_states` in
the taxonomy, which is empty pending the field-character review in
`docs/REVIEW.md`.

## The shape of the update

For each candidate, the answer is either consistent with what that species
shows, inconsistent with it, or says nothing because the species declares no
states for that character. The three cases get three likelihoods, and the
candidate distribution is re-weighted by them and renormalised.

The third case is the important one right now. **No declared states means no
evidence, not a mismatch.** A species we have not yet described cannot be
ruled out by an answer, so its likelihood is exactly 1.0 and the update
leaves it alone. With the table empty, every likelihood is 1.0 and the
ranking does not move at all -- which is the honest behaviour, and is
deliberately visible rather than disguised by a heuristic that fires
occasionally on unrelated grounds.

## Why the asymmetry

A consistent answer does not boost a species. Only inconsistency moves
anything, and it moves things down. That keeps the update conservative: the
evidence a user supplies can eliminate, but cannot manufacture confidence in
something the classifier did not already rank.

Contradicting a deadly species moves it far less than contradicting a
harmless one. This is the same asymmetry the risk matrix encodes, applied to
evidence rather than to loss: being wrong about a brittlegill costs a meal,
being wrong about a death cap costs a life, so dismissing the death cap has
to clear a higher bar. A user peering at gills in failing light is a noisy
sensor, and the cost of trusting that sensor is not symmetric.

Concretely, one contradicting observation quarters an ordinary candidate and
only roughly halves a deadly one, so ruling out a death cap takes several
independent observations rather than one.

Finally, nothing here may push a deadly species below the threshold at which
the safety layer stops warning about it. `CLAUDE.md` rule 3 -- never round
away a small probability of death -- is a property of the whole pipeline, and
an answer-weighting step that could quietly extinguish a 3% death cap would
break it from the inside.
"""

from __future__ import annotations

from dataclasses import dataclass

from .taxonomy_service import Species, TaxonomyService, Toxicity

# A consistent answer leaves a candidate where it is. Evidence here only ever
# eliminates; it never invents confidence the classifier did not supply.
CONSISTENT = 1.0

# An answer that contradicts what a species shows. 0.25 means one
# contradiction quarters the candidate relative to its consistent rivals.
INCONSISTENT = 0.25

# The same, for a species that can kill. Deliberately much closer to 1.0:
# dismissing a lethal candidate should take several independent observations,
# not one glance in bad light.
DEADLY_INCONSISTENT = 0.55

# A species that declares no states for this character. Not a mismatch --
# an absence of description on our side, which is not evidence about the
# mushroom. This is what makes the mechanism a no-op while the table is empty.
UNDESCRIBED = 1.0

# No answer may drive a deadly species below this. Matches the threshold in
# docs/SAFETY.md at which a deadly candidate still triggers the full warning.
DEADLY_PROBABILITY_FLOOR = 0.02


@dataclass(frozen=True)
class Evidence:
    """How one answer bears on one species."""

    species_key: str
    likelihood: float
    verdict: str  # "consistent" | "inconsistent" | "undescribed"


def likelihood_for(species: Species, character_key: str, answer: str) -> Evidence:
    """How much one answer supports or undermines one species."""
    states = species.character_states.get(character_key)

    if not states:
        return Evidence(species.key, UNDESCRIBED, "undescribed")

    # Compared case-insensitively and whitespace-trimmed. The answer strings
    # are validated against the character catalogue before they reach here,
    # so this is belt-and-braces rather than parsing.
    normalised = answer.strip().casefold()
    if any(state.strip().casefold() == normalised for state in states):
        return Evidence(species.key, CONSISTENT, "consistent")

    inconsistent = (
        DEADLY_INCONSISTENT if species.toxicity is Toxicity.DEADLY else INCONSISTENT
    )
    return Evidence(species.key, inconsistent, "inconsistent")


def reweight(
    ranked: list[tuple[str, float]],
    character_key: str,
    answer: str,
    taxonomy: TaxonomyService,
) -> list[tuple[str, float]]:
    """Apply one answer to a candidate distribution, highest first.

    Returns the input unchanged when the answer is blank, when nothing is
    described for this character, or when the update would leave no mass at
    all -- in each case we have learned nothing and should say so by doing
    nothing.
    """
    if not answer or not answer.strip():
        return ranked

    weighted: list[tuple[str, float]] = []
    moved = False

    for key, score in ranked:
        species = taxonomy.get(key)
        if species is None:
            weighted.append((key, score))
            continue

        evidence = likelihood_for(species, character_key, answer)
        if evidence.verdict != "undescribed":
            moved = True
        weighted.append((key, score * evidence.likelihood))

    # Nothing in the candidate set declares this character, so the answer
    # carries no information about any of them.
    if not moved:
        return ranked

    total = sum(score for _, score in weighted)
    if total <= 0:
        return ranked

    normalised = [(key, score / total) for key, score in weighted]
    floored = _restore_deadly_floor(ranked, normalised, taxonomy)
    return sorted(floored, key=lambda kv: -kv[1])


def _restore_deadly_floor(
    before: list[tuple[str, float]],
    after: list[tuple[str, float]],
    taxonomy: TaxonomyService,
) -> list[tuple[str, float]]:
    """Stop an answer from extinguishing a deadly candidate.

    A species that can kill, and that the classifier put at or above the
    warning threshold, stays at or above it however the answer went. The user
    may still be looking at it; what they have told us is that it does not
    match the description we hold, and our descriptions are not yet reviewed.

    Only candidates that were already above the floor are protected. An
    answer cannot promote a deadly species the model never seriously
    proposed -- that would manufacture alarm rather than preserve it.
    """
    deadly = taxonomy.deadly_keys()
    prior = dict(before)

    adjusted: list[tuple[str, float]] = []
    changed = False
    for key, score in after:
        if (
            key in deadly
            and prior.get(key, 0.0) >= DEADLY_PROBABILITY_FLOOR
            and score < DEADLY_PROBABILITY_FLOOR
        ):
            adjusted.append((key, DEADLY_PROBABILITY_FLOOR))
            changed = True
        else:
            adjusted.append((key, score))

    if not changed:
        return after

    total = sum(score for _, score in adjusted)
    return [(key, score / total) for key, score in adjusted] if total > 0 else after


def described_coverage(taxonomy: TaxonomyService) -> dict[str, float]:
    """How much of the character-state table has actually been filled in.

    The mechanism is only as good as the data behind it, and with the table
    empty it is a no-op by design. Reporting coverage keeps that visible
    rather than letting a silent no-op read as a broken feature.
    """
    total = len(taxonomy.species)
    if total == 0:
        return {"species": 0, "described": 0, "fraction": 0.0, "state_entries": 0}

    described = sum(1 for s in taxonomy.species.values() if s.character_states)
    entries = sum(len(s.character_states) for s in taxonomy.species.values())
    return {
        "species": total,
        "described": described,
        "fraction": described / total,
        "state_entries": entries,
    }
