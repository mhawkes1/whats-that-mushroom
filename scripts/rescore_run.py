#!/usr/bin/env python3
"""Re-score a finished run against a changed safety threshold.

    python scripts/rescore_run.py --run ml/runs/run4-b32

**Why this exists.** The deadly-mass trigger moved from 2% to 1% on
2026-10-29. Every figure in a model card that depends on it -- the silent
confusion count above all -- was computed against the old line, and a card
reporting silence against a threshold the app no longer uses is the exact
failure `ml/tests/test_evaluate.py` greps `safety.py` to prevent, arriving
by a different road: not drift between two copies of the constant, but
drift between the constant and the evidence already written down.

**It needs no GPU, no dataset and no pod**, because `predictions.npz`
holds the calibrated probabilities for the whole split. That is what
committing it was for, and this is the second question it has answered
that could not otherwise have been asked at all.

**It recomputes only what the threshold decides.** Accuracy, risk-weighted
error, deadly recall and the coverage curve are untouched: they do not
depend on where the warning fires. The report records that it was
rescored, and from what, so a reviewer can tell a recomputed figure from a
measured one.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--run", required=True, help="a run directory under ml/runs")
    ap.add_argument("--taxonomy", default=str(ROOT / "data" / "taxonomy.seed.json"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    import numpy as np

    from fungi_ml.evaluate import (
        DEADLY_MASS_THRESHOLD,
        dangerous_confusions,
        write_model_card,
    )
    from fungi_ml.taxonomy import Taxonomy

    run = Path(args.run)
    preds, report_path = run / "predictions.npz", run / "report.json"
    for required in (preds, report_path):
        if not required.exists():
            print(f"No {required}.", file=sys.stderr)
            return 2

    report = json.loads(report_path.read_text(encoding="utf-8"))
    was = report.get("deadly_mass_threshold")
    if was == DEADLY_MASS_THRESHOLD:
        print(f"  {run.name} is already scored at "
              f"{DEADLY_MASS_THRESHOLD:.0%}; nothing to do.\n")
        return 0

    blob = np.load(preds, allow_pickle=False)
    taxonomy = Taxonomy.load(args.taxonomy)
    rows = dangerous_confusions(
        blob["probs"].astype(np.float32),
        blob["labels"],
        [str(c) for c in blob["classes"]],
        taxonomy,
    )
    n = int(len(blob["labels"]))
    silent = sum(r["silent"] for r in rows)

    print(f"\n  {run.name}: {was:.0%} -> {DEADLY_MASS_THRESHOLD:.0%}\n")
    print(f"  dangerous confusions  {report.get('dangerous_confusion_count')} "
          f"-> {len(rows)}")
    print(f"  of which SILENT       "
          f"{report.get('silent_dangerous_confusion_count')} -> {silent}")
    print()

    if args.dry_run:
        print("  --dry-run: nothing written.\n")
        return 0

    report["dangerous_confusions"] = rows
    report["dangerous_confusion_count"] = len(rows)
    report["dangerous_confusion_rate"] = len(rows) / n
    report["silent_dangerous_confusion_count"] = silent
    report["silent_dangerous_confusion_rate"] = silent / n
    report["deadly_mass_threshold"] = DEADLY_MASS_THRESHOLD
    # Provenance, so a recomputed figure is never mistaken for a measured
    # one. Appended rather than overwritten: the log is evidence, and that
    # applies to a model card as much as to an incident.
    report.setdefault("rescored", []).append(
        {"on": date.today().isoformat(),
         "deadly_mass_threshold": {"from": was, "to": DEADLY_MASS_THRESHOLD},
         "from_file": preds.name}
    )
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    calibration = None
    cal_path = run / "calibration.json"
    if cal_path.exists():
        calibration = json.loads(cal_path.read_text(encoding="utf-8"))
    write_model_card(report, calibration, run / "MODEL_CARD.md")

    def shown(path: Path) -> str:
        """`--run` may be relative or absolute; neither must crash the
        last line after the files are already written."""
        try:
            return str(path.resolve().relative_to(ROOT))
        except ValueError:
            return str(path)

    print(f"  Rewrote {shown(report_path)} and {shown(run / 'MODEL_CARD.md')}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
