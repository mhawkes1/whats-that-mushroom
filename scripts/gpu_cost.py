#!/usr/bin/env python3
"""What the training run costs, with the guesses labelled as guesses.

    python scripts/gpu_cost.py
    python scripts/gpu_cost.py --img-per-sec 118    # after step 4 measures it

Everything here is arithmetic over two kinds of input: numbers read out of
`ml/configs/default.yaml` and the run-book, and numbers nobody has measured
yet. The second kind is the reason this is a script rather than a sentence
in a document -- step 4 of the run-book times one epoch precisely so the
guess can be replaced, and when it is, re-run this with `--img-per-sec` and
the whole estimate moves with it.

The dominant uncertainty is throughput, and it is not close: the GPU hours
are roughly linear in it and everything else is rounding. A measured number
turns a factor-of-two range into a figure.

Deliberately NOT included, because none of them is a GPU cost and pretending
otherwise makes the number look respectable while being wrong: a mycologist's
time, legal review, the Apple and Google developer programmes, or any of the
four release blockers in `docs/SAFETY.md` that code cannot close.
"""

from __future__ import annotations

import argparse

# --- Measured or decided ----------------------------------------------------
N_IMAGES = 93_000          # run-book, step 3: ~93,000 across 244 species
EPOCHS = 30                # ml/configs/default.yaml, train.epochs
VAL_FRACTION = 0.10        # fungi_ml.data.prepare default
TEST_FRACTION = 0.10

# --- Priced 2026-10-27, and prices move -------------------------------------
#
# 0.34 was the Community Cloud rate for a 4090 that every pricing roundup
# quoted. Martin's actual pod billed **0.90**, on EUR-IS-2 -- a different
# tier or region, nearly three times the figure this script was telling him.
# The default is now what was really charged rather than what was
# advertised, because a cost estimate that is cheaper than the bill is
# worse than no estimate: it is the one people act on.
#
# Check the hourly rate on the pod card BEFORE deploying and pass
# --usd-per-hour if it differs.
USD_PER_HOUR = 0.90        # RunPod, RTX 4090, as actually billed 2026-10-27
USD_PER_GB_MONTH = 0.07    # network volume
VOLUME_GB = 60
USD_PER_GBP = 1.27

# --- Assumed, and this is the one that matters ------------------------------
# ViT-B/16 at 384 px is 577 tokens a pass and about 55 GFLOPs forward, so
# roughly 166 GFLOPs per image to train. Published 4090 figures for this
# model and resolution with AMP sit around 100-180 img/s. Nobody has run it.
# MEASURED on the first real run: 354 s an epoch over 74,837 training
# images plus validation, which is about 210 img/s. The 100-180 guess
# below is kept only as the range the estimate spanned before anyone had
# run it.
IMG_PER_SEC_LOW, IMG_PER_SEC_MID, IMG_PER_SEC_HIGH = 100.0, 210.0, 240.0

# Inference is roughly a third of the work of a training step.
INFERENCE_SPEEDUP = 3.0


def train_hours(img_per_sec: float) -> float:
    """One full run: every epoch over train, plus validation each epoch."""
    train_n = N_IMAGES * (1 - VAL_FRACTION - TEST_FRACTION)
    val_n = N_IMAGES * VAL_FRACTION
    per_epoch = train_n / img_per_sec + val_n / (img_per_sec * INFERENCE_SPEEDUP)
    return per_epoch * EPOCHS / 3600


def phases(img_per_sec: float) -> list[tuple[str, float, str]]:
    test_n = N_IMAGES * TEST_FRACTION
    val_n = N_IMAGES * VAL_FRACTION
    inf = img_per_sec * INFERENCE_SPEEDUP
    return [
        ("Pod start, pip install ml/requirements", 0.25, "onnxscript included"),
        ("Resolve names to GBIF keys", 0.03, "--resolve-only, read the output"),
        ("Download and prepare the dataset", 2.50, "network-bound, not GPU"),
        ("Time one epoch (step 4)", train_hours(img_per_sec) / EPOCHS,
         "the step people skip"),
        ("Train 30 epochs", train_hours(img_per_sec), "the only real GPU cost"),
        ("Calibrate + fit the energy threshold", val_n / inf / 3600,
         "on val, never test"),
        ("Export to ONNX and verify", 0.08, "do NOT skip to save money"),
        ("Model card on the test split", test_n / inf / 3600, "held-out"),
        ("runpodctl send ~700 MB", 0.25, "best.pt + model.onnx"),
    ]


