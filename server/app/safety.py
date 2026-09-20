"""The safety layer.

Everything the model produces passes through here before a user sees it.
The rules are deliberately blunt and deliberately conservative, because the
failure mode they guard against is someone being poisoned.

Design rules, in order of precedence:

1. The app never asserts edibility. Not "edible", not "safe", not "choice".
   The word does not appear in any user-facing output path.
2. If a deadly species is plausibly in play, the warning is shown regardless
   of how confident the model is about something else.
3. If the top candidates straddle a known dangerous pair, no species-level
   answer is given at all. The app names the group and asks for the
   character that separates them.
4. Below the calibrated confidence threshold, the app declines to name a
   species. Declining is a correct answer, not a failure.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .taxonomy_service import TaxonomyService, Toxicity


class Verdict(str, Enum):
    """What the app is willing to tell the user."""

    SPECIES = "species"  # Confident enough to name one species.
    GROUP = "group"  # Genus or group only.
    UNCERTAIN = "uncertain"  # Candidates listed, nothing asserted.
    DANGEROUS_GROUP = "dangerous_group"  # Lethal species plausibly in play.
    OUT_OF_SCOPE = "out_of_scope"  # Probably not in the label space at all.


@dataclass
class Candidate:
    species_key: str
    scientific_name: str
    common_names: list[str]
    confidence: float
    toxicity: str
    genus: str


@dataclass
class SafetyAssessment:
    verdict: Verdict
    headline: str
    detail: str
    candidates: list[Candidate]
    warnings: list[str] = field(default_factory=list)
    # Characters that would most reduce the remaining ambiguity.
    requested_evidence: list[str] = field(default_factory=list)
    deadly_in_play: bool = False


# Never rendered as advice, only as a warning. Note the absence of any
# positive edibility language anywhere in this module.
DEADLY_WARNING = (
    "One or more candidates for this photograph are species that can kill. "
    "Do not eat this mushroom. A photograph cannot rule these out."
)

GROUP_ONLY_DETAIL = (
    "The candidates cannot be separated from this photograph alone. "
    "They differ by characters that are not visible here."
)

UNIVERSAL_DISCLAIMER = (
    "This app identifies possibilities, not certainties, and never tells you "
    "whether something is safe to eat. Never eat a wild mushroom identified "
    "only by an app."
)


class SafetyLayer:
    def __init__(
        self,
        taxonomy: TaxonomyService,
        confidence_threshold: float = 0.80,
        group_threshold: float = 0.50,
        ood_threshold: float = 0.20,
        dangerous_mass_threshold: float = 0.02,
    ):
        self.taxonomy = taxonomy
        # Fitted empirically by ml/fungi_ml/calibrate.py, not chosen because
        # it sounds reassuring.
        self.confidence_threshold = confidence_threshold
        self.group_threshold = group_threshold
        self.ood_threshold = ood_threshold
        # A deadly species holding even 2% of the probability mass triggers
        # the warning. Deliberately low: the cost of a false alarm is a
        # wasted foraging trip, the cost of a miss is a liver transplant.
        self.dangerous_mass_threshold = dangerous_mass_threshold

    @classmethod
    def from_calibration(
        cls, taxonomy: TaxonomyService, calibration_path: str | Path
    ) -> "SafetyLayer":
        blob = json.loads(Path(calibration_path).read_text(encoding="utf-8"))
        return cls(taxonomy, confidence_threshold=blob["confidence_threshold"])

    def _to_candidates(self, ranked: list[tuple[str, float]]) -> list[Candidate]:
        out = []
        for key, score in ranked:
            sp = self.taxonomy.get(key)
            if sp is None:
                continue
            out.append(
                Candidate(
                    species_key=key,
                    scientific_name=sp.scientific_name,
                    common_names=list(sp.common_names),
                    confidence=round(float(score), 4),
                    toxicity=sp.toxicity.name,
                    genus=sp.genus,
                )
            )
        return out

    def deadly_probability_mass(self, ranked: list[tuple[str, float]]) -> float:
        """Total probability sitting on species that can kill."""
        deadly = self.taxonomy.deadly_keys()
        return sum(score for key, score in ranked if key in deadly)

    def dangerous_group_mass(self, ranked: list[tuple[str, float]]) -> float:
        """Probability on any genus that contains a deadly species.

        Broader than deadly mass alone, and the more useful trigger: a user
        who cannot tell *Amanita phalloides* from *Amanita rubescens* is in
        danger either way.
        """
        dangerous_genera = self.taxonomy.dangerous_genera()
        return sum(
            score
            for key, score in ranked
            if self.taxonomy.genus_of(key) in dangerous_genera
        )

    def straddles_dangerous_pair(
        self, ranked: list[tuple[str, float]], top_n: int = 5
    ) -> tuple[str, str] | None:
        """Whether the leading candidates include both halves of a lethal pair."""
        top_keys = [k for k, _ in ranked[:top_n]]
        pairs = self.taxonomy.dangerous_pairs()
        for i, a in enumerate(top_keys):
            for b in top_keys[i + 1 :]:
                if tuple(sorted((a, b))) in pairs:
                    return (a, b)
        return None

    def assess(self, ranked: list[tuple[str, float]]) -> SafetyAssessment:
        """Turn a calibrated probability distribution into what we will say.

        `ranked` must be sorted descending and must be calibrated. Feeding
        raw softmax output here defeats the entire design.
        """
        if not ranked:
            return SafetyAssessment(
                verdict=Verdict.OUT_OF_SCOPE,
                headline="No identification possible",
                detail="No candidates were produced for this image.",
                candidates=[],
                warnings=[UNIVERSAL_DISCLAIMER],
            )

        candidates = self._to_candidates(ranked[:8])
        top_key, top_score = ranked[0]
        warnings: list[str] = []

        deadly_mass = self.deadly_probability_mass(ranked)
        group_mass = self.dangerous_group_mass(ranked)
        deadly_in_play = (
            deadly_mass >= self.dangerous_mass_threshold
            or group_mass >= self.dangerous_mass_threshold * 5
        )

        if deadly_in_play:
            warnings.append(DEADLY_WARNING)

        # Rule 0: the image probably isn't something we know at all.
        if top_score < self.ood_threshold:
            return SafetyAssessment(
                verdict=Verdict.OUT_OF_SCOPE,
                headline="This doesn't match anything I know well",
                detail=(
                    "The photograph does not resemble any species in my range with "
                    "reasonable confidence. It may be a species I was never trained "
                    "on, or the photograph may not show enough of the mushroom."
                ),
                candidates=candidates,
                warnings=warnings + [UNIVERSAL_DISCLAIMER],
                requested_evidence=["cap_surface", "gill_type", "stipe_base", "substrate"],
                deadly_in_play=deadly_in_play,
            )

        # Rule 1: a lethal pair is in play. Never resolve this from a photo.
        pair = self.straddles_dangerous_pair(ranked)
        if pair is not None:
            a, b = pair
            separators = self.taxonomy.separating_characters(a, b)
            return SafetyAssessment(
                verdict=Verdict.DANGEROUS_GROUP,
                headline="I can't safely narrow this down",
                detail=(
                    f"The leading candidates include both {self.taxonomy[a].scientific_name} "
                    f"and {self.taxonomy[b].scientific_name}. These are confused with each "
                    "other in the field, and one of them can kill. I will not choose between "
                    "them from a photograph."
                ),
                candidates=candidates,
                warnings=[DEADLY_WARNING, UNIVERSAL_DISCLAIMER],
                requested_evidence=separators,
                deadly_in_play=True,
            )

        # Rule 2: confident enough to name a species.
        if top_score >= self.confidence_threshold:
            sp = self.taxonomy[top_key]
            return SafetyAssessment(
                verdict=Verdict.SPECIES,
                headline=f"Most likely {sp.scientific_name}",
                detail=sp.notes or "",
                candidates=candidates,
                warnings=warnings + [UNIVERSAL_DISCLAIMER],
                requested_evidence=self.taxonomy.confirming_characters(top_key),
                deadly_in_play=deadly_in_play,
            )

        # Rule 3: confident at genus level but not species.
        genus_mass: dict[str, float] = {}
        for key, score in ranked:
            genus_mass[self.taxonomy.genus_of(key)] = (
                genus_mass.get(self.taxonomy.genus_of(key), 0.0) + score
            )
        best_genus, best_genus_score = max(genus_mass.items(), key=lambda kv: kv[1])

        if best_genus_score >= self.group_threshold:
            return SafetyAssessment(
                verdict=Verdict.GROUP,
                headline=f"This looks like a {best_genus} species",
                detail=(
                    f"{GROUP_ONLY_DETAIL} I'm reasonably confident about the genus "
                    f"({best_genus_score:.0%}) but not about which species within it."
                ),
                candidates=candidates,
                warnings=warnings + [UNIVERSAL_DISCLAIMER],
                requested_evidence=self.taxonomy.genus_discriminators(best_genus),
                deadly_in_play=deadly_in_play,
            )

        # Rule 4: not confident about anything. Say so.
        return SafetyAssessment(
            verdict=Verdict.UNCERTAIN,
            headline="I'm not sure what this is",
            detail=(
                "No candidate is likely enough to name. The possibilities below are "
                "ranked, but the photograph does not settle between them."
            ),
            candidates=candidates,
            warnings=warnings + [UNIVERSAL_DISCLAIMER],
            requested_evidence=self._most_informative_characters(ranked),
            deadly_in_play=deadly_in_play,
        )

    def _most_informative_characters(
        self, ranked: list[tuple[str, float]], top_n: int = 5
    ) -> list[str]:
        """Characters that appear across the leading candidates.

        A crude proxy for information gain, but an effective one: a character
        that several plausible candidates are defined by is worth asking about.
        """
        counts: dict[str, float] = {}
        for key, score in ranked[:top_n]:
            sp = self.taxonomy.get(key)
            if sp is None:
                continue
            for char in sp.diagnostic_characters:
                counts[char] = counts.get(char, 0.0) + score
        return [c for c, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:4]]
