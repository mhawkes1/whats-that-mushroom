"""The label list and the model must be the same list, in the same order.

A classifier's output is an *index*. `labels.json` is the only thing that
turns index 37 into a species name, and it is a property of the checkpoint,
not of the taxonomy. Two places were willing to supply one anyway.

`main.py` fell back to `sorted(taxonomy.species)` whenever `labels.json` was
missing. That is correct and useful for the stub, whose names are meaningless
by construction. For a trained model it is a guess: the checkpoint's order is
`sorted(species that survived the image-count filter)`, so the two coincide
only while nothing was filtered out, and the moment one species is, every
class after the gap is named as its neighbour. Confident output, plausible
names, nothing downstream able to notice -- and a DEADLY species served under
a harmless one, which is the same shape of failure as the GBIF genus-key
gotcha in CLAUDE.md.

It mattered the day a trained model first had to be installed by hand, by
copying three files into a directory. Two of three is a silent relabelling.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))


def _tiny_onnx(path: Path, n_classes: int) -> Path:
    torch = pytest.importorskip("torch", reason="exporting needs torch")

    class Tiny(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.fc = torch.nn.Linear(4, n_classes)

        def forward(self, x):  # noqa: ANN001
            return self.fc(x)

    # No dynamic axes: the check reads the last dimension, and a fixed batch
    # keeps the export quiet.
    torch.onnx.export(
        Tiny(), torch.zeros(1, 4), str(path),
        input_names=["image"], output_names=["logits"],
    )
    return path


@pytest.fixture(scope="module")
def model_of_244(tmp_path_factory) -> Path:
    return _tiny_onnx(tmp_path_factory.mktemp("onnx") / "model.onnx", 244)


def test_a_matching_label_list_loads(model_of_244):
    from app.inference import OnnxBackend

    backend = OnnxBackend(model_of_244, [f"species-{i:03d}" for i in range(244)])
    assert len(backend.classes) == 244


@pytest.mark.parametrize("n", [243, 245])
def test_a_label_list_of_the_wrong_width_is_refused(model_of_244, n):
    """Off by one in either direction, which is what a filtered-out species
    and an added one respectively look like."""
    from app.inference import OnnxBackend

    classes = [f"species-{i:03d}" for i in range(n)]
    with pytest.raises(ValueError, match="244 classes but labels.json lists"):
        OnnxBackend(model_of_244, classes)


def test_a_model_without_labels_is_refused_rather_than_guessed(tmp_path, monkeypatch):
    """The failure mode of installing a trained model by hand.

    The file need not be a valid model: the refusal has to happen before
    anything tries to load it, because by then the label order has already
    been invented.
    """
    from app import main
    from app.config import Settings

    (tmp_path / "model.onnx").write_bytes(b"not really a model")
    monkeypatch.setattr(
        main, "settings",
        Settings(model_path=tmp_path / "model.onnx",
                 labels_path=tmp_path / "labels.json",
                 calibration_path=tmp_path / "calibration.json"),
    )

    with pytest.raises(RuntimeError, match="labels.json"):
        with _run_lifespan(main):
            pass


def _run_lifespan(main):
    """Drive the app's lifespan directly; TestClient would mask the error."""
    import asyncio
    from contextlib import contextmanager

    @contextmanager
    def runner():
        loop = asyncio.new_event_loop()
        ctx = main.lifespan(main.app)
        try:
            loop.run_until_complete(ctx.__aenter__())
            yield
            loop.run_until_complete(ctx.__aexit__(None, None, None))
        finally:
            loop.close()

    return runner()


def test_the_stub_still_derives_its_labels(tmp_path, monkeypatch):
    """The fallback is right when there is no model, and must survive.

    Removing it would stop the service starting on a fresh clone, which is
    every first run and every CI job.
    """
    from app import main
    from app.config import Settings

    monkeypatch.setattr(
        main, "settings",
        Settings(model_path=tmp_path / "absent.onnx",
                 labels_path=tmp_path / "labels.json",
                 calibration_path=tmp_path / "absent.json"),
    )
    with _run_lifespan(main):
        classes = main.state["classifier"].classes
    assert len(classes) > 200, "the stub should range over the whole taxonomy"


def test_the_real_labels_file_matches_the_taxonomy_in_length_today():
    """And records that this is luck, not a guarantee.

    All 244 species cleared `--min-images` on the first real run, so the
    taxonomy's order and the checkpoint's happen to be identical. The
    refusal above exists for the run where that stops being true.
    """
    taxonomy = json.loads(
        (ROOT / "data" / "taxonomy.seed.json").read_text(encoding="utf-8")
    )
    labels = ROOT / "ml" / "runs" / "baseline" / "labels.json"
    if not labels.exists():
        pytest.skip("no trained run in this checkout")
    classes = json.loads(labels.read_text(encoding="utf-8"))["classes"]
    keys = sorted(s["key"] for s in taxonomy["species"])
    assert classes == keys or len(classes) < len(keys), (
        "the checkpoint carries classes the taxonomy does not"
    )


# --- Recovering a lost labels.json -----------------------------------------


def _run_recover(model: Path, out: Path, taxonomy: Path | None = None):
    import subprocess

    cmd = [sys.executable, str(ROOT / "scripts" / "recover_labels.py"),
           "--model", str(model), "--out", str(out)]
    if taxonomy:
        cmd += ["--taxonomy", str(taxonomy)]
    return subprocess.run(cmd, capture_output=True, text=True)


def test_recovery_succeeds_only_when_the_widths_prove_it(model_of_244, tmp_path):
    """244 classes against 244 species means nothing was filtered out, so
    the derived order IS the checkpoint's order. That is a proof, not a
    hunch, and it is the only case the script writes anything in."""
    out = tmp_path / "labels.json"
    result = _run_recover(model_of_244, out)
    assert result.returncode == 0, result.stderr
    classes = json.loads(out.read_text(encoding="utf-8"))["classes"]
    taxonomy = json.loads(
        (ROOT / "data" / "taxonomy.seed.json").read_text(encoding="utf-8")
    )
    assert classes == sorted(s["key"] for s in taxonomy["species"])


def test_recovery_refuses_when_species_were_filtered_out(tmp_path):
    """The case the refusal exists for. Which species went is recorded in
    the manifest, which is exactly what a destroyed pod takes with it."""
    model = _tiny_onnx(tmp_path / "narrow.onnx", 240)
    out = tmp_path / "labels.json"
    result = _run_recover(model, out)
    assert result.returncode == 1
    assert not out.exists(), "nothing may be written on the refusing path"
    assert "REFUSING" in result.stderr


def test_recovery_never_overwrites_a_real_labels_file(model_of_244, tmp_path):
    """A derivation must not replace the thing it is standing in for."""
    out = tmp_path / "labels.json"
    out.write_text('{"classes": ["the-real-one"]}', encoding="utf-8")
    result = _run_recover(model_of_244, out)
    assert result.returncode == 2
    assert "the-real-one" in out.read_text(encoding="utf-8")


def test_a_recovered_file_satisfies_the_backend_it_was_written_for(
    model_of_244, tmp_path
):
    """End to end: recover, then load. If OnnxBackend still refuses it, the
    recovery produced something that looks right and is not."""
    from app.inference import OnnxBackend

    out = tmp_path / "labels.json"
    assert _run_recover(model_of_244, out).returncode == 0
    classes = json.loads(out.read_text(encoding="utf-8"))["classes"]
    assert len(OnnxBackend(model_of_244, classes).classes) == 244
