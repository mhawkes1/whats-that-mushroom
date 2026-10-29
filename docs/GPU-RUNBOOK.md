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

**RunPod, RTX 4090.** Not Vast.ai for the first run — the marketplace floor
is lower and a host that dies three hours in costs more than the 20p it
saved. Lambda does not offer the 4090, and Nebius does not rent anything
smaller than an L40S, which is four times the price for a card this job does
not need.

**Read the hourly rate off the pod card before you deploy.** Every pricing
roundup quotes the Community floor of about $0.34; the first real run, on
EUR-IS-2, billed **$0.90/hr** — a different tier or region, and nearly three
times it. The figures below use what was actually billed, because an
estimate that comes in under the bill is worse than no estimate: it is the
one people act on. Pass `--usd-per-hour` to `scripts/gpu_cost.py` if yours
differs.

### What it costs

Measured on the first real run, 2026-10-27: **354 s per epoch**, which is
about 210 img/s, not the 140 assumed before anyone had run one.

| | Hours | At $0.90/hr |
| --- | --- | --- |
| Dataset download (network-bound, **no GPU needed**) | ~2–3 | $1.80–2.70 |
| Training, 10 epochs | ~1.0 | $0.90 |
| Calibrate, export, model card | ~0.3 | $0.27 |
| **One complete run on one GPU pod** | **~3.5** | **~$3.15 · £2.50** |

**The download now costs more than the training, and that inverts the old
advice.** Thirty epochs took three hours; ten is the right number (see
`docs/runs/` — risk was minimised around epochs 5–8 and got steadily worse
after), so training is down to about an hour while the download has not
moved. Paying 4090 rates to sit and make HTTP requests is the largest
avoidable cost in the exercise — see the note under step 5 about building it
on a cheap CPU pod against a network volume.

Budget **$25 of credit** anyway. It covers several attempts, and budgeting
tightly is how people end up not running a second attempt because they
begrudged the first. You will do three or four: one that dies on a config
detail, one that reveals a data problem, one that is real, one that is the
keeper.

**Add $25 of credit.** It covers the exercise three times over. Budgeting
tightly is how people end up not running a second attempt because they
begrudged the first, and you will do three or four: one that dies on a
config detail, one that reveals a data problem, one that is real, one that
is the keeper.

If Community has no 4090 free, Secure Cloud is roughly double — about $14
for the whole exercise. Take it rather than wait. A host that dies three
hours in costs more than the difference.

**None of the expensive things are on this list**, because none of them is
GPU time: mycological review, legal review, Apple's $99/year and Google's
$25 one-off. The compute is the cheap part of shipping this, by a long way.

### What to put in the form

RunPod moves its labels around, so these are the values that matter rather
than a click-by-click that will be wrong by spring.

| Field | Value | Why |
| --- | --- | --- |
| Cloud type | **Community** | Half the price of Secure. Fine for a job you can restart |
| GPU | **RTX 4090**, 1× | 24 GB, which is what `configs/default.yaml` targets |
| Template | **RunPod PyTorch 2.x** (CUDA 12.x) | Saves installing torch. Any recent PyTorch image works |
| Container disk | **30 GB** | Code, wheels, checkpoints |
| Volume disk | **60 GB**, mounted at `/workspace` | The dataset is ~16 GB of images; this is the part that survives a restart, so **work in `/workspace`** |
| Region | Any | Unless you are attaching a network volume, which pins you to its data centre |

Then **Deploy**, wait for the pod to go green, and use **Connect → Web
Terminal** (or SSH, if you have added a key).

Add about $10 of credit. You will not spend it.

### Getting the code onto the box

This is the step that stops people, because the repo is private and `git
clone` will simply fail.

On GitHub: **Settings → Developer settings → Personal access tokens → Fine-grained
tokens**. Scope it to `whats-that-mushroom` only, give it an expiry of a
week, and grant **Contents: read and write**.

Read-only is the tidier instinct and it is the wrong call here. You will
almost certainly change `configs/default.yaml` on the box — the timing check
in step 4 exists precisely so you can — and a change you cannot push is a
change that dies with the pod. One repo, one week, one permission is a
reasonable trade for not losing the fix.

Then on the pod:

```bash
cd /workspace
git clone https://<TOKEN>@github.com/mhawkes1/whats-that-mushroom.git wtm
cd wtm && git checkout claude/mushroom-app-continue-fy5f4m
```

