# GPU run-book

Everything to do on a rented box, in order, with the decision points marked.
Written to be followed while a meter runs, so it is commands first and
explanation second.

`docs/ROADMAP.md` is the why; this is the what-to-type.

---

## Before you rent anything

These cost nothing and save money. Run them **in a checkout with the ML
dependencies installed** — `pip install -r ml/requirements.txt` — because a
bare container has none of them and both commands will simply fail to import.

```bash
python -m pytest ml/tests server/tests -q     # expect 345 passing
python scripts/smoke_e2e.py                   # ~1 min, no GPU, no network
```

`smoke_e2e.py` runs the whole chain — prepare → train → calibrate → export →
serve — on synthetic noise. It exists to catch the failures that only appear
at the *end* of a paid run: a config key the trainer writes and the exporter
cannot read, a tensor shape that only bites at export. **If it fails, do not
rent a GPU.**

Decide one thing before you start: **are you training on everything, or
non-commercial-free?** The answer is everything — dropping NC-licensed images
takes *Cortinarius orellanus* to 5 images and *Lepiota brunneoincarnata* to
15, both below the 40-image floor, so both leave the label space. Two DEADLY
species the model then cannot name. That is a safety regression, not a
quality trade. See `BRIEF`-level detail in the session notes; the short
version is: train on everything, settle the commercial question separately
with a lawyer.

---

## 1. Rent

**RunPod Community Cloud, RTX 4090, ~$0.34/hr.** Not Vast.ai for the first
run — the marketplace floor is lower and a host that dies three hours in
costs more than the 20p it saved. Lambda does not offer the 4090.

Ask for **≥ 60 GB disk**. The dataset is about 16 GB of images, plus the
manifest, plus checkpoints.

Budget **£50 for the whole exercise**, not £5. You will do three or four
runs: one that dies on a config detail, one that reveals a data problem, one
that is real, one that is the keeper. At these prices that is still trivial,
and treating it as trivial is what stops you shipping run one because you
begrudged a second.

---

## 2. Set the box up

```bash
git clone <this repo> wtm && cd wtm
pip install -r ml/requirements.txt
python -c "import torch; print(torch.cuda.get_device_name(0))"
```

If that last line does not print a GPU, stop and fix it before anything else.

`onnxscript` is in that requirements file and is **not** optional: since
torch 2.9 the default ONNX exporter imports it, and without it
`fungi_ml.export` dies on `ModuleNotFoundError` — at the very end of the
pipeline, after the whole training run has been paid for.

---

## 3. Build the dataset **on the box**

The images are not in git and never will be. Rebuild them here rather than
uploading 16 GB.

```bash
# Resolve names to GBIF keys first. One minute, and it is the point at
# which a name silently becomes the wrong fungus.
python scripts/build_dataset.py --resolve-only
```

**Read `data/gbif-keys.json` before continuing.** Every match and every
refusal, with reasons. A refusal on a DEADLY species stops the build, which
is correct — a species the model cannot name is one the app cannot warn
about.

```bash
python scripts/build_dataset.py --target 400 --min-images 40
```

- **Never pass `--country GB`.** It is the intuitive choice for a British app
  and it wrecks the dataset: zero images for three DEADLY/SERIOUS species.
- Expect roughly **93,000 images across 244 species** and a couple of hours.
- It is network-bound, not GPU-bound. If you want to be frugal, build it on a
  cheap CPU box first and snapshot the volume — though at $0.34/hr two idle
  hours cost 70p, so this is optional tidiness rather than real saving.

That one command does the splits too — it calls `fungi_ml.data.prepare`
itself and writes `data/processed/`. There is no second step, and running
`prepare` again by hand just redoes work.

Read the summary it prints. It names any species that cleared `--min-images`
on photographs of only a few fruiting bodies; those clear the bar on paper
and their validation scores say almost nothing.

Splits are on `observation_id`, never on image. **If accuracy later looks too
good, check this before believing it.**

---

## 4. Time one epoch before you commit to thirty

```bash
cd ml
python - <<'PY'
import yaml, pathlib
c = yaml.safe_load(open("configs/default.yaml"))
c["train"]["epochs"] = 1
c["output"]["dir"] = "runs/timing"
pathlib.Path("configs/timing.yaml").write_text(yaml.safe_dump(c))
PY
time python -m fungi_ml.train --config configs/timing.yaml
```

