"""Service configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


# Which run is being served. Named rather than generic: `baseline` said
# nothing about which of four runs was live, and the run's own committed
# evidence -- labels.json, calibration.json, report.json, MODEL_CARD.md --
# already lives under its real name. Pointing here means the served model
# sits with the numbers that justify serving it, and the confusion graph's
# run check lines up without anything being copied about.
#
# Run five, 2026-10-30: 271 species, risk-weighted error 2.0766, coverage
# 72.6%, 18 dangerous confusions and **0 silent** -- the first run to reach
# zero natively, on test and on validation both. See ml/runs/run5/MODEL_CARD.md.
#
# It is NOT straightforwardly better than run four (244 species, risk
# 1.0820, coverage 85.0%), and those figures are not comparable anyway:
# different label space, different dataset, different split. What is sound
# is run five's own curve, which shows rule 6 selecting epoch 1 out of a
# flat noise band -- so the coverage is a selection artefact rather than a
# capability one, and that question is open.
#
# Pointed here so the 271-species model can be looked at. Reverting to
# `run4-b32` is this one line plus regenerating data/model-confusions.json
# from that run's predictions.npz.
RUN = ROOT / "ml" / "runs" / "run5"


class Settings(BaseSettings):
    taxonomy_path: Path = ROOT / "data" / "taxonomy.seed.json"
    model_path: Path = RUN / "model.onnx"
    labels_path: Path = RUN / "labels.json"
    calibration_path: Path = RUN / "calibration.json"
    # What THIS checkpoint confuses, from scripts/confusion_graph.py.
    # Absent is legitimate and means the taxonomy's field lookalikes
    # alone, which is where the app was before run one was measured.
    confusions_path: Path = ROOT / "data" / "model-confusions.json"

    # Append-only. See docs/INCIDENTS.md for what is done with these.
    incident_log_path: Path = ROOT / "data" / "incidents.jsonl"

    image_size: int = 384
    max_upload_bytes: int = 12 * 1024 * 1024

    # Overridden by the fitted calibration when it exists.
    confidence_threshold: float = 0.80

    cors_origins: list[str] = ["*"]

    # Rate limiting on POST /incident. See server/app/ratelimit.py and the
    # "Before launch" list in docs/INCIDENTS.md. A report declaring that
    # someone ate it, or is unwell, is never limited.
    incident_rate_limit: int = 5
    incident_rate_window_seconds: int = 3600
    # Only enable behind a proxy that OVERWRITES X-Forwarded-For. Trusting a
    # caller-supplied header hands anyone a fresh quota per request.
    trust_forwarded_for: bool = False

    model_config = SettingsConfigDict(env_prefix="WTM_")


settings = Settings()