def money(hours: float) -> tuple[float, float]:
    usd = hours * USD_PER_HOUR
    return usd, usd / USD_PER_GBP


def rule(ch: str = "-", n: int = 72) -> None:
    print(ch * n)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--img-per-sec", type=float, default=None,
                    help="measured training throughput; replaces the guess")
    ap.add_argument("--runs", type=int, default=4,
                    help="how many attempts before a keeper (run-book says 3-4)")
    ap.add_argument("--days-held", type=float, default=3.0,
                    help="days the volume exists before you terminate")
    ap.add_argument("--usd-per-hour", type=float, default=USD_PER_HOUR)
    args = ap.parse_args()

    measured = args.img_per_sec is not None
    mid = args.img_per_sec if measured else IMG_PER_SEC_MID

    print()
    print("  ONE COMPLETE RUN, start to finish")
    print(f"  {N_IMAGES:,} images  |  {EPOCHS} epochs  |  "
          f"{'measured' if measured else 'ASSUMED'} {mid:.0f} img/s")
    rule()
    total = 0.0
    for name, hours, note in phases(mid):
        total += hours
        print(f"  {name:<40}{hours:>6.2f} h   {note}")
    rule()
    usd, gbp = money(total)
    print(f"  {'':<40}{total:>6.2f} h   ${usd:,.2f}  /  £{gbp:,.2f}")

    if not measured:
        print()
        print("  The same run across the plausible throughput range")
        rule()
        for label, ips in (("slow", IMG_PER_SEC_LOW), ("mid", IMG_PER_SEC_MID),
                           ("fast", IMG_PER_SEC_HIGH)):
            t = sum(h for _, h, _ in phases(ips))
            u, g = money(t)
            print(f"  {label:<10}{ips:>6.0f} img/s   {t:>6.2f} h   "
                  f"${u:>6.2f}   £{g:>6.2f}")
        print()
        print("  Throughput is the whole uncertainty. Step 4 of the run-book")
        print("  measures it in one epoch; re-run with --img-per-sec then.")

    # --- The exercise, not the run ---------------------------------------
    # Attempt one dies early; attempt two gets further; the dataset is on the
    # volume by then, so later attempts skip the download.
    print()
    print(f"  THE WHOLE EXERCISE  ({args.runs} attempts before a keeper)")
    rule()
    one = sum(h for _, h, _ in phases(mid))
    download = next(h for n, h, _ in phases(mid) if n.startswith("Download"))
    setup = next(h for n, h, _ in phases(mid) if n.startswith("Pod start"))

    attempts = []
    for i in range(args.runs):
        if i == 0:
            # Dies on a config detail an hour in; the download still happened.
            h = setup + download + 1.0
            why = "dies early; dataset now on the volume"
        elif i == args.runs - 1:
            h = one - download
            why = "the keeper"
        else:
            h = one - download
            why = "reveals something; dataset reused"
        attempts.append((f"attempt {i + 1}", h, why))
    gpu_hours = 0.0
    for name, h, why in attempts:
        gpu_hours += h
        print(f"  {name:<40}{h:>6.2f} h   {why}")

    storage_gb_months = VOLUME_GB * args.days_held / 30
    storage_usd = storage_gb_months * USD_PER_GB_MONTH
    gpu_usd = gpu_hours * args.usd_per_hour
    rule()
    print(f"  {'GPU time':<40}{gpu_hours:>6.2f} h   ${gpu_usd:,.2f}")
    print(f"  {'Volume, ' + f'{VOLUME_GB} GB for {args.days_held:g} days':<40}"
          f"{'':>6}     ${storage_usd:,.2f}")
    rule("=")
    tot_usd = gpu_usd + storage_usd
    print(f"  {'TOTAL':<40}{'':>6}     ${tot_usd:,.2f}  /  "
          f"£{tot_usd / USD_PER_GBP:,.2f}")
    print()
    print(f"  Add credit in round numbers: $25 covers this about "
          f"{25 / tot_usd:.0f}x over.")
    print()
    print("  If Community has no 4090 free, Secure Cloud is about double:")
    su = gpu_hours * 0.69 + storage_usd
    print(f"  ${su:,.2f} / £{su / USD_PER_GBP:,.2f}. Still not the thing to")
    print("  optimise -- a host that dies three hours in costs more than the")
    print("  difference, which is why the run-book says Community but not")
    print("  the marketplaces.")
    print()
    print("  NOT included, because none of it is GPU time: mycological")
    print("  review, legal review, Apple ($99/yr) and Google ($25 once).")
    print("  Those are the release blockers; this is the cheap part.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
