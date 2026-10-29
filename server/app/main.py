"""HTTP API for Funga.

Endpoints are deliberately few:

  POST /identify    photographs plus optional field notes -> assessment
  POST /answer      answer a diagnostic question -> revised assessment
  POST /spore-print/match  a photographed spore print -> which chart colour
  GET  /field-form  the characters to offer on the capture form
  GET  /species     reference data for one species
  GET  /disclaimer  what a user acknowledges before first use
  POST /incident    a suspected misidentification
  GET  /health      readiness, including whether calibration is loaded

The identify response never contains a bare species name without the
surrounding verdict, warnings and questions. Clients are expected to render
the verdict, not to cherry-pick candidates[0] -- and the response shape makes
that awkward on purpose.
"""

from __future__ import annotations

import io
import logging
import uuid
from dataclasses import asdict
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, UnidentifiedImageError

from .config import settings
from .disclaimer import build as build_disclaimer
from .incidents import EMERGENCY_GUIDANCE, IncidentStore, build_report
from .inference import Classifier, OnnxBackend
from .ratelimit import RateLimiter, client_key
from .interrogation import InterrogationEngine
from .confusions import ConfusionGraph
from .safety import SafetyLayer
from .spore_print import read_from_photograph
from .characters import CHARACTERS, field_note_characters
from .evidence import described_coverage
from .schemas import (
    AcknowledgementOut,
    AnswerRequest,
    ColourMatchOut,
    CandidateOut,
    DisclaimerOut,
    FieldFormOut,
    FieldNoteFieldOut,
    HealthOut,
    IdentifyResponse,
    IncidentOut,
    IncidentRequest,
    IncidentStatusOut,
    QuestionOut,
    SpeciesListEntryOut,
    SpeciesListOut,
    SpeciesOut,
    SporePrintReadingOut,
)
from .taxonomy_service import TaxonomyService

log = logging.getLogger(__name__)

state: dict = {}

# In-memory store, sufficient for a single-process deployment and for the
# follow-up question flow. Swap for Redis or Postgres before scaling out.
observations: dict[str, dict] = {}

