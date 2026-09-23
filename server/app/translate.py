"""Turning a sentence into field notes.

A user types *small brown mushroom, tuft on a rotten stump, ring on the stem,
no smell*. The eight-question form would get the same information out of them
in eight taps, and most people will not make eight taps. This module maps the
sentence onto the character vocabulary the evidence engine already speaks.

## It translates. It does not identify.

Everything it produces goes through the existing `reweight` and the existing
safety layer, unchanged -- the same floors, the same dangerous-pair rule, the
same refusals. The value is that a description reaches the engine at all; the
engine's judgement is untouched.

So the schema this module builds has **no field in which a species could be
named**. Not a discouraged one. There is nowhere to put it. A model asked to
fill in `substrate` and `ring` cannot answer "Galerina marginata", because the
response shape does not admit the string.

## A state that is not an option is impossible, not merely rejected

Each property's `enum` is exactly `CHARACTERS[key].options`, read at request
time. The model cannot emit "brownish" where the catalogue says "Brown",
because a constrained decode will not produce it -- the same guarantee the
worksheet importer enforces by refusing the row, moved one step earlier.

The result is validated again here anyway. `strict` is a promise from the API
and this is a safety path; a promise is not a check.

## Silence is the safe answer

Every property is nullable and the prompt says so twice. The capture screen
already tells users to skip anything they are unsure of, because "a guess
recorded as an observation is worse than a blank" -- the same is true of a
guess made on their behalf, and more so, because they never said it.

## Two backends, and it always says which one ran

`ClaudeTranslator` calls the API. `KeywordTranslator` is a small rule-based
stand-in for a deployment with no key, and for the tests and the demo, which
must run offline. Every response carries `backend`, in the same spirit as
`/health` reporting `model_loaded: false` rather than pretending.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

from .characters import CHARACTERS

MODEL = "claude-opus-5"

# Characters a person might mention in a sentence. `taste` is absent: the
# interrogation engine may ask for one only when no deadly candidate holds
# mass (rule 5), and a free-text box has no such gate. If a user volunteers a
# taste, they have already tasted it, and the form can still take it -- this
# is about what the app extracts unprompted.
TRANSLATABLE = tuple(
    key for key, character in CHARACTERS.items()
    if character.options and key != "taste"
)

SYSTEM = """You map a forager's description of a single mushroom onto a fixed \
catalogue of observations. You are a translator, not an identifier.

Rules, in order of importance:

