"""Export a trained checkpoint to ONNX for serving.

Exports with dynamic batch axes and both inputs (image and metadata) so the
serving path matches training exactly. The verification step is not optional:
a silently wrong export produces a model that runs, returns plausible
numbers, and is subtly wrong -- the worst possible failure for this
application.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import torch

log = logging.getLogger(__name__)


def export_onnx(
    checkpoint_path: str | Path,
    out_path: str | Path | None = None,
    opset: int = 17,
    verify: bool = True,
    tolerance: float = 1e-3,
) -> Path:
    from .models.build import FungiClassifier

    checkpoint_path = Path(checkpoint_path)
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    classes = checkpoint["classes"]
    config = checkpoint["config"]
    image_size = config["data"]["image_size"]

    model = FungiClassifier(
        num_classes=len(classes),
        backbone=config["model"]["backbone"],
        pretrained=False,
    )
    model.load_state_dict(checkpoint["model"])
    model.eval()

    out_path = Path(out_path or checkpoint_path.with_name("model.onnx"))
    dummy_image = torch.randn(1, 3, image_size, image_size)
    dummy_metadata = torch.zeros(1, 7)

    torch.onnx.export(
        model,
        (dummy_image, dummy_metadata),
        str(out_path),
        input_names=["image", "metadata"],
        output_names=["logits"],
        dynamic_axes={
            "image": {0: "batch"},
            "metadata": {0: "batch"},
            "logits": {0: "batch"},
        },
        opset_version=opset,
        do_constant_folding=True,
    )
    log.info("Exported to %s", out_path)

    # Ship the label order beside the model. A model whose class order does
    # not match its labels maps every prediction to the wrong species.
    labels_path = out_path.with_name("labels.json")
    labels_path.write_text(
        json.dumps({"classes": classes}, indent=2), encoding="utf-8"
    )

    if verify:
        _verify(model, out_path, dummy_image, dummy_metadata, tolerance)

    return out_path


def _verify(model, onnx_path: Path, image, metadata, tolerance: float) -> None:
    import onnxruntime as ort

    with torch.no_grad():
        expected = model(image, metadata).numpy()

    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    actual = session.run(
        None, {"image": image.numpy(), "metadata": metadata.numpy()}
    )[0]

    max_difference = float(np.abs(expected - actual).max())
    if max_difference > tolerance:
        raise RuntimeError(
            f"ONNX export diverges from the PyTorch model by {max_difference:.6f} "
            f"(tolerance {tolerance}). Do not ship this model."
        )
    log.info("Export verified: max difference %.2e", max_difference)


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Export a checkpoint to ONNX.")
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--out")
    ap.add_argument("--opset", type=int, default=17)
    ap.add_argument("--no-verify", action="store_true")
    args = ap.parse_args()

    export_onnx(args.checkpoint, args.out, args.opset, verify=not args.no_verify)
