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
        if row["species_key"] == "not-determined":
            # Held, not measured: nobody has identified it yet. The two
            # rows this exists for are a possible Tricholoma and a
            # possible Cortinarius, and a genus with two deadly members is
            # the last place to write down a guess as though it were a
            # determination. It still has to say what was seen, or there
            # is nothing for a person to work from.
            assert not row["confirmed_by"].strip(), (
                f"{row['filename']}: confirmed_by on an undetermined row -- "
                f"if somebody determined it, give it the species key"
            )
            assert row.get("notes"), (
                f"{row['filename']}: an undetermined row must describe what "
                f"is in the photograph, or it cannot be determined later"
            )
            continue
        if row["species_key"] == "not-in-label-space":
            # A photograph of something the 244 do not contain. The first
            # eight real photographs produced one -- Craterellus
            # tubaeformis, the yellowfoot, an ordinary British species --
            # and for these the right answer is a refusal. Dropping the
            # row would hide the gap; labelling it with the nearest
            # species in the label space would be a lie about the picture.
            assert row.get("notes"), (
                f"{row['filename']}: an out-of-label-space row must name "
                f"what it actually is in `notes`, or nobody can check it"
            )
            continue
        assert taxonomy.get(row["species_key"]) is not None, (
            f"{row['filename']}: {row['species_key']!r} is not in the label "
            f"space -- check the key against data/taxonomy.seed.json"
        )
        assert "confirmed_by" in row, (
            f"{row['filename']}: the manifest must record WHO confirmed the "
            f"label. A guess and a determination are not the same evidence."
        )
        assert row.get("visible"), (
            f"{row['filename']}: 'visible' is the column that makes this set "
            f"worth more than a score -- whether the app is honest about a "
            f"photograph that does not show the diagnostic feature"
        )


def test_photographs_are_stripped_of_location_on_the_way_in():
    """Every one of the first eight real photographs carried GPS.

    They were never committed -- `eval/photos/` is ignored and git has
    never held an image -- but Martin asked for them deleted on
    2026-10-29 anyway, and deleting is a fix that has to be remembered
    every time. Stripping on ingest does not.

    Read from source because exercising it needs a photograph, and the
    point is that the repository never holds one.
    """
    source = (ROOT / "scripts" / "add_eval_photo.py").read_text(encoding="utf-8")
    assert "exif_transpose" in source, (
        "orientation must be applied to the PIXELS before the metadata is "
        "dropped, or a portrait photograph is served to the model sideways "
        "and the score is blamed on distribution shift"
    )
    assert "clean.paste(upright)" in source, (
        "the saved image must be a fresh one: PIL writes info['exif'] back "
        "out, so saving the transposed original can keep what was stripped"
    )
    assert "refusing to overwrite" in source, (
        "a re-added photograph must not silently replace another, or the "
        "manifest's label stops matching its picture"
    )


def test_the_runner_notices_a_photograph_that_slipped_through():
    """The strip is a convenience; this is the guard.

    A photograph copied in by hand rather than added by the script keeps
    its GPS, and nothing else in the pipeline would ever mention it.
    """
    source = (ROOT / "scripts" / "real_photo_eval.py").read_text(encoding="utf-8")
    assert "34853" in source, (
        "the runner must check for the GPSInfo tag by number -- its name "
        "varies between Pillow versions"
    )
    assert "still carry GPS" in source


def test_the_runner_holds_an_undetermined_row_rather_than_dropping_it():
    """And says so. A set that quietly skips what it cannot grade looks
    smaller and cleaner than it is, which is the same shape as the report
    that printed a warning and then reassured past it forty lines later."""
    source = (ROOT / "scripts" / "real_photo_eval.py").read_text(
        encoding="utf-8")
    assert 'NOT_DETERMINED = "not-determined"' in source
    assert "undetermined.append(" in source, (
        "an undetermined row must be collected, not merely skipped"
    )
    assert "HELD, not measured" in source, (
        "the summary must report how many photographs are waiting on a "
        "determination"
    )