1. Never identify anything. You have no field in which to name a species, and \
you must not name one in any other field either.
2. Record only what the description actually states. If the text does not \
mention a character, that character is null. A guess recorded as an \
observation is worse than a blank, because the user never said it.
3. Do not infer one character from another. "On a stump" says what it is \
growing on; it says nothing about which trees are nearby. "Brown" describes \
whatever the user said was brown -- do not spread it to the gills.
4. Pick the catalogue option that the description matches. If the description \
is close to two options, choose neither: leave it null.
5. "No smell", "smelled of nothing" and "nothing unusual" are an observation, \
not an absence -- they map to "Nothing much"."""


@dataclass
class Translation:
    """What was understood, and what was not."""

    field_notes: dict[str, str] = field(default_factory=dict)
    backend: str = "none"
    # Phrases the translator could not place. Shown to the user so the gap is
    # theirs to close, rather than silently dropped.
    not_understood: list[str] = field(default_factory=list)
    # Values the model produced that are not catalogue options. Should always
    # be empty when a constrained decode worked; recorded rather than hidden,
    # because a non-empty list means the guarantee did not hold.
    rejected: dict[str, str] = field(default_factory=dict)


def response_schema(keys: tuple[str, ...] = TRANSLATABLE) -> dict:
    """The JSON schema the model answers in.

    Built from the catalogue at call time, so it cannot drift from the options
    the server validates against. Every property is required and nullable:
    required so the model considers each character rather than quietly
    skipping it, nullable so that considering one and finding nothing said
    about it is expressible.
    """
    properties: dict[str, dict] = {}
    for key in keys:
        character = CHARACTERS[key]
        properties[key] = {
            "type": ["string", "null"],
            "enum": [*character.options, None],
            "description": character.label,
        }
    properties["not_understood"] = {
        "type": "array",
        "items": {"type": "string"},
        "description": (
            "Phrases from the description that do not correspond to any "
            "character above. Quote them; do not paraphrase."
        ),
    }
    return {
        "type": "object",
        "properties": properties,
        "required": [*keys, "not_understood"],
        "additionalProperties": False,
    }


def validate(raw: dict) -> Translation:
    """Check the model's answer against the catalogue, again.

    A constrained decode should make this a formality. It is here because the
    output of this function is fed to the safety layer, and a safety path does
    not take a promise in place of a check.
    """
    out = Translation()
    for key, value in raw.items():
        if key == "not_understood":
            out.not_understood = [str(v) for v in (value or []) if str(v).strip()]
            continue
        if value is None or key not in CHARACTERS:
            continue
        if value in CHARACTERS[key].options:
            out.field_notes[key] = value
        else:
            out.rejected[key] = str(value)
    return out


class ClaudeTranslator:
    """The real one."""

    def __init__(self, model: str = MODEL, client=None):
        self.model = model
        self._client = client

    @property
    def client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client

    def translate(self, description: str) -> Translation:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=[
                # The catalogue is identical on every request and the
                # description is not, so the stable half goes first and is
                # cached. Order is tools -> system -> messages; putting the
                # breakpoint here means a user pays for their own sentence.
                {
                    "type": "text",
                    "text": SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            # Extraction, not reasoning.
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": response_schema()},
            },
            messages=[{"role": "user", "content": description}],
        )
        text = next(b.text for b in response.content if b.type == "text")
        result = validate(json.loads(text))
        result.backend = self.model
        return result


# --- The offline stand-in ----------------------------------------------------
#
# Phrase -> (character, option). Deliberately small and deliberately literal:
# it exists so the demo and the tests run without a key, and so a deployment
# without one degrades to something honest rather than to nothing. It is not
# an attempt to do the model's job.

CUES: list[tuple[str, str, str]] = [
    (r"\bon (a |an |the )?(rotten |dead |fallen )*(stump|log|branch|wood)\b",
     "substrate", "Dead wood or a stump"),
    (r"\bon (a )?living tree\b|\bon the trunk\b", "substrate", "A living tree"),
    (r"\bin (the )?grass\b|\bon (a )?lawn\b|\bin (a )?(field|meadow|pasture)\b",
     "substrate", "Grass or lawn"),
    (r"\bon dung\b|\bon (cow|horse) muck\b", "substrate", "Dung"),
    (r"\bin (the )?(leaf )?litter\b|\bon (the )?soil\b|\bon (the )?ground\b",
     "substrate", "Soil or leaf litter"),
    (r"\btuft\w*\b|\bcluster\w*\b|\bclump\w*\b|\bbunch\w*\b|\bin a group\b",
     "growth_form", "In a tight cluster"),
    (r"\bin a ring\b|\bfairy ring\b", "growth_form", "In a ring"),
    (r"\bsingly\b|\bon its own\b|\ba single\b", "growth_form", "Singly"),
    (r"\bbracket\b|\bshelf\b", "growth_form", "As a bracket"),
    (r"\bring on the stem\b|\bhas a ring\b|\bskirt\b", "ring", "Firm skirt-like ring"),
    (r"\bno ring\b|\bwithout a ring\b", "ring", "No ring"),
    (r"\b(bag|sac|cup|volva) (at|around) the (base|bottom)\b|\bsac-?like base\b",
     "volva", "Clear cup or sac"),
    (r"\bcut it off\b|\bcut the (stem|base) off\b", "volva", "I cut it off"),
    (r"\bno smell\b|\bsmell(ed|s)? of nothing\b|\bnothing unusual\b|\bodourless\b",
     "smell", "Nothing much"),
    (r"\bsmell(s|ed|ing)? of aniseed\b|\baniseed\b|\balmond\b", "smell", "Aniseed or almond"),
    (r"\bradish\b", "smell", "Radish"),
    (r"\bapricot\b|\bfruity\b", "smell", "Apricot or fruity"),
    (r"\bearthy\b|\braw potato\b", "smell", "Raw potato or earthy"),
    (r"\bink\b|\bchemical\b|\bbleach\b", "smell", "Ink or chemicals"),
    (r"\bfoul\b|\brotting\b|\bcarrion\b", "smell", "Rotting or foul"),
    (r"\bslimy\b|\bsticky\b|\bgreasy\b", "cap_surface", "Slimy or greasy"),
    (r"\bscaly\b|\bshaggy cap\b", "cap_surface", "Scaly"),
    (r"\bvelvety\b", "cap_surface", "Velvety"),
    (r"\bpores\b|\bspongy underneath\b|\btubes\b", "gill_type", "Pores or tubes"),
    (r"\bspines\b|\bteeth\b", "gill_type", "Spines or teeth"),
    # Anything that says something *about* the gills goes before the bare
    # "gills", which would otherwise claim the word and block it.
    (r"\bfree gills\b|\bgills (don'?t|do not) touch\b",
     "gill_attachment", "Free, not touching the stem"),
    (r"\bgills run(ning)? down\b|\bdecurrent\b",
     "gill_attachment", "Running down the stem"),
    (r"\bwhite gills\b", "gill_colour", "White"),
    (r"\bpink gills\b", "gill_colour", "Pink"),
    (r"\bdark gills\b|\bblack gills\b", "gill_colour", "Chocolate or black"),
    (r"\bgills\b", "gill_type", "Blade-like gills"),
    (r"\bnetted stem\b|\bnet(work)? on the stem\b",
     "stipe_surface", "Netted or with a raised mesh"),
    (r"\btiny\b|\bunder 2 ?cm\b", "size", "Under 2 cm"),
    (r"\bhuge\b|\benormous\b|\bover 20 ?cm\b", "size", "Over 20 cm"),
    (r"\bjelly\b|\bgelatinous\b|\brubbery\b", "texture", "Gelatinous and rubbery"),
    (r"\bunder (oak|oaks)\b|\bwith oak\b", "habitat", "Oak"),
    (r"\bunder (beech|beeches)\b|\bwith beech\b", "habitat", "Beech"),
    (r"\bunder (birch|birches)\b|\bwith birch\b", "habitat", "Birch"),
    (r"\bunder (pine|spruce|conifer)\w*\b|\bwith (pine|spruce)\b",
     "habitat", "Pine or spruce"),
    (r"\bno trees\b|\bopen (ground|field)\b", "habitat", "No trees nearby"),
    # Both orders, because people write it both ways.
    (r"\bwhite spore print\b|\bspore print (was |is |came out )?(white|cream)\b",
     "spore_print_colour", "White or cream"),
    (r"\b(rust|cinnamon)[- ]?(brown)? spore print\b"
     r"|\bspore print (was |is |came out )?(rust|cinnamon)([\s-]*brown)?\b",
     "spore_print_colour", "Rust or cinnamon brown"),
    (r"\bblack spore print\b|\bspore print (was |is |came out )?black\b",
     "spore_print_colour", "Black"),
    (r"\bpink spore print\b|\bspore print (was |is |came out )?pink\b",
     "spore_print_colour", "Pink"),
    (r"\bbruis(es|ed|ing) blue\b|\bturns blue\b", "bruising_reaction", "Blue"),
    (r"\bbruis(es|ed|ing) (red|pink)\b|\bturns red\b", "bruising_reaction", "Red or pink"),
    (r"\bwhite milk\b|\bmilky\b|\bbleeds white\b", "latex_colour", "White"),
    # Bare colour words come LAST, and only claim text no other cue took.
    # "spore print came out rust brown" is about the print, not the cap, and
    # a cap colour lifted out of that sentence is a wrong observation handed
    # to the safety layer -- which is worse than no observation at all.
    (r"\bwhite (cap|mushroom|toadstool)\b|\bcream cap\b", "cap_colour", "White or cream"),
    (r"\bbrown\b", "cap_colour", "Brown"),
    (r"\borange\b", "cap_colour", "Orange"),
    (r"\byellow\b", "cap_colour", "Yellow"),
    (r"\bred\b", "cap_colour", "Red"),
    (r"\bpurple\b|\blilac\b|\bviolet\b", "cap_colour", "Purple"),
    (r"\bgrey\b|\bgray\b", "cap_colour", "Grey"),
    (r"\bgreen\b|\bolive\b", "cap_colour", "Olive or greenish"),
]


class KeywordTranslator:
    """Literal phrase matching, for when there is no key.

    Reports itself as `keywords` so nothing downstream can mistake it for the
    model. It finds much less and invents nothing, which is the right way
    round for a fallback on a safety path.
    """

    name = "keywords"

    def translate(self, description: str) -> Translation:
        text = description.lower()
        notes: dict[str, str] = {}
        matched: list[tuple[int, int]] = []
        def overlaps(span: tuple[int, int]) -> bool:
            return any(span[0] < end and start < span[1] for start, end in matched)

        for pattern, key, state in CUES:
            if key in notes:
                continue  # first cue wins, so "brown cap" beats a later "brown"
            for hit in re.finditer(pattern, text):
                # A word already claimed by a more specific cue is spoken for.
                if overlaps(hit.span()) or state not in CHARACTERS[key].options:
                    continue
                notes[key] = state
                matched.append(hit.span())
                break

        # Whatever is left once the matched spans are blanked out.
        leftover = list(text)
        for start, end in matched:
            leftover[start:end] = " " * (end - start)
        phrases = [
            p.strip() for p in re.split(r"[,.;]| and ", "".join(leftover))
            if len(p.strip()) > 3
        ]
        return Translation(field_notes=notes, backend=self.name,
                           not_understood=phrases)


def default_translator():
    """Claude when there is a key, the keyword matcher when there is not.

    The same shape as the classifier's own fallback: real backend if the
    environment provides one, an honest stand-in otherwise, and the response
    says which.
    """
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return ClaudeTranslator()
    return KeywordTranslator()
