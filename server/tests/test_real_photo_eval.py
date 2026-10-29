"""The real-photograph evaluation set, and the guard that makes it mean
anything.

Every figure in a model card is measured on held-out iNaturalist images,
which share a distribution with the training set. This set is the other
population -- photographs a person took -- and the thing it must never do
is report a number taken against the stub backend.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "real_photo_eval.py"


def test_it_refuses_to_measure_the_stub(monkeypatch, tmp_path):
    """A measurement against deterministic fakes is fabricated, not noisy.

    On 2026-10-29 a browser-renamed `model (2).onnx` left the server on the
    stub, and an hour went into analysing an identification a random number
    generator had produced. An evaluation script that would have written
    that into `eval/results/` as a dated record is worse than no script.
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    import importlib.util

    spec = importlib.util.spec_from_file_location("real_photo_eval", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    monkeypatch.setattr(mod, "_health", lambda base: {"model_loaded": False})
    monkeypatch.setattr(sys, "argv", ["real_photo_eval.py"])
    assert mod.main() == 3, (
        "a run against the stub backend must fail loudly rather than write "
        "a fabricated result"
    )


def test_the_photographs_are_not_committed_but_the_manifest_is():
    """Phone photographs are large, personal and carry location metadata.

    The manifest and the results are the reviewable artefacts; the images
    are the raw material. Asking git itself, because a gitignore rule
    ending in `/` silently kills every negation under it -- this project
    has been bitten by that three times.
    """
    def ignored(path: str) -> bool:
        return subprocess.run(
            ["git", "check-ignore", path], cwd=ROOT, capture_output=True
        ).returncode == 0

    assert ignored("eval/photos/anything.jpg"), (
        "a photograph must not be committed -- they carry EXIF location"
    )
    assert not ignored("eval/real-photos.csv"), (
        "the manifest is the reviewable artefact and must be kept"
    )
    assert not ignored("eval/README.md")


def test_every_manifest_row_names_a_species_in_the_label_space():
    """A wrong label here reports the app as failing where it was right.

    The set is only worth anything if it is believed, so the species key
    has to resolve. A typo would otherwise be silently skipped and the
    photograph would vanish from a count nobody re-checks.
    """
    sys.path.insert(0, str(ROOT / "ml"))
    from fungi_ml.taxonomy import Taxonomy

    taxonomy = Taxonomy.load(ROOT / "data" / "taxonomy.seed.json")
    rows = list(csv.DictReader(
        (ROOT / "eval" / "real-photos.csv").open(encoding="utf-8")))
    assert rows, "the manifest must not be empty"

    for row in rows:
        assert taxonomy.get(row["species_key"]) is not None, (
            f"{row['filename']}: {row['species_key']!r} is not in the label "
            f"space -- check the key against data/taxonomy.seed.json"
        )
        assert row.get("visible"), (
            f"{row['filename']}: 'visible' is the column that makes this set "
            f"worth more than a score -- whether the app is honest about a "
            f"photograph that does not show the diagnostic feature"
        )
