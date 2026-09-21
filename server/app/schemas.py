"""API request and response models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CandidateOut(BaseModel):
    species_key: str
    scientific_name: str
    common_names: list[str]
    confidence: float = Field(description="Calibrated probability, 0-1.")
    toxicity: str = Field(
        description=(
            "Consequence of eating this species: DEADLY, SERIOUS, TOXIC, INEDIBLE. "
            "Never a recommendation. No value means edible."
        )
    )
    genus: str


class QuestionOut(BaseModel):
    key: str
    label: str
    prompt: str
    how: str
    effort: str
    options: list[str]
    requires_photo: bool
    safety_note: str
    rationale: str
    expected_information_gain: float


class IdentifyResponse(BaseModel):
    observation_id: str
    verdict: str = Field(
        description=(
            "species | group | uncertain | dangerous_group | out_of_scope. "
            "Anything other than 'species' means no species was asserted."
        )
    )
    headline: str
    detail: str
    candidates: list[CandidateOut]
    warnings: list[str]
    deadly_in_play: bool
    questions: list[QuestionOut]
    model_version: str
    calibrated: bool


class FieldNoteFieldOut(BaseModel):
    key: str
    label: str
    prompt: str
    how: str
    options: list[str]
    effort: str


class FieldFormOut(BaseModel):
    """The capture form, served rather than hardcoded in the client.

    The answer strings are compared against the character catalogue, so a
    client that invented its own list would submit values the server silently
    ignores. Serving the form makes that impossible.
    """

    fields: list[FieldNoteFieldOut]
    note: str


class AnswerRequest(BaseModel):
    observation_id: str
    character_key: str
    answer: str


class ColourMatchOut(BaseModel):
    option: str
    distance: float = Field(
        description="Perceptual distance (CIEDE2000). Lower is closer."
    )


class SporePrintReadingOut(BaseModel):
    """What the colour match concluded, and whether it may be acted on.

    `confident` is the only field a client should branch on. When it is false
    there is no matched option and the ranking is for ordering the manual
    picker, not for presenting as an answer.
    """

    confident: bool
    option: str | None = Field(
        description=(
            "The matched spore_print_colour answer, or null when no match may "
            "be asserted. Submit it to /answer unchanged."
        )
    )
    reason: str
    ranked: list[ColourMatchOut]
    corrected_rgb: list[int] | None = Field(
        description="The sample after white-balance correction, for display."
    )


class SpeciesOut(BaseModel):
    species_key: str
    scientific_name: str
    common_names: list[str]
    genus: str
    toxicity: str
    notes: str
    lookalikes: list[CandidateOut]
    diagnostic_characters: list[str]


class HealthOut(BaseModel):
    status: str
    model_loaded: bool
    calibrated: bool
    n_classes: int
    model_version: str = Field(
        default="",
        description=(
            "The same string `/identify` stamps on a result. A client holding "
            "stored results needs it to know whether an old confidence is "
            "still comparable to a new one, and asking for that should not "
            "require running an identification."
        ),
    )
    taxonomy_reviewed: bool
    character_states_described: int = Field(
        default=0,
        description=(
            "Species with a character-state table. Answers to diagnostic "
            "questions only re-weight candidates that have one, so a zero "
            "here means field notes are inert by design, not broken."
        ),
    )
