"""Service configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    taxonomy_path: Path = ROOT / "data" / "taxonomy.seed.json"
    model_path: Path = ROOT / "ml" / "runs" / "baseline" / "model.onnx"
    labels_path: Path = ROOT / "ml" / "runs" / "baseline" / "labels.json"
    calibration_path: Path = ROOT / "ml" / "runs" / "baseline" / "calibration.json"

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
