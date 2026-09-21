# Roadmap

## Status

Working: taxonomy and risk model, dataset pipeline, training loop,
calibration, evaluation and model card generation, safety layer,
interrogation engine, HTTP API, Expo client. 157 tests pass.

The chain from raw manifest through to a served ONNX model has now been run
end to end on synthetic data (`scripts/smoke_e2e.py`), so the stages are known
to fit together rather than merely known to work in isolation.

Not working: there is no trained model, and no dataset. The API serves a stub
backend that produces deterministic fake predictions so the rest of the system
can be developed and tested. Everything except the predictions themselves is
real.

## Next, in order

### 0. Rehearse the pipeline before spending anything

```bash
python scripts/smoke_e2e.py
```

About a minute on CPU. Synthesises a small random dataset and walks
prepare -> train -> calibrate -> export -> serve, asserting only that each
stage hands the next one something usable. It says nothing about accuracy --
the data is noise -- and that is the point: it tests the seams, which is where
this pipeline actually breaks.

Running it the first time found two faults that would each have surfaced only
at the end of a paid training run:

- `onnxscript` was missing from `ml/requirements.txt`. Since torch 2.9 the
  default ONNX exporter imports it, so export died on `ModuleNotFoundError`
  after training had completed.
- `export` and `calibrate` rebuilt the model from the checkpoint by hand,
  reading only `backbone`. Every other architectural switch was dropped --
  `use_metadata` above all, which changes the state dict, so a run configured
  without the metadata branch trained fine and then failed to load.

A third fault it surfaced was quieter and is the one worth remembering:
`torch.onnx.export` treats `opset_version` as a request, not a promise. Asking
for opset 17 produced a file declaring opset 18, with no exception and no
non-zero exit. It verified, served and looked correct, because the local
onnxruntime is new enough to run either. It would have failed against a pinned
runtime or against the Core ML/TFLite converters step 5 needs. Export now reads
back what it wrote and refuses to ship an opset that is not the one requested.

Re-run this after any change to the model, the config schema or the export
path.

### 1. Build the dataset

```bash
pip install -r ml/requirements.txt
python scripts/build_dataset.py --target 400 --country GB
```

**This is the gate on everything else, and it needs no GPU.** It is bound by
network and disk: roughly 20k images pulled one at a time from GBIF, which is
hours of wall time and tens of GB. Renting a GPU to sit idle through it wastes
the rent.

It also needs unrestricted outbound access to `api.gbif.org` and to the
iNaturalist media CDN. Sandboxes and locked-down CI runners commonly block
both, which fails at the first request rather than partway through. The run is
resumable -- images already on disk are skipped -- so an interrupted build
costs only the time already spent.

Check before moving on: how many species survived `--min-images 40`. The seed
taxonomy has 57, and the long tail of UK fungi means fewer will clear the
threshold. Species that were dropped are not in the label space, and the safety
layer cannot warn about a lookalike the model cannot name.

### 2. Train the first model

```bash
cd ml && python -m fungi_ml.train --config configs/default.yaml
python -m fungi_ml.calibrate --checkpoint runs/baseline/best.pt \
    --manifest ../data/processed/manifest.parquet --split test
python -m fungi_ml.export --checkpoint runs/baseline/best.pt
```

This is the step that needs a GPU, and the only one that does. The default
config is a 86M-parameter ViT-B/16 at 384px; a single 24GB card (A10G, 3090,
4090) fits it at batch size 32, and 30 epochs over ~20k images is roughly
6-10 hours. Rent rather than buy at this stage.

Take the dataset to the GPU box already built, or build it on a cheap
CPU instance and copy it across. Bring `data/processed/` and `data/images/`;
nothing else in the repo is large.

Calibration and export are CPU-bound and take minutes, so they can run
anywhere -- but run them before releasing the rental, because a checkpoint
that will not export is a checkpoint that has to be retrained.

Expect species-level top-1 somewhere in the 50-70% range on a first pass with
this label space, and genus accuracy substantially higher. If the first run
reports 95%, there is a leak — check the observation-level split first.

### 3. Fill in the rest of the character-state table

**The mechanism is built and the 8 deadly species are filled in, unreviewed.
The remaining 49 need a reviewer rather than a programmer.**

`apply_answer` now delegates to `server/app/evidence.py`, which compares an
answer against each species' declared `character_states` and applies a
likelihood: consistent leaves a candidate alone, inconsistent pushes it down,
and *undescribed leaves it alone too* -- because an absence of description on
our side is not evidence about the mushroom. Contradicting a deadly species
costs it far less than contradicting a harmless one, and no answer may drive a
deadly candidate below the threshold at which the safety layer still warns.

An undescribed species gets a likelihood of 1.0, so answers about the 49
species still undescribed change nothing. That degradation is visible rather
than disguised: `/health` reports `character_states_described`, and
`python scripts/character_states.py status` prints coverage.

The 8 deadly species were filled in from this repository's own `notes`, via
the worksheet and importer below rather than by hand, so every state was
validated against the answer options. They are marked UNREVIEWED in the
taxonomy, in the worksheet and in `docs/REVIEW.md`, and still need
field-character sign-off.

