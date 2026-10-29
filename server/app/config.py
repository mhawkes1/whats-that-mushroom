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
# Run four, 2026-10-28: risk-weighted error 1.0820, coverage 85.0%,
# 7 dangerous confusions. See ml/runs/run4-b32/MODEL_CARD.md.
RUN = ROOT / "ml" / "runs" / "run4-b32"


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