# Rate limiting for the one unauthenticated write route. Same single-process
# caveat as `observations`; `ratelimit.py` says what that costs.
incident_limiter = RateLimiter(
    limit=settings.incident_rate_limit,
    window_seconds=settings.incident_rate_window_seconds,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    taxonomy = TaxonomyService.load(settings.taxonomy_path)

    labels_path = settings.labels_path
    if not labels_path.exists():
        # Deriving the label space is safe for the stub, whose names are
        # meaningless by construction, and is NEVER safe for a trained
        # model. The checkpoint's class order is `sorted(species present in
        # the dataset)`; the taxonomy's is `sorted(all 244)`. Those coincide
        # only while every species survived the image-count filter, and the
        # moment one does not, every class after it is named as its
        # neighbour -- silently, with confident-looking output, and with a
        # DEADLY species potentially served under a harmless name.
        if settings.model_path.exists():
            raise RuntimeError(
                f"A model is present at {settings.model_path} but there is no "
                f"labels.json at {labels_path}. Refusing to derive the label "
                f"order from the taxonomy: it is only the checkpoint's order "
                f"while no species was filtered out of the dataset, and when "
                f"it is not, every prediction after the first gap is given "
                f"its neighbour's name. Copy the labels.json written beside "
                f"the checkpoint."
            )
        # Before a model exists, the stub needs some label space to range
        # over and the taxonomy's own key list is the honest choice.
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
    # A temperature fitted for a model we are not serving calibrates
    # nothing. Before run four's calibration.json was committed, the file
    # only ever existed beside the model it belonged to, so its presence
    # stood in for both -- and a fresh clone then reported
    # `calibrated: true` while the stub served deterministic fakes. That is
    # rule 4 broken by the health endpoint itself, in the direction that
    # dresses a meaningless number up as a measured one.
    calibrated = settings.calibration_path.exists() and settings.model_path.exists()
    # Bound to the model being served: a confusion the previous checkpoint
    # made is not evidence about this one, and a stale graph would refuse
    # pairs this model does not confuse while missing the ones it does.
    confusions = ConfusionGraph.load(
        settings.confusions_path,
        expected_checkpoint=(
            str(settings.model_path) if settings.model_path.exists() else None
        ),
    )
    safety = (
        SafetyLayer.from_calibration(
            taxonomy, settings.calibration_path, confusions=confusions
        )
        if calibrated
        else SafetyLayer(
            taxonomy, confidence_threshold=threshold, confusions=confusions
        )
    )

    state.update(
        taxonomy=taxonomy,
        classifier=classifier,
        safety=safety,
        engine=InterrogationEngine(taxonomy),
        calibrated=calibrated,
        incidents=IncidentStore(settings.incident_log_path),
    )
    log.info("Ready: %d classes, calibrated=%s", len(classifier.classes), calibrated)
    yield
    state.clear()


app = FastAPI(
    title="Funga",
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


def _build_response(
    observation_id: str, ranked, answered: set[str], energy: float | None = None
) -> IdentifyResponse:
    assessment = state["safety"].assess(ranked, energy)
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

    reviewed = _taxonomy_reviewed()
    return HealthOut(
        status="ok",
        model_loaded=isinstance(state["classifier"].backend, OnnxBackend),
        confusions_loaded=state["safety"].confusions.loaded,
        confusion_pairs=len(state["safety"].confusions.pairs),
        calibrated=state["calibrated"],
        n_classes=len(state["classifier"].classes),
        model_version=app.version,
        taxonomy_reviewed=reviewed,
        character_states_described=int(
            described_coverage(state["taxonomy"])["described"]
        ),
    )


async def _read_photo(upload: UploadFile, what: str) -> Image.Image:
    payload = await upload.read()
    if len(payload) > settings.max_upload_bytes:
        raise HTTPException(413, f"The {what} photograph is too large.")
    if not payload:
        raise HTTPException(400, f"The {what} photograph was empty.")
    try:
        picture = Image.open(io.BytesIO(payload))
        picture.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(
            400, f"The {what} photograph could not be read as an image."
        )
    return picture


def _parse_field_notes(raw: str | None) -> dict[str, str]:
    """Validate the capture form's answers against the character catalogue.

    An unknown character key, or an answer outside a character's option list,
    is rejected rather than ignored. Silently dropping it would leave the user
    believing they had told the app something they had not.
    """
    if not raw:
        return {}

    import json

    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        raise HTTPException(400, "field_notes must be a JSON object.")
    if not isinstance(parsed, dict):
        raise HTTPException(400, "field_notes must be a JSON object.")

    notes: dict[str, str] = {}
    for key, value in parsed.items():
        if value is None or value == "":
            continue  # every field is skippable
        character = CHARACTERS.get(key)
        if character is None:
            raise HTTPException(400, f"Unknown character '{key}'.")
        if not isinstance(value, str):
            raise HTTPException(400, f"Answer for '{key}' must be a string.")
        if character.options and value not in character.options:
            raise HTTPException(
                400, f"'{value}' is not one of the options for '{key}'."
            )
        notes[key] = value
    return notes


@app.get("/field-form", response_model=FieldFormOut)
def field_form() -> FieldFormOut:
    """The characters worth offering before any question is asked."""
    return FieldFormOut(
        fields=[
            FieldNoteFieldOut(
                key=c.key,
                label=c.label,
                prompt=c.prompt,
                how=c.how,
                options=list(c.options),
                effort=c.effort,
            )
            for c in field_note_characters()
        ],
        note=(
            "Every field is optional. Answer only what you actually observed "
            "-- a guess is worse than a blank, because the app cannot tell "
            "the two apart."
        ),
    )


@app.post("/identify", response_model=IdentifyResponse)
async def identify(
    image: UploadFile = File(..., description="The cap, photographed from above."),
    side: UploadFile | None = File(None, description="The mushroom from the side."),
    underside: UploadFile | None = File(
        None, description="The underside: gills, pores or spines."
    ),
    month: int | None = Form(None, ge=1, le=12),
    latitude: float | None = Form(None, ge=-90, le=90),
    longitude: float | None = Form(None, ge=-180, le=180),
    field_notes: str | None = Form(
        None, description="JSON object of character_key -> answer, all optional."
    ),
) -> IdentifyResponse:
    """Identify from one to three views, with optional field notes.

    Only the top view is required, so a single photograph still works. The
    side and underside are accepted because they carry evidence the cap does
    not -- what is under the cap separates whole families -- and because
    collecting them upfront is cheaper for the user than being asked for them
    one at a time afterwards.
    """
    if not state:
        raise HTTPException(503, "Service is still starting.")

    notes = _parse_field_notes(field_notes)

    pictures = [await _read_photo(image, "cap")]
    if side is not None:
        pictures.append(await _read_photo(side, "side"))
    if underside is not None:
        pictures.append(await _read_photo(underside, "underside"))

    prediction = state["classifier"].predict_views(pictures, month, latitude, longitude)
    ranked = prediction.ranked

    # Field notes are applied exactly as answers given to a question, so a
    # fact volunteered upfront counts the same as one asked for later.
    answered: set[str] = set()
    for key, value in notes.items():
        ranked = state["engine"].apply_answer(ranked, key, value)
        answered.add(key)

    observation_id = uuid.uuid4().hex
    observations[observation_id] = {
        "ranked": ranked,
        "answered": answered,
        # Kept so follow-up answers are assessed against the same
        # out-of-scope judgement; the photographs do not change.
        "energy": prediction.energy,
    }

    return _build_response(observation_id, ranked, answered, prediction.energy)


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

    return _build_response(
        request.observation_id, ranked, record["answered"], record.get("energy")
    )


def _region(raw: str, what: str) -> tuple[float, float, float, float]:
    """Parse an "x,y,w,h" patch, in fractions of the image."""
    parts = [piece.strip() for piece in raw.split(",")]
    if len(parts) != 4:
        raise HTTPException(
            400, f"The {what} region must be four numbers: x,y,width,height."
        )
    try:
        values = tuple(float(piece) for piece in parts)
    except ValueError:
        raise HTTPException(400, f"The {what} region must be four numbers.")
    return values  # type: ignore[return-value]


@app.post("/spore-print/match", response_model=SporePrintReadingOut)
async def match_spore_print_photo(
    image: UploadFile = File(..., description="The print on the half-white card."),
    sample_region: str = Form(
        ..., description="x,y,w,h of the deposit, as fractions of the image."
    ),
    white_region: str = Form(
        ..., description="x,y,w,h of the card's white half."
    ),
) -> SporePrintReadingOut:
    """Match a photographed spore print against the reference chart.

    The client marks two patches rather than sampling them: reading pixels is
    awkward on the device, and doing it here keeps the judgement beside the
    answer strings it has to produce.

    This never submits anything. A confident reading returns the option for
    the user to confirm, and every other outcome returns a reason and a
    ranking to order the manual picker by. Spore print colour separates
    deadly species from edible lookalikes, so the app proposes and the person
    decides.
    """
    if not state:
        raise HTTPException(503, "Service is still starting.")

    picture = await _read_photo(image, "spore print")
    sample = _region(sample_region, "sample")
    white = _region(white_region, "white card")

    try:
        reading = read_from_photograph(picture, sample, white)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    return SporePrintReadingOut(
        confident=reading.confident,
        option=reading.option,
        reason=reading.reason,
        ranked=[
            ColourMatchOut(option=m.option, distance=round(m.distance, 3))
            for m in reading.ranked
        ],
        corrected_rgb=list(reading.corrected_rgb) if reading.corrected_rgb else None,
    )


def _taxonomy_reviewed() -> bool:
    import json

    return bool(
        json.loads(settings.taxonomy_path.read_text(encoding="utf-8")).get("reviewed_by")
    )


@app.get("/disclaimer", response_model=DisclaimerOut)
def disclaimer() -> DisclaimerOut:
    """What a user acknowledges before first use.

    Served rather than shipped in the client so that one copy exists, and so
    that the statements can depend on what the service currently is. While
    there is no trained model, no fitted calibration and no reviewed taxonomy,
    the user is told each of those before they see an identification.

    `version` is a hash of the text. When any of those facts changes the text
    changes, the version changes with it, and the client asks again.
    """
    if not state:
        raise HTTPException(503, "Service is still starting.")

    built = build_disclaimer(
        model_loaded=isinstance(state["classifier"].backend, OnnxBackend),
        calibrated=state["calibrated"],
        taxonomy_reviewed=_taxonomy_reviewed(),
    )
    return DisclaimerOut(
        version=built.version,
        heading=built.heading,
        body=built.body,
        acknowledgements=[
            AcknowledgementOut(key=a.key, statement=a.statement, because=a.because)
            for a in built.acknowledgements
        ],
    )


@app.post("/incident", response_model=IncidentOut)
def incident(request: IncidentRequest, http_request: Request) -> IncidentOut:
    """Report a suspected misidentification.

    Stored for a person to read. Nothing here changes the taxonomy: see
    `docs/INCIDENTS.md` for who acts on these and how.

    A report saying someone ate it, or that anyone is unwell, is not a defect
    report. It comes back flagged, with the emergency guidance, and the client
    shows that instead of a confirmation.

    Rate limited per client, because this is the only unauthenticated write
    route the service has -- **except** for a report declaring that someone
    ate it or is unwell, which is never limited. A flood of medical reports
    costs a large file; dropping one costs something this project will not
    trade away. The check reads the request's own flags rather than the
    triaged severity, so it happens before any work is done.
    """
    if not state:
        raise HTTPException(503, "Service is still starting.")

    medical_claim = request.anyone_ate_it or request.anyone_unwell
    if not medical_claim:
        key = client_key(
            http_request.client.host if http_request.client else None,
            http_request.headers.get("x-forwarded-for"),
            trust_forwarded_for=settings.trust_forwarded_for,
        )
        if not incident_limiter.allow(key):
            retry_after = incident_limiter.retry_after(key)
            # Logged at WARNING: a client hitting the limit is either broken
            # or hostile, and a limiter nobody can see firing is a limiter
            # that hides an attack rather than reporting one.
            log.warning(
                "incident rate limit reached for %s; refusing for %ds", key, retry_after
            )
            raise HTTPException(
                429,
                detail=(
                    "Too many reports from this device. Try again later. "
                    "If someone has eaten a mushroom or is unwell, say so on "
                    "the form and it will always go through."
                ),
                headers={"Retry-After": str(retry_after)},
            )

    report = build_report(
        taxonomy=state["taxonomy"],
        observation_id=request.observation_id,
        verdict=request.verdict,
        reported_candidates=request.reported_candidates,
        model_version=request.model_version,
        calibrated=request.calibrated,
        believed_species_key=request.believed_species_key,
        account=request.account,
        anyone_ate_it=request.anyone_ate_it,
        anyone_unwell=request.anyone_unwell,
        contact=request.contact,
    )
    state["incidents"].append(report)
    log.warning("incident %s severity=%s", report.incident_id, report.severity)

    medical = report.severity == "medical"
    return IncidentOut(
        incident_id=report.incident_id,
        severity=report.severity,
        acknowledgement=(
            "Recorded. A person reads these; nothing is changed automatically."
        ),
        medical_emergency=medical,
        emergency_guidance=EMERGENCY_GUIDANCE if medical else None,
    )


@app.get("/incident/{incident_id}", response_model=IncidentStatusOut)
def incident_status(incident_id: str) -> IncidentStatusOut:
    """What happened to a report.

    `docs/INCIDENTS.md` listed "a way to tell a reporter what happened to
    their report" as blocking for release. This is it, and it deliberately
    needs no account, no email and no contact address: the reporter keeps
    the id, and the id is the whole credential.

    That choice is the privacy answer as much as the engineering one. The
    alternative was storing an address in order to write to it later, which
    means holding personal data on somebody whose only involvement was
    telling us we were wrong.

    Unauthenticated by necessity and safe because of what it returns: an
    outcome, a note a person wrote for the reporter, and nothing else. No
    free text of theirs, no contact, no species, nothing about any other
    report. A uuid4 is not guessable, but it is the sort of string that gets
    pasted into a forum, so the response is written for a reader who may not
    be the person who filed it.
    """
    if not state:
        raise HTTPException(503, "Service is still starting.")

    status = state["incidents"].status(incident_id)
    if status is None:
        # Deliberately the same 404 for a malformed id and an unknown one.
        raise HTTPException(404, "No report with that reference.")
    return IncidentStatusOut(**asdict(status))


@app.get("/species", response_model=SpeciesListOut)
def species_list() -> SpeciesListOut:
    """Every species in the label space, for naming one.

    Needed by the incident form. The failure worth reporting most is the app
    missing something dangerous, and the species it missed is by definition
    not among the candidates it offered -- so a reporter who can only pick
    from those candidates can never describe it.
    """
    if not state:
        raise HTTPException(503, "Service is still starting.")

    taxonomy: TaxonomyService = state["taxonomy"]
    return SpeciesListOut(
        species=[
            SpeciesListEntryOut(
                species_key=sp.key,
                scientific_name=sp.scientific_name,
                common_names=list(sp.common_names),
            )
            for sp in sorted(
                taxonomy.species.values(), key=lambda s: s.scientific_name
            )
        ],
        note=(
            "These are the species this app knows. It is a small fraction of "
            "the British fungi, and a mushroom missing from it cannot be "
            "identified here at all."
        ),
    )


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
