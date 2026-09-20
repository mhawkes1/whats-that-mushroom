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

    image_size: int = 384
    max_upload_bytes: int = 12 * 1024 * 1024

    # Overridden by the fitted calibration when it exists.
    confidence_threshold: float = 0.80

    cors_origins: list[str] = ["*"]

    model_config = SettingsConfigDict(env_prefix="WTM_")


settings = Settings()
