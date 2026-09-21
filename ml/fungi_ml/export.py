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
    from .models.build import load_checkpoint_model

    checkpoint_path = Path(checkpoint_path)
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    classes = checkpoint["classes"]
    config = checkpoint["config"]
    image_size = config["data"]["image_size"]

    model = load_checkpoint_model(checkpoint)

    out_path = Path(out_path or checkpoint_path.with_name("model.onnx"))
    dummy_image = torch.randn(1, 3, image_size, image_size)
    dummy_metadata = torch.zeros(1, 7)

    _export_at_opset(model, (dummy_image, dummy_metadata), out_path, opset)
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


def emitted_opset(path: Path) -> int:
    """The default-domain opset the file on disk actually declares."""
    import onnx

    model = onnx.load(str(path), load_external_data=False)
    for entry in model.opset_import:
        if entry.domain in ("", "ai.onnx"):
            return int(entry.version)
    raise RuntimeError(f"{path} declares no default-domain opset")


def _export_at_opset(model, inputs, out_path: Path, opset: int) -> None:
    """Write the ONNX file, and guarantee the opset we asked for is the one we got.

    `torch.onnx.export` takes `opset_version` as a request, not a promise. The
    torch.export-based exporter (the default since torch 2.9) emits at its own
    opset and then tries to down-convert; when that conversion fails it logs a
    warning, leaves the model at the higher opset and returns successfully.
    We measured that here: asking for 17 produced a file declaring 18, with no
    non-zero exit and no exception.

    Nothing downstream would have caught it. onnxruntime on the dev box is new
    enough to run either, so the export verifies, serves and looks correct --
    right up until it meets a pinned runtime or the Core ML/TFLite converters
    the on-device work needs, which do enforce the opset they advertise.

    So: export, read back what was actually written, and if it is not what was
    asked for, retry with the TorchScript exporter, which honours
    `opset_version` exactly. If neither can produce it, raise -- an export at
    an opset the caller did not ask for is exactly the silently-wrong artefact
    this module exists to refuse to ship.
    """
    image, metadata = inputs
    common = dict(
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

    torch.onnx.export(model, (image, metadata), str(out_path), **common)
    written = emitted_opset(out_path)
    if written == opset:
        return

    log.warning(
        "Exporter emitted opset %d despite a request for %d; retrying with the "
        "TorchScript exporter, which honours it.",
        written, opset,
    )
    torch.onnx.export(model, (image, metadata), str(out_path), dynamo=False, **common)

    written = emitted_opset(out_path)
    if written != opset:
        raise RuntimeError(
            f"Could not export at opset {opset}; got {written}. Either install a "
            f"toolchain that supports it or pass --opset {written} deliberately. "
            f"Do not ship a model whose opset is not the one you asked for."
        )


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
    log.info(
        "Export verified: max difference %.2e, opset %d",
        max_difference, emitted_opset(onnx_path),
    )


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
