#!/usr/bin/env python3
"""The last thing you run on a GPU pod, before you stop it.

    python scripts/finish_run.py

A training run produces about seven small files and three large ones. The
small ones are the evidence for the release decision and belong in git; the
large ones have to be transferred off the box by hand. Until now that was a
list in the run-book's step 9, which means it depended on somebody reading
it at the end of a long day, on a machine billing by the hour, with the
interesting part already finished.

On the first real run it did not survive that. `calibration.json` was never
taken, and it **cannot be reconstructed** -- temperature scaling is fitted
on the validation split, so recovering it needs the images and the
checkpoint, and both were destroyed with the pod. `labels.json` went the
same way and was only recoverable by luck, because all 244 species happened
to clear the image-count filter.

So this script replaces the list with a check. It reports every artefact as
present or missing, says which of the small ones git would silently refuse
to add, and **exits non-zero while anything is missing** -- because the
moment to discover that is while the pod is still running, not the next
morning.

It changes nothing. It prints the commands.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (path relative to the repo root, why it matters, can it be rebuilt?)
SMALL = [
    ("{run}/MODEL_CARD.md", "the release decision, in prose", "yes, from report.json"),
    ("{run}/report.json", "every metric, including the silent count", "no"),
    ("{run}/calibration.json", "temperature, thresholds, energy cutoff",
     "NO -- needs the val images and the checkpoint"),
    ("{run}/labels.json", "which output index is which species",
     "only if no species was filtered out"),
    ("{run}/predictions.npz", "the calibrated test-set predictions", "no"),
    ("{run}/predictions-val.npz",
     "the same on VALIDATION -- what a safety threshold may be tuned on",
     "no"),
    ("{run}/config.yaml", "what was actually run", "yes, if unchanged"),
    ("{run}/history.json", "the per-epoch curve behind rule 6", "no"),
    ("data/processed/splits.csv.gz", "which image went to which split", "NO"),
]

LARGE = [
    ("{run}/model.onnx", "~350 MB", "what the server loads"),
    ("{run}/best.pt", "~350 MB", "resume or re-export from this"),
    ("data/processed/manifest.parquet", "~20 MB",
     "the full index; never committable, still worth taking"),
]


def ignored(path: Path) -> bool:
    """Whether git would silently decline to add this."""
    try:
        return subprocess.run(
            ["git", "check-ignore", str(path.relative_to(ROOT))],
            cwd=ROOT, capture_output=True, text=True,
        ).returncode == 0
    except (OSError, ValueError):
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", default="ml/runs/baseline",
                    help="relative to the repo root")
    args = ap.parse_args()
    run = args.run_dir.rstrip("/")

    print()
    print("  SMALL -- these go in git. The run-book's step 9.")
    print("  " + "-" * 70)
    missing, unaddable, present = [], [], []
    for template, why, rebuildable in SMALL:
        rel = template.format(run=run)
        path = ROOT / rel
        if not path.exists():
            missing.append((rel, why, rebuildable))
            print(f"   MISSING  {rel:<42} {why}")
            continue
        if ignored(path):
            unaddable.append(rel)
            print(f"   IGNORED  {rel:<42} git would add nothing")
            continue
        present.append(rel)
        size = path.stat().st_size
        unit = f"{size / 1e6:.1f} MB" if size > 1e6 else f"{size / 1e3:.0f} KB"
        print(f"   ok       {rel:<42} {unit}")

    print()
    print("  LARGE -- transfer these off the box; git will refuse them.")
    print("  " + "-" * 70)
    for template, size, why in LARGE:
        rel = template.format(run=run)
        mark = "ok      " if (ROOT / rel).exists() else "MISSING "
        print(f"   {mark} {rel:<42} {size:<9} {why}")

    if present:
        print()
        print("  Commit what is here:")
        print()
        print("    git add " + " \\\n            ".join(present))
        print('    git commit -m "Run: <top-1>, <n> dangerous, <n> silent"')
        print("    git push")

    print()
    print("  Take the large ones (runpodctl prints a code; run")
    print("  `runpodctl receive <code>` on your own machine):")
    print()
    for template, _, _ in LARGE:
        rel = template.format(run=run)
        if (ROOT / rel).exists():
            print(f"    runpodctl send {rel}")

    if unaddable:
        print()
        print("  REFUSING: git is ignoring files the run-book says to commit:")
        for rel in unaddable:
            print(f"    - {rel}")
        print("  A rule ending in `/` makes every negation under it dead, and")
        print("  `git add` then exits 0 having added nothing. Fix .gitignore.")

    if missing:
        print()
        print("  REFUSING: artefacts are missing.")
        for rel, why, rebuildable in missing:
            print(f"    - {rel}")
            print(f"        {why}")
            print(f"        rebuildable later: {rebuildable}")
        print()
        print("  DO NOT STOP THE POD YET. A stopped pod with no volume disk")
        print("  loses everything, and the ones marked NO above cannot be")
        print("  made again from what survives -- they need the images and")
        print("  the checkpoint, which go with it.")

    print()
    if missing or unaddable:
        return 1
    print("  Everything is here and git will take all of it. Safe to stop.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
