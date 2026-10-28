#!/usr/bin/env python3
"""Rebuild a lost `labels.json`, but only when it can be PROVEN correct.

    python scripts/recover_labels.py

`labels.json` maps the model's output index to a species key, and it belongs
to the checkpoint that produced it. `server/app/main.py` deliberately refuses
to start without it rather than deriving the order from the taxonomy,
because that derivation is only right while no species was filtered out of
the training set -- and when it is wrong, every prediction after the first
gap is given its neighbour's name, silently, with a DEADLY species possibly
served under a harmless one.

This script does **not** relax that rule. It performs the same derivation,
and then checks it:

    `fungi_ml.data.prepare.build_label_map` orders classes as
    `sorted(species_key for species that survived --min-images)`.

    So the derived order is correct **if and only if** no species was
    filtered out -- and the model itself says how many classes it has. If
    the ONNX graph's output width equals the number of species in the
    taxonomy, then nothing was dropped, the two sorted lists are the same
    list, and the mapping is recovered rather than guessed.

    If the widths differ, species WERE dropped, the script cannot know
    which, and it refuses. There is no "probably fine" branch.

Written 2026-10-28, when the first trained model reached a laptop without
its `labels.json`: the pod that held the original had been destroyed, and
the file had never been committed. The run it recovers is the 244-class
one, where all 244 species cleared the filter -- the coincidence that makes
this provable at all, and the coincidence that will not hold on a run with
a stricter `--min-images`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = ROOT / "ml" / "runs" / "baseline" / "model.onnx"
DEFAULT_OUT = ROOT / "ml" / "runs" / "baseline" / "labels.json"
DEFAULT_TAXONOMY = ROOT / "data" / "taxonomy.seed.json"


def model_width(model_path: Path) -> int:
    """How many classes the graph actually predicts over."""
    try:
        import onnxruntime as ort
    except ImportError:
        raise SystemExit(
            "onnxruntime is not installed. Run scripts/try_it.py once first "
            "-- it installs the server's dependencies, which include it."
        )

    session = ort.InferenceSession(
        str(model_path), providers=["CPUExecutionProvider"]
    )
    shape = session.get_outputs()[0].shape
    last = shape[-1] if shape else None
    if not isinstance(last, int):
        raise SystemExit(
            f"The model's output shape is {shape}, whose last dimension is "
            f"not a fixed number. Without it there is nothing to check the "
            f"derived order against, so this cannot be recovered safely."
        )
    return last


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=str(DEFAULT_MODEL))
    ap.add_argument("--taxonomy", default=str(DEFAULT_TAXONOMY))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    model_path = Path(args.model)
    out_path = Path(args.out)

    if not model_path.exists():
        print(f"No model at {model_path}", file=sys.stderr)
        return 2
    if out_path.exists():
        print(f"{out_path} already exists. Refusing to overwrite the real "
              f"thing with a derivation.", file=sys.stderr)
        return 2

    keys = sorted(
        s["key"] for s in
        json.loads(Path(args.taxonomy).read_text(encoding="utf-8"))["species"]
    )
    width = model_width(model_path)

    print()
    print(f"  model predicts over      {width} classes")
    print(f"  taxonomy holds           {len(keys)} species")
    print()

    if width != len(keys):
        dropped = len(keys) - width
        print(
            f"  REFUSING.\n\n"
            f"  The model has {width} classes and the taxonomy has "
            f"{len(keys)}, so {abs(dropped)} species "
            f"{'were filtered out of' if dropped > 0 else 'are missing from'} "
            f"the training set. Which ones is not recorded anywhere this\n"
            f"  script can read, and guessing would shift every name after\n"
            f"  the first gap onto its neighbour -- which is how a deadly\n"
            f"  species gets served under a harmless one.\n\n"
            f"  The real labels.json is the only answer. It is written next\n"
            f"  to the checkpoint by the training run.",
            file=sys.stderr,
        )
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"label_map": {k: i for i, k in enumerate(keys)},
                    "classes": keys}, indent=2),
        encoding="utf-8",
    )
    print(f"  The widths match, so no species was filtered out and the")
    print(f"  checkpoint's order IS sorted(taxonomy keys). Recovered.")
    print()
    print(f"  Wrote {out_path}")
    print(f"  index 0   = {keys[0]}")
    print(f"  index {len(keys) - 1} = {keys[-1]}")
    print()
    print("  This is a reconstruction, not the original. Commit the real")
    print("  labels.json from the next training run and delete this one.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
