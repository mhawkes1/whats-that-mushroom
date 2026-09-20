"""Taxonomy helpers and the dangerous-confusion risk model.

The central idea of this project is that not all classification errors are
equal. Mistaking one *Russula* for another is a nuisance. Mistaking
*Amanita phalloides* for *Agaricus campestris* kills the user. Standard
top-1 accuracy cannot see the difference, so we model it explicitly and
carry the distinction through training, evaluation and inference.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path


class Toxicity(IntEnum):
    """Consequence of eating the species, not of misidentifying it."""

    DEADLY = 4  # Contains amatoxins/orellanine/gyromitrin; can be fatal.
    SERIOUS = 3  # Hospitalisation likely (e.g. rhabdomyolysis, severe GI).
    TOXIC = 2  # Significant illness, rarely life-threatening.
    INEDIBLE = 1  # Unpalatable or mildly upsetting.
    UNKNOWN = 0  # Not assessed. Treated as TOXIC by the safety layer.


@dataclass(frozen=True)
class Species:
    """A single taxon in the model's label space."""

    key: str  # Stable slug, e.g. "amanita-phalloides"
    scientific_name: str
    genus: str
    common_names: tuple[str, ...] = ()
    toxicity: Toxicity = Toxicity.UNKNOWN
    gbif_key: int | None = None
    # Species this one is realistically confused with in the field, by a
    # non-expert working from photographs.
    lookalikes: tuple[str, ...] = ()
    # Characters that separate this species from its lookalikes. The
    # interrogation engine turns these into the next question it asks.
    diagnostic_characters: tuple[str, ...] = ()
    notes: str = ""


@dataclass
class Taxonomy:
    """The label space, plus the risk structure layered over it."""

    species: dict[str, Species] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> "Taxonomy":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        species = {}
        for entry in raw["species"]:
            species[entry["key"]] = Species(
                key=entry["key"],
                scientific_name=entry["scientific_name"],
                genus=entry.get("genus") or entry["scientific_name"].split()[0],
                common_names=tuple(entry.get("common_names", ())),
                toxicity=Toxicity[entry.get("toxicity", "UNKNOWN")],
                gbif_key=entry.get("gbif_key"),
                lookalikes=tuple(entry.get("lookalikes", ())),
                diagnostic_characters=tuple(entry.get("diagnostic_characters", ())),
                notes=entry.get("notes", ""),
            )
        return cls(species=species)

    def __contains__(self, key: object) -> bool:
        return key in self.species

    def __getitem__(self, key: str) -> Species:
        return self.species[key]

    def get(self, key: str) -> Species | None:
        return self.species.get(key)

    def genus_of(self, key: str) -> str:
        sp = self.species.get(key)
        return sp.genus if sp else key.split("-")[0]

    def deadly_keys(self) -> set[str]:
        return {k for k, s in self.species.items() if s.toxicity is Toxicity.DEADLY}

    def dangerous_pairs(self) -> set[tuple[str, str]]:
        """Unordered pairs where confusing one for the other could kill.

        A pair qualifies when one member is DEADLY, the other is not, and the
        two are plausibly confused in the field. Both the declared lookalike
        graph and same-genus membership count as "plausibly confused" --
        within a genus containing a deadly species, every member is suspect.
        """
        pairs: set[tuple[str, str]] = set()
        for key, sp in self.species.items():
            if sp.toxicity is not Toxicity.DEADLY:
                continue
            candidates = set(sp.lookalikes)
            # Anything sharing the genus, plus anything that names this
            # species as its own lookalike.
            for other_key, other in self.species.items():
                if other_key == key:
                    continue
                if other.genus == sp.genus or key in other.lookalikes:
                    candidates.add(other_key)
            for other_key in candidates:
                other = self.species.get(other_key)
                if other is None or other.toxicity is Toxicity.DEADLY:
                    continue
                pairs.add(tuple(sorted((key, other_key))))  # type: ignore[arg-type]
        return pairs

    def risk_weight(self, true_key: str, pred_key: str) -> float:
        """Cost of predicting `pred_key` when the truth is `true_key`.

        Used to weight the training loss and to produce a risk-weighted error
        rate at evaluation time. The asymmetry is deliberate: calling a
        deadly mushroom edible is catastrophic, while calling an edible one
        deadly merely costs the user a meal.
        """
        if true_key == pred_key:
            return 0.0

        true_sp = self.species.get(true_key)
        pred_sp = self.species.get(pred_key)
        if true_sp is None or pred_sp is None:
            return 1.0

        # The catastrophic direction: it really is deadly, we said it wasn't.
        if true_sp.toxicity is Toxicity.DEADLY and pred_sp.toxicity < Toxicity.TOXIC:
            return 1000.0
        if true_sp.toxicity is Toxicity.DEADLY:
            return 50.0
        if true_sp.toxicity is Toxicity.SERIOUS and pred_sp.toxicity < Toxicity.TOXIC:
            return 100.0
        # The merely annoying direction: safe mushroom called dangerous.
        if pred_sp.toxicity is Toxicity.DEADLY:
            return 2.0
        # Same genus errors are the ordinary cost of fine-grained work.
        if true_sp.genus == pred_sp.genus:
            return 0.5
        return 1.0
