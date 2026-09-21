"""Regression tests for the checkpoint -> ONNX seam.

Both cases here were found by running the pipeline end to end rather than by
reading it. Each one produced a working-looking artefact or a failure that
only surfaced after training had already been paid for.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("timm")
pytest.importorskip("onnx")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml"))

from fungi_ml.export import emitted_opset, export_onnx  # noqa: E402
from fungi_ml.models.build import build_model, load_checkpoint_model  # noqa: E402

CLASSES = ["amanita-phalloides", "agaricus-campestris", "cantharellus-cibarius"]


def _config(use_metadata: bool = True) -> dict:
    return {
        "data": {"image_size": 64},
        "model": {
            "backbone": "resnet18",
            "pretrained": False,
            "drop_rate": 0.1,
            "drop_path_rate": 0.0,
            "use_metadata": use_metadata,
        },
    }


def _checkpoint(tmp_path: Path, use_metadata: bool = True) -> Path:
    config = _config(use_metadata)
    model = build_model(config, len(CLASSES))
    path = tmp_path / "best.pt"
    torch.save(
        {"model": model.state_dict(), "classes": CLASSES, "config": config,
         "metrics": {"risk": 0.0}, "epoch": 0},
        path,
    )
    return path


@pytest.mark.parametrize("use_metadata", [True, False])
def test_checkpoint_rebuilds_with_the_architecture_it_was_trained_with(tmp_path, use_metadata):
    """`use_metadata` changes the state dict, so reconstruction must honour it.

    Calibration and export used to rebuild the model from `backbone` alone.
    A run configured without the metadata branch therefore trained happily and
    then failed to load at calibration time -- after the GPU bill.
    """
    checkpoint = torch.load(_checkpoint(tmp_path, use_metadata), weights_only=False)
    model = load_checkpoint_model(checkpoint)

    assert (model.metadata_encoder is not None) is use_metadata
    assert not model.training, "reconstructed model must be in eval mode"

    logits = model(torch.randn(2, 3, 64, 64), torch.zeros(2, 7))
    assert logits.shape == (2, len(CLASSES))


def test_export_honours_the_requested_opset(tmp_path):
    """An export at an opset other than the requested one must never ship.

    torch's exporter treats `opset_version` as a request: when its internal
    down-conversion fails it warns, keeps the higher opset and returns
    normally. The file then runs fine on a current onnxruntime and fails only
    against a pinned runtime or an on-device converter.
    """
    path = export_onnx(_checkpoint(tmp_path), opset=17, verify=True)
    assert emitted_opset(path) == 17


def test_export_writes_labels_in_checkpoint_order(tmp_path):
    """A label order that drifts from the model maps every prediction wrong."""
    import json

    path = export_onnx(_checkpoint(tmp_path), opset=17, verify=False)
    shipped = json.loads(path.with_name("labels.json").read_text())["classes"]
    assert shipped == CLASSES


def test_export_raises_when_no_exporter_can_honour_the_opset(tmp_path, monkeypatch):
    """If even the fallback cannot produce the requested opset, refuse to ship.

    The guard is driven by what is actually written to disk, so this fakes a
    file that always reads back at the wrong opset. Degrading quietly to a
    different opset than the caller asked for is the failure mode the whole
    check exists to prevent.
    """
    import fungi_ml.export as export_module

    monkeypatch.setattr(export_module, "emitted_opset", lambda _path: 99)
    with pytest.raises(RuntimeError, match="opset 17"):
        export_onnx(_checkpoint(tmp_path), opset=17, verify=False)
