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
from .evidence import entropy, expected_information_gain, reweight
from .taxonomy_service import TaxonomyService, Toxicity


@dataclass
class Question:
    character: Character
    # Bits of entropy this question is expected to remove. This is the real
    # figure, and it is what leaves in the API response.
    expected_information_gain: float
    resolves_dangerous_pair: bool
    rationale: str
    # Internal sort key: the share of the available uncertainty this would
    # resolve, plus a bonus for settling a lethal ambiguity, minus a discount
    # for effort. Kept separate from the gain because they are different
    # quantities, and conflating them once let a question with almost no
    # information ride the safety bonus to the top of the list.
    priority: float = 0.0

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

        Delegates to `evidence.expected_information_gain`, which simulates
        every answer the user could give using the same re-weighting the app
        will really apply. Question selection and answer application are
        therefore one model rather than two that can disagree.

        The earlier version estimated gain from the fact that candidates
        *declared* a character as diagnostic, without knowing which state each
        one showed. That could not distinguish a character the candidates
        differ on from one they happen to share, so it recommended questions
        that could not discriminate at all -- substrate as the top question for
        the funeral bell against the sheathed woodtuft, where both grow on dead
        wood. A character every remaining candidate answers identically now
        scores zero.
        """
        return expected_information_gain(ranked, character_key, self.taxonomy)

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

        available = entropy([score for _, score in ranked])
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

            # Priority is scored on the share of the uncertainty actually
            # present, so the bonus and the effort discount stay comparable
            # whatever the size of the candidate set.
            share = gain / available if available > 0 else 0.0
            # A character that settles a potentially lethal ambiguity is worth
            # asking even when a cheaper question would cut more entropy.
            priority = share + (1.0 if resolves else 0.0)
            # Discount by effort so we don't send someone away for eight hours
            # when looking at the stem base would do.
            priority -= 0.05 * EFFORT_ORDER.get(character.effort, 1)

            scored.append(
                Question(
                    character=character,
                    expected_information_gain=gain,
                    resolves_dangerous_pair=resolves,
                    rationale=self._rationale(ranked, char_key, resolves, dangerous_pair),
                    priority=priority,
                )
            )

        scored.sort(key=lambda q: -q.priority)
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
    ) -> list[tuple[str, float]]:
        """Re-weight candidates given a user's answer.

        The judgement lives in `evidence.reweight`, which compares the answer
        against each species' declared `character_states` and applies a
        deliberately asymmetric likelihood: contradicting a deadly candidate
        moves it far less than contradicting a harmless one, and no answer may
        drive a deadly candidate below the threshold at which the safety layer
        still warns about it.

        A species that declares no states for the character is left untouched,
        because an absence of description on our side is not evidence about
        the mushroom. The table is empty until the field-character review in
        docs/REVIEW.md lands, so today this is a no-op for every answer.

        That is a deliberate change from the previous placeholder, which
        boosted a species when the answer string happened to appear somewhere
        in that species' free-text `notes`. It fired on 34 of 157 possible
        answers, but on grounds unrelated to whether the character was
        diagnostic -- any species whose prose mentioned "White" was promoted
        by a white gill answer. Coincidence presented as evidence is worse
        than no evidence, particularly in a system whose whole claim is that
        it reports uncertainty honestly.
        """
        return reweight(ranked, character_key, answer, self.taxonomy)
