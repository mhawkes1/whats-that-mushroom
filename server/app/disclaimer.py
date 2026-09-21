"""The disclaimer a user acknowledges before first use.

Served rather than hardcoded in the client, for the reason `/field-form` is
served: a second copy drifts, and a drifted copy of this one means a user has
acknowledged a text that is no longer what the app does.

## The version is the text

`version` is a hash of the rendered content. It cannot be forgotten on the way
past, and a change to a single word produces a different version, which makes
the stored consent stale and asks again. An acknowledgement of an older
statement is not an acknowledgement of a newer one.

## The statements depend on what is true today

Three of the acknowledgements are conditional on the service's own state:
whether a model is loaded, whether calibration has been fitted, and whether
the taxonomy has been reviewed. Those are the facts `/health` reports, and
while any of them is false the user is told so before they are shown a single
identification -- not in a settings screen they will never open.

When one of them becomes true the statement disappears, the version changes,
and consent is sought again. That is the intended behaviour: the terms a user
agreed to genuinely changed.

## Each claim is acknowledged on its own

One "I agree" covering everything is a formality that trains people to tap
past safety text. Each of these is a separate statement, phrased as something
the user asserts about their own understanding, and each is refused until it
is ticked. There is no "accept all".
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class Acknowledgement:
    key: str
    statement: str
    # Why this one is here, shown beneath it. Never a reassurance.
    because: str


@dataclass(frozen=True)
class Disclaimer:
    version: str
    heading: str
    body: str
    acknowledgements: tuple[Acknowledgement, ...]


HEADING = "Before you use this"

BODY = (
    "This app exists because the other ones answer every question. It will "
    "often tell you that it cannot identify what you have photographed, and "
    "that is the app working, not failing.\n\n"
    "It will never tell you that a mushroom is safe to eat. No app can. "
    "People are killed every year by mushrooms that were identified "
    "confidently and wrongly, and the species responsible have ordinary "
    "lookalikes that experienced foragers collect on purpose."
)

# Always true, whatever the service's state.
CONSTANT: tuple[Acknowledgement, ...] = (
    Acknowledgement(
        key="never_asserts_edibility",
        statement="I understand this app will never tell me a mushroom is safe to eat.",
        because=(
            "There is no such category in it. The strongest thing it says about "
            "any species is that the risk has not been assessed."
        ),
    ),
    Acknowledgement(
        key="photograph_cannot_rule_out",
        statement="I understand a photograph cannot rule out a deadly lookalike.",
        because=(
            # Not "from the safe ones". There is no safe category in this app,
            # and a sentence implying one is the thing rule 1 forbids -- a
            # test caught this phrasing.
            "The features that separate the dangerous species from their "
            "ordinary lookalikes are usually underground, underneath, or only "
            "visible hours later in a spore print."
        ),
    ),
    Acknowledgement(
        key="not_a_substitute",
        statement=(
            "I will not eat a wild mushroom on the strength of what this app tells me."
        ),
        because=(
            "An identification here is a starting point for a person who "
            "already knows what they are doing, and nothing more than that."
        ),
    ),
)


def build(
    *, model_loaded: bool, calibrated: bool, taxonomy_reviewed: bool
) -> Disclaimer:
    """The disclaimer as it stands, given what the service currently is."""
    conditional: list[Acknowledgement] = []

    if not model_loaded:
        conditional.append(
            Acknowledgement(
                key="no_trained_model",
                statement=(
                    "I understand this build has no trained model, and the "
                    "identifications it produces are placeholders."
                ),
                because=(
                    "The classifier has not been trained yet. Results come from "
                    "a stub that produces consistent but meaningless answers, "
                    "so that everything around it can be built and tested."
                ),
            )
        )
    if not calibrated:
        conditional.append(
            Acknowledgement(
                key="uncalibrated",
                statement=(
                    "I understand the percentages shown are not probabilities."
                ),
                because=(
                    "Calibration has not been fitted. Until it is, a number is "
                    "an ordering between candidates and nothing more -- 80% "
                    "does not mean eight times in ten."
                ),
            )
        )
    if not taxonomy_reviewed:
        conditional.append(
            Acknowledgement(
                key="taxonomy_unreviewed",
                statement=(
                    "I understand the reference data has not been checked by a mycologist."
                ),
                because=(
                    "Which species are dangerous, which are confused with which, "
                    "and what separates them are compiled from standard "
                    "references and have not been reviewed by a qualified "
                    "person. Errors in that data become errors in every answer."
                ),
            )
        )

    acknowledgements = (*CONSTANT, *conditional)
    return Disclaimer(
        version=_version(HEADING, BODY, acknowledgements),
        heading=HEADING,
        body=BODY,
        acknowledgements=acknowledgements,
    )


def _version(heading: str, body: str, acks: tuple[Acknowledgement, ...]) -> str:
    """A hash of everything shown, so the version cannot drift from the text."""
    material = "\x00".join(
        [heading, body, *[f"{a.key}\x01{a.statement}\x01{a.because}" for a in acks]]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