The token ends up in `.git/config` on the pod. That is acceptable only
because the pod is disposable — **terminate it when you are done, do not just
stop it**, and let the token expire.

---

## 2. Set the box up

```bash
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
- Expect roughly **93,000 images across 244 species**, about 16 GB, and a
  couple of hours.
- **It is network-bound, not GPU-bound, and at the real billed rate that is
  worth acting on.** This note used to say building it on a cheap CPU box
  was "optional tidiness rather than real saving", on the strength of
  $0.34/hr making two idle hours cost 70p. At the $0.90/hr actually billed,
  two or three hours of a 4090 waiting on HTTP is **$1.80–2.70 — more than
  the whole 10-epoch training run.** Build it on a CPU pod against a RunPod
  **network volume**, then attach that same volume to the GPU pod and train.
  The GPU is then rented only for the hour it is used. A network volume pins
  you to its data centre, which is the one constraint it adds.
- **If the pod has no volume disk, everything here dies when you stop it.**
  Not just on terminate — RunPod warns "all data will be lost" on a plain
  stop, because without the 60 GB mounted at `/workspace` from step 1 that
  path is ordinary container disk. There is then no cheap pause: keep paying
  the full hourly rate, or lose the 16 GB. That happened on the first run.

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
    --report-out ml/runs/baseline/report.json \
    --probs-out ml/runs/baseline/predictions.npz
```

Then **run it again on validation**, for the predictions alone:

```bash
python scripts/make_model_card.py \
    --checkpoint ml/runs/baseline/best.pt \
    --manifest data/processed/manifest.parquet \
    --calibration ml/runs/baseline/calibration.json \
    --split val \
    --out /dev/null \
    --report-out /dev/null \
    --probs-out ml/runs/baseline/predictions-val.npz
```

`--split test`: the held-out set, which calibration never touched.

**Why the second run exists.** A safety threshold tuned on the split that
gates release is fitted to its own gate -- the same error as selecting a
checkpoint on the data you then report. The deadly-mass trigger moved from
2% to 1% on 2026-10-29 under a rule stated in advance (the highest
threshold at which no genuinely deadly mushroom is shown with no hazard at
all), and the only evidence available for where that rule lands was the
test split, because run four wrote test predictions only. The claim the
test split *can* support without circularity is the weaker one that 2% was
too high. Confirming the figure needs this file, and it costs one extra
inference pass over images that are already on the box.

**`--probs-out` is not optional in practice.** It writes the calibrated
predictions as float16 — about 4 MB for 9,000 test images across 244 species
— and it is the difference between a run you can still interrogate and one
you can only quote. The first run omitted it, and a fortnight later the
obvious question (what would the app actually have *shown* for the worst
dangerous confusion?) was unanswerable: the number that decides had been
computed during evaluation, used, and discarded, and the pod was gone.

**It exits non-zero if there is a single dangerous confusion**, because
`docs/SAFETY.md` asks for zero or a documented, bounded exception. The card is
written either way — read it before deciding anything. A non-zero exit is the
script declining to let a bad run pass quietly, not a verdict on the model.

The summary prints two counts and they are not the same question:

```
  dangerous confus.  10
    of which SILENT  ?    <- the ones a user would see unwarned
```

A **silent** confusion is one where the deadly species kept less than 2% of
the probability mass, so `server/app/safety.py` never raises the lethal
warning and — since rule 1 renders nothing at all for `NO_RECORDED_TOXICITY`
— the user is shown a harmless name with no hazard line. The rest were
caught by the safety layer: bad, worth fixing, not dangerous.
`--max-silent-dangerous-confusions` is a **separate dial** from the total,
on purpose, so raising the total to admit the caught ones cannot admit a
silent one in the same breath.

---

## 9. Get the results off the box

**Run this first, before anything else in this step:**

```bash
python scripts/finish_run.py
```

It lists every artefact as present or missing, says which of the small ones
`.gitignore` would silently refuse, prints the `git add` line and the
`runpodctl send` lines ready to paste, and **exits non-zero while anything
is missing**. It changes nothing.