Filling them in surfaced a hazard in the mechanism that an empty table hid.
`volva` offers "I cut it off" and `cortina` offers "Can't tell" -- answers
that report a failed observation rather than a state of the mushroom. Treated
as states they *contradicted* the species that have a volva, so cutting the
stem base off, which is precisely how an Amanita gets missed, pushed the death
cap from 0.50 to 0.355 against a field mushroom. Those options are now marked
`uninformative_options` and carry no evidence either way.

**Write the lists generously.** Omitting a state a species can show turns a
true observation into a contradiction and pushes a lethal candidate down. An
extra state merely makes the character less discriminating. Leave a row blank
wherever you are unsure: blank means undescribed, which is always safe.

To fill it in:

```bash
python scripts/character_states.py emit     # docs/character-states-worksheet.csv
# ... a reviewer fills REVIEW_states, deadliest species first ...
python scripts/character_states.py import --dry-run
python scripts/character_states.py import
```

190 rows, one per (species, diagnostic character) pair; 30 filled, 160 open. Import refuses any
state that is not exactly one of that character's answer options, since such a
state would store cleanly and never match anything -- a populated table that
cannot fire is worse than an empty one.

This still wants the field-character review in `docs/REVIEW.md`: it encodes
claims about species that users act on. But `REVIEW.md` is explicit that
field-character review is the half an experienced forager can do and that it
unblocks internal development, as distinct from the toxicity and nomenclature
review that blocks release.

#### What the old stub did

`InterrogationEngine.apply_answer` currently applies a weak, conservative
re-weighting because there is no per-species character-state table. It should
never have been more aggressive than that without one, but it is the weakest
part of the system.

How weak is measurable. Running every character against every one of its
answer options, 157 combinations in total:

> **Only 34 of 157 (22%) change the candidate ranking at all.** The remaining
> 78% are silent no-ops.

The cause is that `apply_answer` boosts a species only when the answer string
happens to appear verbatim in that species' free-text `notes`. That is an
accident of the data rather than a model of anything.

That is why it was removed rather than kept as a fallback. Coincidence
presented as evidence is worse than no evidence in a system whose whole claim
is that it reports uncertainty honestly -- and keeping it would have polluted
the real mechanism with the old noise. The measured effect of answers is
therefore 22% today and 0% after this change, deliberately, until the table
lands.

The fix is a `character_states` block per species in the taxonomy:

```json
"amanita-phalloides": {
  "character_states": {
    "volva": ["Clear cup or sac"],
    "spore_print_colour": ["White or cream"],
    "gill_colour": ["White"]
  }
}
```

With that, answers become proper likelihood updates rather than a heuristic
nudge, and an answer can legitimately rule candidates out. This requires the
mycological review in `SAFETY.md` to happen first, since it encodes claims
about species that users will act on.

### 4. Out-of-distribution detection

The current OOD check is a threshold on top-1 probability, which is weak. A
user photographing a slug, a pine cone, or a species outside the label space
should get a clear "that isn't something I know", not a confident wrong
answer. Options: an energy-based score, a Mahalanobis distance on penultimate
features, or an explicit "not a fungus" class trained on negatives.

### 5. On-device inference

Signal in woodland is poor and this is where the app is used. Export to
TFLite or Core ML with a smaller backbone (EfficientNet-B0/B2) and ship the
model in the bundle. The safety layer must move client-side with it —
critically, it must not be possible to get a species answer with the safety
rules bypassed because the network was unavailable.

### 6. Guided spore print workflow

Nobody has built this and it is the most diagnostic cheap test in mycology.
Guided capture, a timer, and colour matching against a reference chart under
controlled white balance. A genuine differentiator and a genuine contribution.

### 7. Observation log

Local history of what the user photographed, where and when, with the
questions they answered. Useful in itself, and the foundation for any future
community verification.

## Done since this list was written

- **Multi-view capture.** `/identify` takes cap, side and underside; the views
  are averaged in probability space rather than in logits, so one
  over-confident view cannot shout down the others and the result stays a
  probability the safety thresholds can be set against. Only the top view is
  required.
- **The field-notes form.** One screen, eight characters, every field
  skippable. Served from `/field-form` rather than hardcoded in the client, so
  the options cannot drift from the catalogue the server validates against.
  An unknown character or an out-of-list answer is rejected rather than
  quietly dropped.
- **Spore print colour matching** (`server/app/spore_print.py`). Matches a
  photographed deposit against a reference chart in CIELAB using CIEDE2000,
  correcting exposure and colour cast against the white half of the card. It
  refuses far more often than it answers, which is the point. Not yet wired
  to a guided-capture screen -- the matcher exists, the camera flow does not.

## Explicitly not doing

- **Competing with iNaturalist on community or breadth.** They have won that.
  This is a focused tool for one taxonomic group.
- **Edibility guidance.** Not now, not behind a paywall, not with a
  disclaimer. See `SAFETY.md`.
- **Global coverage at launch.** UK-first with real depth beats worldwide and
  shallow. The model conditions on location, so regional expansion is a
  data problem rather than a redesign.
