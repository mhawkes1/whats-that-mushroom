"""Model serving.

Loads an exported ONNX classifier and applies the calibration fitted at
training time. The important detail: the temperature is applied *here*, so
every probability leaving this module is calibrated. The safety layer's
thresholds are meaningless otherwise.

A stub backend is provided so the API, the safety layer and the mobile app
can be developed and tested before a trained model exists.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np
from PIL import Image

log = logging.getLogger(__name__)

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def preprocess(image: Image.Image, size: int = 384) -> np.ndarray:
    """Resize, centre-crop and normalise, matching the eval transform exactly.

    Any divergence from the training-time transform silently degrades
    accuracy, so this mirrors `build_transforms(train=False)`.
    """
    image = image.convert("RGB")
    scale = int(size * 1.14)
    w, h = image.size
    if w < h:
        new_w, new_h = scale, round(h * scale / w)
    else:
        new_w, new_h = round(w * scale / h), scale
    image = image.resize((new_w, new_h), Image.Resampling.BILINEAR)

    left = (new_w - size) // 2
    top = (new_h - size) // 2
    image = image.crop((left, top, left + size, top + size))

    array = np.asarray(image, dtype=np.float32) / 255.0
    array = (array - IMAGENET_MEAN) / IMAGENET_STD
    return np.transpose(array, (2, 0, 1))[None, ...]


def encode_metadata(
    month: int | None, latitude: float | None, longitude: float | None
) -> np.ndarray:
    """Mirror of `fungi_ml.data.prepare.encode_metadata` for a single query."""
    vector = np.zeros((1, 7), dtype=np.float32)

    if month:
        radians = 2 * np.pi * (min(max(month, 1), 12) - 1) / 12
        vector[0, 0] = np.sin(radians)
        vector[0, 1] = np.cos(radians)
        vector[0, 2] = 1.0

    if latitude is not None and longitude is not None:
        lat_r, lon_r = np.radians(latitude), np.radians(longitude)
        vector[0, 3] = np.cos(lat_r) * np.cos(lon_r)
        vector[0, 4] = np.cos(lat_r) * np.sin(lon_r)
        vector[0, 5] = np.sin(lat_r)
        vector[0, 6] = 1.0

    return vector


def softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - logits.max(axis=-1, keepdims=True)
    exp = np.exp(shifted)
    return exp / exp.sum(axis=-1, keepdims=True)


class Backend(ABC):
    classes: list[str]

    @abstractmethod
    def logits(self, image: np.ndarray, metadata: np.ndarray) -> np.ndarray: ...


class OnnxBackend(Backend):
    def __init__(self, model_path: str | Path, classes: list[str]):
        import onnxruntime as ort

        self.session = ort.InferenceSession(
            str(model_path), providers=["CPUExecutionProvider"]
        )
        self.classes = classes
        self.input_names = [i.name for i in self.session.get_inputs()]
        log.info("Loaded ONNX model with inputs %s", self.input_names)

    def logits(self, image: np.ndarray, metadata: np.ndarray) -> np.ndarray:
        feed = {self.input_names[0]: image}
        if len(self.input_names) > 1:
            feed[self.input_names[1]] = metadata
        return np.asarray(self.session.run(None, feed)[0])


class StubBackend(Backend):
    """Deterministic fake predictions for development and testing.

    Derives a stable pseudo-distribution from the image content so the same
    photograph always yields the same answer, which makes the mobile app and
    the API testable without a trained model.
    """

    def __init__(self, classes: list[str], seed: int = 0):
        self.classes = classes
        self.seed = seed

    def logits(self, image: np.ndarray, metadata: np.ndarray) -> np.ndarray:
        digest = int(abs(float(np.sum(image))) * 1000) % (2**31)
        rng = np.random.default_rng(digest + self.seed)
        base = rng.normal(0, 1.2, size=(1, len(self.classes))).astype(np.float32)
        base[0, rng.integers(0, len(self.classes))] += 4.0
        return base


class Classifier:
    """Backend plus calibration. The only thing the API talks to."""

    def __init__(
        self,
        backend: Backend,
        temperature: float = 1.0,
        image_size: int = 384,
    ):
        self.backend = backend
        self.temperature = max(temperature, 1e-3)
        self.image_size = image_size

    @property
    def classes(self) -> list[str]:
        return self.backend.classes

    @classmethod
    def load(
        cls,
        model_path: str | Path | None,
        labels_path: str | Path,
        calibration_path: str | Path | None = None,
        image_size: int = 384,
    ) -> "Classifier":
        classes = json.loads(Path(labels_path).read_text(encoding="utf-8"))["classes"]

        temperature = 1.0
        if calibration_path and Path(calibration_path).exists():
            temperature = json.loads(
                Path(calibration_path).read_text(encoding="utf-8")
            )["temperature"]
        else:
            log.warning(
                "No calibration file. Serving UNCALIBRATED probabilities -- the "
                "safety thresholds are not meaningful until calibration is fitted."
            )

        if model_path and Path(model_path).exists():
            backend: Backend = OnnxBackend(model_path, classes)
        else:
            log.warning("No model at %s -- using the stub backend.", model_path)
            backend = StubBackend(classes)

        return cls(backend, temperature=temperature, image_size=image_size)

    def predict(
        self,
        image: Image.Image,
        month: int | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> list[tuple[str, float]]:
        """Return calibrated (species_key, probability), highest first."""
        tensor = preprocess(image, self.image_size)
        metadata = encode_metadata(month, latitude, longitude)

        logits = self.backend.logits(tensor, metadata)
        probabilities = softmax(logits / self.temperature)[0]

        ranked = sorted(
            zip(self.classes, probabilities.tolist()), key=lambda kv: -kv[1]
        )
        return ranked
