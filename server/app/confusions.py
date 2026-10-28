"""The empirical confusion graph: what *this model* gets dangerously wrong.

`taxonomy.dangerous_pairs()` records what people confuse in the field. It
comes from field guides, the interrogation engine asks about it, the
companion book prints from it, and a mycologist will read it. It is a claim
about mushrooms.

A classifier confuses different things. Measured on the first real run,
2026-10-28: **seven of its eight dangerous confusions were not registered
pairs**, its worst being *Galerina marginata* called *Crepidotus cesatii* at
0.850. Nobody picks a *Crepidotus* thinking it is a funeral bell; a network
looking at a small brown thing on wood does. So the lethal-pair refusal was
blind on almost every mistake the model actually made, and the only thing
protecting a user there was the 2% deadly-mass rule.

The fix is a second graph, not more edges in the first. Writing model
artefacts into `lookalikes` would mend the safety layer by making the
mycology wrong, in the one file that exists to be right about mushrooms.

Three properties this file exists to enforce.

**It belongs to one checkpoint.** A confusion the previous model made is not
evidence about this one. `load` refuses a graph whose `checkpoint` does not
match the model being served, rather than applying it anyway -- the same
reasoning as `ood.py` refusing to invent a threshold.

**It is never a resemblance.** Nothing here reaches a user as "these look
alike", because they do not. What the user sees is the same refusal the
lethal-pair rule always gave: the app will not choose between them.

**Absent is a legitimate state.** No file means no empirical pairs and the
taxonomy's graph alone, which is exactly where the app was before. A missing
graph must never read as a graph with nothing in it.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConfusionPair:
    deadly: str
    mistaken_for: str
    count: int
    max_confidence: float
    max_deadly_mass: float
    also_a_field_lookalike: bool


class ConfusionGraph:
    """Pairs this model confuses, or an empty graph that says it is empty."""

    def __init__(
        self,
        pairs: list[ConfusionPair] | None = None,
        checkpoint: str | None = None,
        generated: str | None = None,
    ):
        self.pairs = list(pairs or [])
        self.checkpoint = checkpoint
        self.generated = generated

    @property
    def loaded(self) -> bool:
        """Whether a graph was actually read.

        Distinguished from `not self.pairs` on purpose: a model with no
        dangerous confusions and a model whose graph was never generated are
        different claims, and `/health` reports them differently.
        """
        return self.checkpoint is not None

    def as_pairs(self) -> frozenset[tuple[str, str]]:
        """Sorted key tuples, the shape `straddles_dangerous_pair` wants."""
        return frozenset(
            tuple(sorted((p.deadly, p.mistaken_for))) for p in self.pairs
        )

    @classmethod
    def load(
        cls, path: str | Path | None, expected_checkpoint: str | None = None
    ) -> "ConfusionGraph":
        if path is None:
            return cls()
        path = Path(path)
        if not path.exists():
            log.info(
                "No confusion graph at %s -- the lethal-pair rule uses the "
                "taxonomy's field lookalikes only. Generate one with "
                "scripts/confusion_graph.py after a run.", path,
            )
            return cls()

        blob = json.loads(path.read_text(encoding="utf-8"))
        checkpoint = blob.get("checkpoint")

        # A graph from another model is worse than none: it would refuse
        # pairs this model does not confuse while missing the ones it does,
        # and it would read in /health as though the protection were live.
        if (expected_checkpoint and checkpoint
                and Path(checkpoint).name != Path(expected_checkpoint).name):
            log.error(
                "Confusion graph at %s was generated from %r but the model "
                "being served is %r. IGNORING it: a confusion the previous "
                "model made is not evidence about this one. Regenerate with "
                "scripts/confusion_graph.py.",
                path, checkpoint, expected_checkpoint,
            )
            return cls()

        pairs = [
            ConfusionPair(
                deadly=p["deadly"],
                mistaken_for=p["mistaken_for"],
                count=int(p.get("count", 0)),
                max_confidence=float(p.get("max_confidence", 0.0)),
                max_deadly_mass=float(p.get("max_deadly_mass", 0.0)),
                also_a_field_lookalike=bool(p.get("also_a_field_lookalike", False)),
            )
            for p in blob.get("pairs", [])
        ]
        novel = sum(1 for p in pairs if not p.also_a_field_lookalike)
        log.info(
            "Confusion graph: %d pairs, %d of them not field lookalikes "
            "(from %s, generated %s)",
            len(pairs), novel, checkpoint, blob.get("generated"),
        )
        return cls(pairs, checkpoint=checkpoint, generated=blob.get("generated"))
