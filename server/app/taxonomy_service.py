"""Serving-side taxonomy access.

Re-exports the training-time taxonomy model and adds the query methods the
safety layer and interrogation engine need. Kept as a thin layer over the
same JSON the model was trained against, so the label space and the safety
rules can never drift apart.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ML_ROOT = Path(__file__).resolve().parents[2] / "ml"
if str(_ML_ROOT) not in sys.path:
    sys.path.insert(0, str(_ML_ROOT))

from fungi_ml.taxonomy import Species, Taxonomy, Toxicity  # noqa: E402

__all__ = ["Species", "Toxicity", "TaxonomyService"]


class TaxonomyService(Taxonomy):
    """Taxonomy plus the lookups the serving path needs."""

    @classmethod
    def load(cls, path: str | Path) -> "TaxonomyService":
        base = Taxonomy.load(path)
        return cls(species=base.species)

    # Both of these are derived from the full species map and are hit on
    # every request, so they are computed once and memoised on the instance.
    # A plain lru_cache will not do: Taxonomy is an unhashable dataclass.
    _dangerous_genera: frozenset[str] | None = None
    _dangerous_pairs: frozenset[tuple[str, str]] | None = None

    def dangerous_genera(self) -> frozenset[str]:
        """Genera containing at least one species that can kill."""
        if self._dangerous_genera is None:
            self._dangerous_genera = frozenset(
                self.species[k].genus for k in self.deadly_keys()
            )
        return self._dangerous_genera

    def dangerous_pairs(self) -> frozenset[tuple[str, str]]:  # type: ignore[override]
        if self._dangerous_pairs is None:
            self._dangerous_pairs = frozenset(super().dangerous_pairs())
        return self._dangerous_pairs

    @staticmethod
    def _states_differ(sp_a: Species, sp_b: Species, character: str) -> bool:
        """Could any answer about this character tell these two species apart?

        Only when both are described for it and the state sets are not
        identical. If one is undescribed we cannot say, and if both show the
        same states then no answer separates them however diagnostic the
        character is for each of them individually.
        """
        states_a = set(sp_a.character_states.get(character, ()))
        states_b = set(sp_b.character_states.get(character, ()))
        if not states_a or not states_b:
            return False
        return states_a != states_b

    def separating_characters(self, a: str, b: str) -> list[str]:
        """Characters that distinguish two specific species.

        Both species declaring a character is not enough: the funeral bell and
        the sheathed woodtuft both declare substrate, and both grow on dead
        wood, so asking about it tells a user nothing while sounding like the
        decisive check. Characters whose recorded states actually differ come
        first; characters both declare but which are not known to differ come
        after, since they may still separate the two in ways the table does
        not capture yet.
        """
        sp_a, sp_b = self.get(a), self.get(b)
        if sp_a is None or sp_b is None:
            return []

        shared = [c for c in sp_a.diagnostic_characters if c in sp_b.diagnostic_characters]
        discriminating, unknown = [], []
        for character in shared:
            states_a = set(sp_a.character_states.get(character, ()))
            states_b = set(sp_b.character_states.get(character, ()))
            if states_a and states_b:
                # Both described. Only a difference can separate them; if the
                # states match, no answer distinguishes the two and offering
                # the character would send the user to check nothing.
                if states_a != states_b:
                    discriminating.append(character)
            else:
                unknown.append(character)
        if discriminating or unknown:
            return discriminating + unknown
        # Fall back to the union, preserving the deadly species' ordering so
        # the most safety-relevant check is requested first.
        deadly_first = sp_a if sp_a.toxicity is Toxicity.DEADLY else sp_b
        other = sp_b if deadly_first is sp_a else sp_a
        seen: list[str] = []
        for c in list(deadly_first.diagnostic_characters) + list(other.diagnostic_characters):
            if c not in seen:
                seen.append(c)
        return seen[:5]

    def confirming_characters(self, key: str) -> list[str]:
        """Characters a user should check to confirm a proposed species."""
        sp = self.get(key)
        return list(sp.diagnostic_characters)[:4] if sp else []

    def genus_discriminators(self, genus: str) -> list[str]:
        """Characters that separate species within a genus."""
        members = [s for s in self.species.values() if s.genus == genus]
        counts: dict[str, int] = {}
        for sp in members:
            for c in sp.diagnostic_characters:
                counts[c] = counts.get(c, 0) + 1
        return [c for c, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:4]]

    def lookalikes_of(self, key: str) -> list[Species]:
        sp = self.get(key)
        if sp is None:
            return []
        return [self.species[k] for k in sp.lookalikes if k in self.species]
