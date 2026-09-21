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
            "Recorded harm from eating this species: DEADLY, SERIOUS, TOXIC, "
            "NONE_RECORDED or UNASSESSED. Never a recommendation. NONE_RECORDED "
            "means no toxicity is recorded and asserts nothing about edibility."
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
    taxonomy_reviewed: bool
    character_states_described: int = Field(
        default=0,
        description=(
            "Species with a character-state table. Answers to diagnostic "
            "questions only re-weight candidates that have one, so a zero "
            "here means field notes are inert by design, not broken."
        ),
    )