The reason it exists: this step used to be the list below, which depended on
somebody reading it at the end of a long day, on a machine billing by the
hour, with the interesting part already finished. On the first real run it
did not survive that. `calibration.json` was never taken and **cannot be
reconstructed** — temperature scaling is fitted on the validation split, so
remaking it needs the images and the checkpoint, both of which go with the
pod. The app has been running at `calibrated=False` ever since, falling back
to a 0.80 threshold and an unfitted out-of-distribution check, for the sake
of a few hundred kilobytes.

If it says `DO NOT STOP THE POD YET`, do not stop the pod yet.

Two routes below, because the outputs split cleanly by size.

**Small and text — commit and push them.** These belong in git anyway: they
are the evidence for the release decision.

```bash
git add ml/runs/baseline/MODEL_CARD.md \
        ml/runs/baseline/report.json \
        ml/runs/baseline/calibration.json \
        ml/runs/baseline/labels.json \
        ml/runs/baseline/predictions.npz \
        data/processed/splits.csv.gz \
        configs/default.yaml          # if the timing check made you change it
git commit -m "First trained model: <top-1>, <n> dangerous confusions"
git push
```

`predictions.npz` (~4 MB) and `splits.csv.gz` (~3 MB) are both bigger than
the rest put together and both belong here. The first lets anyone re-ask
what the app would have said, without a GPU. The second says which
photograph went to which split, which is what makes `check_splits.py`'s
clean result checkable months later and run two comparable to run one.
`.gitignore` un-ignores exactly these two inside otherwise-ignored
directories — **check `git status` shows them before you commit**, because
a pattern ending in `/` stops git descending at all and `git add` then
succeeds while adding nothing. That has already happened twice here.

**Large and binary — do not put these in git.** `best.pt` and `model.onnx`
are both roughly **350 MB** for ViT-B/16. A repository is the wrong place for
them and GitHub will refuse anything over 100 MB regardless.

```bash
runpodctl send ml/runs/baseline/model.onnx
runpodctl send ml/runs/baseline/best.pt
```

That prints a one-time code; run `runpodctl receive <code>` on your own
machine. `runpodctl` is already on the pod. If you would rather not, the
Jupyter file browser will download them over HTTP, slowly.

Take **`model.onnx`** if you take nothing else — it is what the server
loads. `best.pt` is the thing you would need to resume or re-export from, so
it is worth the second transfer.

```
ml/runs/baseline/model.onnx         # what the server loads     ~350 MB
ml/runs/baseline/best.pt            # resume / re-export from   ~350 MB
ml/runs/baseline/labels.json        # tiny, commit
ml/runs/baseline/calibration.json   # tiny, commit
ml/runs/baseline/MODEL_CARD.md      # tiny, commit
ml/runs/baseline/report.json        # tiny, commit
ml/runs/baseline/predictions.npz    # ~4 MB, commit
data/processed/splits.csv.gz        # ~3 MB, commit -- which image went where
data/processed/manifest.parquet     # ~20 MB, take it, cannot be committed
```

The images do not need to come home: the manifest records every URL, licence
and rights holder, so the dataset is **rebuildable**.

**Rebuildable is not reproducible, and the difference is the whole reason
`splits.csv.gz` is on that list.** GBIF moves — occurrences are added,
licences change, synonymy is revised — so a rebuild months later gives a
*different* dataset, and re-running `prepare` on it gives a different split
even at the same seed. The reported accuracy then belongs to a dataset that
no longer exists. `splits.csv.gz` pins it: five columns, every image URL and
the split it was assigned to. `manifest.parquet` is the fuller record and is
worth taking, but `*.parquet` is gitignored and always will be, so it only
ever lives on machines — which is how the first run's went with the pod.

**Then terminate the pod, rather than stopping it.** A stopped pod still
bills for its volume, and the GitHub token is sitting in `.git/config` on it.

## What to change on the box, and what not to

The pod is an ordinary Linux machine with your repo on it, so you *can* edit
anything. Two things are worth changing there and the rest is not.

**Worth changing on the box:** `configs/default.yaml` (epochs, batch size,
backbone — whatever the timing check tells you), and any training code that
turns out to be broken under a real dataset. Commit and push both, or they
die with the pod.

**Not worth changing on the box:** the app. The server, the client, the
taxonomy, the safety layer. Editing those at $0.34/hr is paying a GPU rate
for a text editor, and you cannot meaningfully test the React Native client
there anyway — there is no phone and no simulator. Do that work locally,
push, and `git pull` on the pod if the training run needs it.

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
