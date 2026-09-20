"""The interrogation engine.

Given a candidate set, decide what to ask the user next.

This is the core product difference. Existing apps map a photograph to an
answer and stop. A mycologist instead identifies the character that best
separates the remaining possibilities and goes and looks at it. That loop is
what this module implements.

Question selection is by expected information gain. For each character we
can ask about, we estimate how much the candidate distribution's entropy
would fall once the answer is known, then weight that by how expensive the
observation is and by whether it resolves a safety-critical ambiguity.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .characters import CHARACTERS, Character, EFFORT_ORDER
from .taxonomy_service import TaxonomyService, Toxicity


@dataclass
class Question:
    character: Character
    expected_information_gain: float
    resolves_dangerous_pair: bool
    rationale: str

    def to_dict(self) -> dict:
        return {
            "key": self.character.key,
            "label": self.character.label,
            "prompt": self.character.prompt,
            "how": self.character.how,
            "effort": self.character.effort,
            "options": list(self.character.options),
            "requires_photo": self.character.requires_photo,
            "safety_note": self.character.safety_note if self.resolves_dangerous_pair else "",
            "rationale": self.rationale,
            "expected_information_gain": round(self.expected_information_gain, 4),
        }


def entropy(distribution: list[float]) -> float:
    total = sum(distribution)
    if total <= 0:
        return 0.0
    return -sum(
        (p / total) * math.log2(p / total) for p in distribution if p > 0
    )


class InterrogationEngine:
    """Chooses the next most useful observation to request."""

    # An answer is only worth asking for if it can actually split the field.
    MIN_GAIN = 0.05

    # Characters that must never be requested while a species capable of
    # killing remains a live candidate. Asking a user to taste a mushroom
    # that might be a death cap implies a taste test could detect it.
    # Amatoxins are tasteless, odourless, and not destroyed by cooking.
    SUPPRESSED_WHEN_DEADLY = frozenset({"taste"})

    def __init__(self, taxonomy: TaxonomyService):
        self.taxonomy = taxonomy

    def _split_candidates(
        self, ranked: list[tuple[str, float]], character_key: str
    ) -> tuple[list[float], list[float]]:
        """Separate candidates into those this character is diagnostic for,
        and those it says nothing about."""
        declares: list[float] = []
        silent: list[float] = []
        for key, score in ranked:
            sp = self.taxonomy.get(key)
            if sp is None:
                silent.append(score)
            elif character_key in sp.diagnostic_characters:
                declares.append(score)
            else:
                silent.append(score)
        return declares, silent

    def expected_gain(
        self, ranked: list[tuple[str, float]], character_key: str
    ) -> float:
        """Expected reduction in entropy from learning this character.

        We lack a per-species character-state table, so this is a model
        rather than an exact computation. The key insight -- and the thing an
        earlier version got backwards -- is that a character several
        candidates *share* as diagnostic is highly informative, not
        uninformative. A field guide's key works precisely by asking about
        characters that all the remaining candidates possess but in
        *different states*: mild versus acrid taste, white versus rust spores.

        So we assume the declaring candidates separate into distinct states,
        limited by how many answer options the question actually offers, and
        that candidates the character says nothing about stay mixed.
        """
        total = sum(score for _, score in ranked)
        if total <= 0:
            return 0.0

        before = entropy([score for _, score in ranked])
        declares, silent = self._split_candidates(ranked, character_key)

        if len(declares) < 1:
            return 0.0

        declaring_mass = sum(declares)
        silent_mass = sum(silent)

        character = CHARACTERS.get(character_key)
        n_options = len(character.options) if character and character.options else 2
        if character and character.requires_photo and not character.options:
            n_options = 4  # a photograph carries several bits in practice

        residual = self._residual_entropy(declares, n_options)
        after = (
            (declaring_mass / total) * residual
            + (silent_mass / total) * entropy(silent)
        )
        return max(0.0, before - after)

    @staticmethod
    def _residual_entropy(group: list[float], n_options: int) -> float:
        """Entropy left among candidates after they answer a question with
        `n_options` distinct states.

        If there are at least as many states as candidates, they separate
        completely and nothing is left. Otherwise they collapse into
        `n_options` buckets, and the residual is the entropy of a group that
        size.
        """
        n = len(group)
        if n <= 1 or n_options >= n:
            return 0.0
        # Candidates share buckets: roughly n/n_options per bucket.
        per_bucket = n / n_options
        return math.log2(per_bucket)

    def _candidate_characters(self, ranked: list[tuple[str, float]], top_n: int) -> set[str]:
        keys: set[str] = set()
        for key, _ in ranked[:top_n]:
            sp = self.taxonomy.get(key)
            if sp:
                keys.update(sp.diagnostic_characters)
        return {k for k in keys if k in CHARACTERS}

    def next_questions(
        self,
        ranked: list[tuple[str, float]],
        already_answered: set[str] | None = None,
        limit: int = 3,
        top_n: int = 6,
    ) -> list[Question]:
        """Rank the questions worth asking, best first."""
        answered = already_answered or set()
        ranked = [(k, s) for k, s in ranked if s > 0][:top_n]
        if len(ranked) < 2:
            return []

        dangerous_pair = self._leading_dangerous_pair(ranked)
        safety_characters: set[str] = set()
        if dangerous_pair:
            safety_characters = set(
                self.taxonomy.separating_characters(*dangerous_pair)
            )

        # Any deadly species with real probability mass suppresses the
        # characters that require putting the mushroom near your mouth.
        deadly_keys = self.taxonomy.deadly_keys()
        deadly_in_play = any(k in deadly_keys and s > 0.01 for k, s in ranked)

        scored: list[Question] = []
        for char_key in self._candidate_characters(ranked, top_n):
            if char_key in answered:
                continue
            if deadly_in_play and char_key in self.SUPPRESSED_WHEN_DEADLY:
                continue
            character = CHARACTERS[char_key]
            gain = self.expected_gain(ranked, char_key)
            resolves = char_key in safety_characters

            if gain < self.MIN_GAIN and not resolves:
                continue

            # A character that settles a potentially lethal ambiguity is worth
            # asking even when a cheaper question would cut more entropy.
            priority = gain + (2.0 if resolves else 0.0)
            # Discount by effort so we don't send someone away for eight hours
            # when looking at the stem base would do.
            priority -= 0.15 * EFFORT_ORDER.get(character.effort, 1)

            scored.append(
                Question(
                    character=character,
                    expected_information_gain=priority,
                    resolves_dangerous_pair=resolves,
                    rationale=self._rationale(ranked, char_key, resolves, dangerous_pair),
                )
            )

        scored.sort(key=lambda q: -q.expected_information_gain)
        return scored[:limit]

    def _leading_dangerous_pair(
        self, ranked: list[tuple[str, float]]
    ) -> tuple[str, str] | None:
        pairs = self.taxonomy.dangerous_pairs()
        keys = [k for k, _ in ranked]
        for i, a in enumerate(keys):
            for b in keys[i + 1 :]:
                if tuple(sorted((a, b))) in pairs:
                    return (a, b)
        return None

    def _rationale(
        self,
        ranked: list[tuple[str, float]],
        character_key: str,
        resolves: bool,
        pair: tuple[str, str] | None,
    ) -> str:
        """Plain-language reason, shown to the user.

        Telling someone *why* a question is being asked is what turns the app
        from an oracle into something that teaches. It is also the reason a
        knowledgeable forager would trust it.
        """
        if resolves and pair:
            a, b = pair
            deadly = a if self.taxonomy[a].toxicity is Toxicity.DEADLY else b
            other = b if deadly == a else a
            return (
                f"This separates {self.taxonomy[deadly].scientific_name}, which can "
                f"kill, from {self.taxonomy[other].scientific_name}."
            )

        affected = [
            self.taxonomy[k].scientific_name
            for k, _ in ranked[:4]
            if character_key in (self.taxonomy[k].diagnostic_characters if k in self.taxonomy else ())
        ]
        if len(affected) >= 2:
            return f"This is what separates {affected[0]} from {affected[1]}."
        if affected:
            return f"This would help confirm or rule out {affected[0]}."
        return "This narrows the remaining possibilities."

    def apply_answer(
        self,
        ranked: list[tuple[str, float]],
        character_key: str,
        answer: str,
        strength: float = 0.6,
    ) -> list[tuple[str, float]]:
        """Re-weight candidates given a user's answer.

        The v1 rule is intentionally conservative. Without a curated
        character-state table per species, we cannot say which species a
        given answer rules *out*. What we can do is boost species for which
        this character is diagnostic and which the answer is consistent with,
        and let the interrogation continue.

        `strength` is deliberately well below 1.0: a user peering at gills in
        poor light is a noisy sensor, and treating their answer as certain
        would be exactly the overconfidence this project exists to avoid.

        TODO: replace with a per-species character-state matrix once the
        taxonomy is reviewed by a mycologist. See docs/ROADMAP.md.
        """
        answer_norm = answer.strip().lower()
        out: list[tuple[str, float]] = []

        for key, score in ranked:
            sp = self.taxonomy.get(key)
            if sp is None:
                out.append((key, score))
                continue

            multiplier = 1.0
            if character_key in sp.diagnostic_characters:
                # Mention of the answer in the species notes is weak positive
                # evidence; absence is not treated as evidence at all.
                if answer_norm and answer_norm in sp.notes.lower():
                    multiplier = 1.0 + strength
            out.append((key, score * multiplier))

        total = sum(s for _, s in out)
        if total <= 0:
            return ranked
        return sorted([(k, s / total) for k, s in out], key=lambda kv: -kv[1])
