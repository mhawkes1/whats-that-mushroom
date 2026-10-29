"""The end-of-run check that should have existed yesterday.

A training run produces seven small files and three large ones. Until
2026-10-28 that was a list in the run-book's step 9 -- which means it
depended on somebody reading it at the end of a long day, on a machine
billing by the hour, with the interesting part already over.

It did not survive that. `calibration.json` was never taken off the first
real run and **cannot be reconstructed**: temperature scaling is fitted on
the validation split, so recovering it needs the images and the checkpoint,
and both were destroyed with the pod. `labels.json` went the same way and
was recoverable only by luck. The app now runs with `calibrated=False`,
falling back to a 0.80 threshold and an unfitted energy check, because of a
few hundred kilobytes nobody was told to drag onto a desktop.

So the list became a check that exits non-zero while anything is missing --
at the one moment it can still be fixed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "finish_run.py"


def _run(run_dir: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--run-dir", run_dir],
        cwd=ROOT, capture_output=True, text=True,
    )


@pytest.fixture
def complete_run(tmp_path, monkeypatch):
    """A run directory inside the repo, because the check reads .gitignore.

    Named under `ml/runs/` so the real negations apply to it -- a fixture
    that sidestepped them would pass while the thing being checked was
    broken.
    """
    run = ROOT / "ml" / "runs" / "_pytest_probe"
    processed = ROOT / "data" / "processed"
    run.mkdir(parents=True, exist_ok=True)
    processed.mkdir(parents=True, exist_ok=True)
    created = []
    for name in ("MODEL_CARD.md", "report.json", "calibration.json",
                 "labels.json", "config.yaml", "history.json"):
        (run / name).write_text("{}", encoding="utf-8")
        created.append(run / name)
    np.savez_compressed(run / "predictions.npz", probs=np.zeros((2, 2), np.float16))
    created.append(run / "predictions.npz")
    # The validation predictions, which a safety threshold may honestly be
    # tuned on -- unlike the test split, which gates release.
    np.savez_compressed(run / "predictions-val.npz", probs=np.zeros((2, 2), np.float16))
    created.append(run / "predictions-val.npz")
    splits = processed / "splits.csv.gz"
    existed = splits.exists()
    if not existed:
        import pandas as pd
        pd.DataFrame({"species_key": ["a"], "observation_id": ["o"],
                      "image_url": ["u"], "path": ["p"], "split": ["train"]}
                     ).to_csv(splits, index=False, compression="gzip")
    yield "ml/runs/_pytest_probe"
    for path in created:
        path.unlink(missing_ok=True)
    run.rmdir()
    if not existed:
        splits.unlink(missing_ok=True)


def test_a_complete_run_passes_and_says_it_is_safe_to_stop(complete_run):
    result = _run(complete_run)
    assert result.returncode == 0, result.stdout
    assert "Safe to stop" in result.stdout


def test_every_small_artefact_appears_in_the_git_add_line(complete_run):
    """Because the point is to be pasted, not read and retyped."""
    out = _run(complete_run).stdout
    add = out.split("git add")[1].split("git commit")[0]
    for name in ("MODEL_CARD.md", "report.json", "calibration.json",
                 "labels.json", "predictions.npz", "predictions-val.npz",
                 "config.yaml",
                 "history.json", "splits.csv.gz"):
        assert name in add, f"{name} is not in the command to paste"


def test_a_missing_artefact_refuses_and_says_not_to_stop_the_pod():
    result = _run("ml/runs/_does_not_exist")
    assert result.returncode == 1
    assert "DO NOT STOP THE POD YET" in result.stdout


def test_the_irrecoverable_ones_are_marked_as_such():
    """calibration.json and splits.csv.gz are the two that cannot be made
    again from what survives a destroyed pod. Saying "rebuildable: no" where
    it is actually "no, ever" is the difference between a shrug and a stop."""
    out = _run("ml/runs/_does_not_exist").stdout

    def reason(artefact: str) -> str:
        """The two indented lines the refusal prints under an artefact.

        Sliced by line rather than split on `"- "`, which also occurs inside
        the reason itself ("NO -- needs the val images") and silently cut
        the assertion's evidence off before the part being asserted.
        """
        lines = out.splitlines()
        i = max(n for n, line in enumerate(lines) if artefact in line)
        return "\n".join(lines[i + 1:i + 3])

    calibration = reason("calibration.json")
    assert "NO" in calibration and "val images" in calibration, calibration
    assert "NO" in reason("splits.csv.gz")


def test_the_large_files_are_listed_but_never_offered_to_git(complete_run):
    """A 350 MB checkpoint in a `git add` line is a wasted ten minutes and
    a rejected push."""
    out = _run(complete_run).stdout
    add = out.split("git add")[1].split("git commit")[0]
    for name in ("model.onnx", "best.pt", "manifest.parquet"):
        assert name not in add
        assert name in out, f"{name} must still be named for transfer"


def test_it_catches_an_artefact_git_would_silently_decline(complete_run):
    """The failure that has bitten this project three times: a rule ending
    in `/` kills every negation under it and `git add` exits 0 having added
    nothing. The check must read git's own answer, not a list of paths."""
    out = _run(complete_run).stdout
    assert "IGNORED" not in out, (
        "an artefact the run-book commits is currently gitignored"
    )
    assert "check-ignore" in SCRIPT.read_text(encoding="utf-8") or True
    source = SCRIPT.read_text(encoding="utf-8")
    assert "check-ignore" in source, (
        "the check must ask git, not compare against a hardcoded list"
    )
