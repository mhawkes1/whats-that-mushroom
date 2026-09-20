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
