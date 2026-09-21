"""Deciding whether the photograph is something we know at all.

A user points the camera at a slug, a pine cone, or an *Amanita* that is not
in the sixty species this model was trained on. The honest answer is "that
isn't something I recognise". The dangerous answer is a confident species
name, and a softmax head will happily supply one, because softmax always sums
to one no matter how little the network actually recognised.

That is the flaw in the check this replaces. It read the top *probability*
and called anything under 0.20 out of scope. But probability is a share of a
fixed total: it says which class won, never whether anything won by
recognising something. Networks are routinely and confidently wrong on inputs
unlike their training data, and an over-confident 0.9 on a photograph of a
slug sails through a top-1 threshold untouched.

## Free energy

The magnitude the softmax throws away is exactly the signal worth keeping.
The free energy of a logit vector (Liu et al., 2020) is

    E(x) = -T * logsumexp(logits / T)

which is low when some class is strongly activated and high when nothing is.
Crucially it is *not* invariant to shifting all the logits down, which is what
happens when the network sees something it has no features for. Two inputs can
produce the same softmax and very different energies; the one with the higher
energy is the one the network did not recognise.

## Which way to err

Flagging a known species as unrecognised costs the user an answer. Failing to
flag something genuinely outside the label space lets the app put a species
name to a mushroom it has never seen -- and the species most likely to be
missing from a sixty-species label space are the uncommon ones, which is not a
category that excludes the lethal. So the threshold is fitted to accept a
deliberate rate of false "I don't know", and the fitting function takes that
rate rather than a rate of missed detections.

## Before it is fitted

`threshold` is None until `ml/fungi_ml/calibrate.py` has fitted one on
held-out data, and an unfitted detector reports that rather than guessing.
Serving an energy threshold invented from nothing would be the same mistake as
serving uncalibrated confidence as confidence, which `CLAUDE.md` rule 4
forbids. Until then the caller falls back to the old top-1 rule, which is weak
but at least is not pretending.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


# The temperature in the energy expression. 1.0 keeps E(x) exactly
# -logsumexp(logits); the parameter exists because the literature tunes it and
# a future fit may want to.
DEFAULT_ENERGY_TEMPERATURE = 1.0

# The share of genuine, in-distribution photographs we are willing to have
# wrongly flagged as unrecognised when fitting the threshold. Five percent is
# a deliberate cost: see "Which way to err" above.
DEFAULT_FALSE_UNKNOWN_RATE = 0.05


def free_energy(
    logits: list[float], temperature: float = DEFAULT_ENERGY_TEMPERATURE
) -> float:
    """Free energy of a logit vector. Higher means less recognised.

    Computed with the max subtracted out, as softmax is, so that a confident
    logit vector does not overflow the exponential.
    """
    if not logits:
        raise ValueError("free_energy needs at least one logit")
    if temperature <= 0:
        raise ValueError("temperature must be positive")

    scaled = [value / temperature for value in logits]
    peak = max(scaled)
    total = sum(math.exp(value - peak) for value in scaled)
    return -temperature * (peak + math.log(total))


def combine_views(energies: list[float]) -> float:
    """One energy for a set of views of the same mushroom.

    The mean, not the minimum. Taking the minimum would let a single
    well-framed view vouch for a set that is otherwise unrecognisable, and the
    photographs that most need flagging are exactly the ones where only one
    frame looks like a mushroom at all.
    """
    if not energies:
        raise ValueError("combine_views needs at least one energy")
    return sum(energies) / len(energies)


@dataclass(frozen=True)
class OodVerdict:
    """Whether the photograph looks like something in the label space."""

    out_of_distribution: bool
    energy: float
    threshold: float | None
    # False when no threshold has been fitted, in which case
    # `out_of_distribution` carries no information and the caller must fall
    # back to something else rather than trusting it.
    fitted: bool

    @property
    def margin(self) -> float | None:
        """How far past the threshold this sits. Positive means unrecognised."""
        return None if self.threshold is None else self.energy - self.threshold


@dataclass(frozen=True)
class OodDetector:
    """An energy threshold, or an honest absence of one."""

    threshold: float | None = None
    temperature: float = DEFAULT_ENERGY_TEMPERATURE

    @property
    def fitted(self) -> bool:
        return self.threshold is not None

    def score(self, logits: list[float]) -> float:
        return free_energy(logits, self.temperature)

    def assess(self, energy: float) -> OodVerdict:
        """Judge an already-computed energy."""
        if self.threshold is None:
            return OodVerdict(
                out_of_distribution=False,
                energy=energy,
                threshold=None,
                fitted=False,
            )
        return OodVerdict(
            out_of_distribution=energy > self.threshold,
            energy=energy,
            threshold=self.threshold,
            fitted=True,
        )

    def assess_logits(self, logits: list[float]) -> OodVerdict:
        return self.assess(self.score(logits))

    @classmethod
    def from_calibration(cls, blob: dict) -> "OodDetector":
        """Read the fitted threshold out of a calibration file.

        A calibration written before energy fitting existed simply has no
        `energy_threshold`, and yields an unfitted detector rather than an
        error -- old checkpoints stay servable, they just do not get the
        better check.
        """
        threshold = blob.get("energy_threshold")
        return cls(
            threshold=None if threshold is None else float(threshold),
            temperature=float(
                blob.get("energy_temperature", DEFAULT_ENERGY_TEMPERATURE)
            ),
        )


def fit_energy_threshold(
    energies: list[float],
    false_unknown_rate: float = DEFAULT_FALSE_UNKNOWN_RATE,
) -> float:
    """Pick the threshold from in-distribution energies alone.

    Set at the quantile above which `false_unknown_rate` of genuine
    photographs fall, so the rate of wrongly disowning a species we do know is
    a number someone chose rather than a number that happened.

    Fitting from in-distribution data only is deliberate. The alternative --
    collecting negatives and fitting to separate them -- fixes the threshold
    against whatever negatives were gathered, and the out-of-distribution
    inputs that matter here are the ones nobody thought to collect.
    """
    if not energies:
        raise ValueError("fit_energy_threshold needs energies to fit on")
    if not 0.0 < false_unknown_rate < 1.0:
        raise ValueError("false_unknown_rate must be between 0 and 1")

    ordered = sorted(energies)
    # The index of the value that leaves `false_unknown_rate` of the sample
    # above it. Clamped so tiny samples still produce a usable threshold.
    position = (1.0 - false_unknown_rate) * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight
