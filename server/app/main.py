"""HTTP API for What's That Mushroom.

Endpoints are deliberately few:

  POST /identify   photograph plus optional field metadata -> assessment
  POST /answer     answer a diagnostic question -> revised assessment
  GET  /species    reference data for one species
  GET  /health     readiness, including whether calibration is loaded

The identify response never contains a bare species name without the
surrounding verdict, warnings and questions. Clients are expected to render
the verdict, not to cherry-pick candidates[0] -- and the response shape makes
that awkward on purpose.
"""

from __future__ import annotations

import io
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, UnidentifiedImageError

from .config import settings
from .inference import Classifier, OnnxBackend
from .interrogation import InterrogationEngine
from .safety import SafetyLayer
from .schemas import (
    AnswerRequest,
    CandidateOut,
    HealthOut,
    IdentifyResponse,
    QuestionOut,
    SpeciesOut,
)
from .taxonomy_service import TaxonomyService

log = logging.getLogger(__name__)

state: dict = {}

# In-memory store, sufficient for a single-process deployment and for the
# follow-up question flow. Swap for Redis or Postgres before scaling out.
observations: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    taxonomy = TaxonomyService.load(settings.taxonomy_path)

    labels_path = settings.labels_path
    if not labels_path.exists():
        # Fall back to the taxonomy's own key list so the service runs before
        # a model has been trained.
        log.warning("No labels at %s -- deriving the label space from the taxonomy.",
                    labels_path)
        import json
        import tempfile

        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump({"classes": sorted(taxonomy.species)}, tmp)
        tmp.close()
        labels_path = type(labels_path)(tmp.name)

    classifier = Classifier.load(
        settings.model_path,
        labels_path,
        settings.calibration_path,
        settings.image_size,
    )

    threshold = settings.confidence_threshold
    calibrated = settings.calibration_path.exists()
    safety = (
        SafetyLayer.from_calibration(taxonomy, settings.calibration_path)
        if calibrated
        else SafetyLayer(taxonomy, confidence_threshold=threshold)
    )

    state.update(
        taxonomy=taxonomy,
        classifier=classifier,
        safety=safety,
        engine=InterrogationEngine(taxonomy),
        calibrated=calibrated,
    )
    log.info("Ready: %d classes, calibrated=%s", len(classifier.classes), calibrated)
    yield
    state.clear()


app = FastAPI(
    title="What's That Mushroom",
    version="0.1.0",
    description=(
        "Fungi identification that reports honest uncertainty. This API never "
        "asserts that a mushroom is safe to eat, and refuses to name a species "
        "when a potentially lethal lookalike cannot be ruled out."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _candidates_out(candidates) -> list[CandidateOut]:
    return [CandidateOut(**c.__dict__) for c in candidates]


def _build_response(observation_id: str, ranked, answered: set[str]) -> IdentifyResponse:
    assessment = state["safety"].assess(ranked)
    questions = state["engine"].next_questions(ranked, already_answered=answered, limit=3)

    return IdentifyResponse(
        observation_id=observation_id,
        verdict=assessment.verdict.value,
        headline=assessment.headline,
        detail=assessment.detail,
        candidates=_candidates_out(assessment.candidates),
        warnings=assessment.warnings,
        deadly_in_play=assessment.deadly_in_play,
        questions=[QuestionOut(**q.to_dict()) for q in questions],
        model_version=app.version,
        calibrated=state["calibrated"],
    )


@app.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    if not state:
        raise HTTPException(503, "Service is still starting.")
    import json

    reviewed = bool(
        json.loads(settings.taxonomy_path.read_text(encoding="utf-8")).get("reviewed_by")
    )
    return HealthOut(
        status="ok",
        model_loaded=isinstance(state["classifier"].backend, OnnxBackend),
        calibrated=state["calibrated"],
        n_classes=len(state["classifier"].classes),
        taxonomy_reviewed=reviewed,
    )


@app.post("/identify", response_model=IdentifyResponse)
async def identify(
    image: UploadFile = File(..., description="Photograph of the mushroom."),
    month: int | None = Form(None, ge=1, le=12),
    latitude: float | None = Form(None, ge=-90, le=90),
    longitude: float | None = Form(None, ge=-180, le=180),
) -> IdentifyResponse:
    if not state:
        raise HTTPException(503, "Service is still starting.")

    payload = await image.read()
    if len(payload) > settings.max_upload_bytes:
        raise HTTPException(413, "Image is too large.")
    if not payload:
        raise HTTPException(400, "Empty upload.")

    try:
        picture = Image.open(io.BytesIO(payload))
        picture.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(400, "That file could not be read as an image.")

    ranked = state["classifier"].predict(picture, month, latitude, longitude)

    observation_id = uuid.uuid4().hex
    observations[observation_id] = {"ranked": ranked, "answered": set()}

    return _build_response(observation_id, ranked, set())


@app.post("/answer", response_model=IdentifyResponse)
def answer(request: AnswerRequest) -> IdentifyResponse:
    """Apply a user's answer to a diagnostic question and reassess.

    The revised assessment goes back through the full safety layer. An answer
    can never unlock a species-level verdict that the safety rules would
    otherwise withhold.
    """
    if not state:
        raise HTTPException(503, "Service is still starting.")

    record = observations.get(request.observation_id)
    if record is None:
        raise HTTPException(404, "Unknown observation. Start again with /identify.")

    ranked = state["engine"].apply_answer(
        record["ranked"], request.character_key, request.answer
    )
    record["ranked"] = ranked
    record["answered"].add(request.character_key)

    return _build_response(request.observation_id, ranked, record["answered"])


@app.get("/species/{species_key}", response_model=SpeciesOut)
def species(species_key: str) -> SpeciesOut:
    if not state:
        raise HTTPException(503, "Service is still starting.")

    taxonomy: TaxonomyService = state["taxonomy"]
    entry = taxonomy.get(species_key)
    if entry is None:
        raise HTTPException(404, "Unknown species.")

    lookalikes = [
        CandidateOut(
            species_key=la.key,
            scientific_name=la.scientific_name,
            common_names=list(la.common_names),
            confidence=0.0,
            toxicity=la.toxicity.name,
            genus=la.genus,
        )
        for la in taxonomy.lookalikes_of(species_key)
    ]

    return SpeciesOut(
        species_key=entry.key,
        scientific_name=entry.scientific_name,
        common_names=list(entry.common_names),
        genus=entry.genus,
        toxicity=entry.toxicity.name,
        notes=entry.notes,
        lookalikes=lookalikes,
        diagnostic_characters=list(entry.diagnostic_characters),
    )