**This is the step people skip and should not.** My estimate is ~4.5 hours for
30 epochs on a 4090, from an assumed ~140 img/s for ViT-B/16 at 384 px — that
is an *estimate, not a measurement*. One epoch tells you the real number.
Multiply by 30. If it comes out at twelve hours rather than four, you want to
know now, while you can still drop to `convnext_base` or a smaller
`image_size`.

---

## 5. Train

```bash
python -m fungi_ml.train --config configs/default.yaml
```

Writes `runs/baseline/best.pt`, selected on **validation risk**, never
accuracy — rule 6. `risk_strength` is in the config now and is what makes
this different from an ordinary classifier; `0` turns it into one.

Expect **50–70% top-1 at best**, with genus accuracy notably higher, and the
lower end is likelier at 244 species. **95% means a leak** — go and check the
split.

---

## 6. Calibrate, and fit the out-of-scope threshold

```bash
python -m fungi_ml.calibrate \
    --checkpoint runs/baseline/best.pt \
    --manifest ../data/processed/manifest.parquet \
    --split val \
    --out runs/baseline/calibration.json
```

`--split val`, not `test`. Fitting temperature on data the model trained on
gives a temperature near 1.0 and a model that stays overconfident. The energy
threshold for "that isn't something I know" is fitted here too, on the **raw**
logits — before temperature, before softmax — or the signal is gone.

---

## 7. Export **before you release the rental**

```bash
python -m fungi_ml.export \
    --checkpoint runs/baseline/best.pt \
    --out runs/baseline/model.onnx \
    --opset 17
```

**Do not skip this to save money.** A checkpoint that will not export is a
checkpoint you retrain, and finding that out after you have released the box
costs the whole run again. Export verifies numerically against the PyTorch
model and refuses on a mismatch.

---

## 8. The model card

```bash
cd ..
python scripts/make_model_card.py \
    --checkpoint ml/runs/baseline/best.pt \
    --manifest data/processed/manifest.parquet \
    --calibration ml/runs/baseline/calibration.json \
    --split test \
    --out ml/runs/baseline/MODEL_CARD.md \
    --report-out ml/runs/baseline/report.json
```

`--split test`: the held-out set, which calibration never touched.

**It exits non-zero if there is a single dangerous confusion**, because
`docs/SAFETY.md` asks for zero or a documented, bounded exception. The card is
written either way — read it before deciding anything. A non-zero exit is the
script declining to let a bad run pass quietly, not a verdict on the model.

---

## 9. Take these home, then stop the box

```
ml/runs/baseline/best.pt            # the checkpoint
ml/runs/baseline/model.onnx         # what the server loads
ml/runs/baseline/labels.json
ml/runs/baseline/calibration.json
ml/runs/baseline/MODEL_CARD.md
ml/runs/baseline/report.json
data/processed/manifest.parquet     # ~20 MB, reproduces every split
```

The images do not need to come home. The manifest records every URL, licence
and rights holder, so the dataset is rebuildable.

---

## 10. Back here: serve it

```bash
cd server && uvicorn app.main:app --reload
curl -s localhost:8000/health
```

`model_loaded` and `calibrated` should both flip to `true`. **That changes
the disclaimer's hash and re-asks every user for consent** — which is correct
and by design: two of the things they previously agreed to have stopped being
true.

Then run the app against a real classifier for the first time. The stub has
been hiding things; rendering the client for the first time found three fatal
bugs, and a real model will do the same to the safety layer.

---

## What closes, and what does not

Four blockers in `docs/SAFETY.md` close with this run: model card published,
zero dangerous confusions, calibration fitted, and the OOD threshold fitted on
real logits.

Four do not, and none of them is code:

- **Qualified mycological review** of the taxonomy
- **Legal review** of the disclaimer and terms
- **A named person** on the incident rota
- **A retention period** for the incident log, which waits on the legal review

Worth holding in mind while training: the toxicity gradings feed the
**training loss**, not just the display. An upgrade into DEADLY or SERIOUS
after a run means the model was optimised against the wrong costs. That is not
a reason to wait — it is a reason to make sure the *final* run happens after
the review lands.
