# Roadmap

## Status

Working: taxonomy and risk model, dataset pipeline, training loop,
calibration, evaluation and model card generation, safety layer,
interrogation engine, HTTP API, Expo client. 210 tests pass.

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

### 3. Get the character-state table reviewed

**The mechanism is built and the table is complete for all 60 species. What
is left is not filling it in but checking it, and that needs a forager or a
mycologist rather than a programmer.**

`apply_answer` now delegates to `server/app/evidence.py`, which compares an
answer against each species' declared `character_states` and applies a
likelihood: consistent leaves a candidate alone, inconsistent pushes it down,
and *undescribed leaves it alone too* -- because an absence of description on
our side is not evidence about the mushroom. Contradicting a deadly species
costs it far less than contradicting a harmless one, and no answer may drive a
deadly candidate below the threshold at which the safety layer still warns.

An undescribed species -- or a species undescribed for the character being
asked about -- gets a likelihood of 1.0 and is left alone. That degradation is visible rather
than disguised: `/health` reports `character_states_described`, and
`python scripts/character_states.py status` prints coverage.

The 30 species forming the lethal confusion pairs -- the 8 deadly ones and
the 22 safe lookalikes opposite them -- were filled in from this repository's
own `notes`, via the worksheet and importer below rather than by hand, so
every state was validated against the answer options.

Doing the safe half was not optional padding. With only the deadly species
described, nothing a user reported could contradict the harmless lookalike, so
evidence could move mass *away* from a lethal candidate but never toward one:
a user describing a death cap -- volva, white spore print, white gills --
moved it 0.300 to 0.300. With both halves described the same three answers
move it 0.300 to 0.965. They are marked UNREVIEWED in the
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

205 rows, one per (species, diagnostic character) pair, all filled and all unreviewed. Import refuses any
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

### 4. Out-of-distribution detection *(done, pending a trained model)*

The check was a threshold on top-1 probability, and the flaw is structural:
softmax depends only on the *differences* between logits, so it is unchanged
when every logit shifts down -- which is exactly what an input the network has
no features for produces. Two photographs can yield identical softmax output,
one a genuine mushroom and one a slug, and the old rule accepted both at 98%
confidence.

`server/app/ood.py` uses free energy, `-logsumexp(logits)`, which keeps the
magnitude softmax discards. It is computed on the raw logits, before
temperature scaling, and `calibrate.py` fits the threshold on held-out known
species at a chosen rate of false unknowns (5% by default). Fitting from
in-distribution data alone is deliberate: tuning against collected negatives
would fix the threshold against whichever negatives someone gathered, and the
inputs that matter are the ones nobody thought to collect.

Until a threshold is fitted the detector reports itself unfitted and the
safety layer falls back to the old rule knowingly, rather than inventing a
number -- the same principle as rule 4.

Still open here:

- **It is unvalidated against real out-of-distribution photographs.** The
  mechanism is tested and the threshold fits, but nothing has measured the
  detection rate on actual slugs, pine cones and unlisted species, because
  there is no trained model. Do this with the first real checkpoint.
- **A Mahalanobis distance on penultimate features** would likely beat energy
  and needs the same plumbing, which now exists.

### 5. On-device inference

Signal in woodland is poor and this is where the app is used. Export to
TFLite or Core ML with a smaller backbone (EfficientNet-B0/B2) and ship the
model in the bundle. The safety layer must move client-side with it —
critically, it must not be possible to get a species answer with the safety
rules bypassed because the network was unavailable.

### 6. Guided spore print workflow *(done)*

Four steps, in `app/src/screens/SporePrintScreen.tsx`: how to set a print up,
a timer that outlives the app being closed, a guided photograph against the
half-white card, and a colour match the user confirms. Reached from the
question card whenever the engine asks for a spore print, which is the one
character it will send someone away for hours to obtain.

The matcher in `server/app/spore_print.py` already existed and was wired to
nothing. `POST /spore-print/match` now takes the photograph plus two regions
as fractions of the image and samples them server-side, because pixel access
is awkward on the device and the colour judgement already lives beside the
answer strings it has to produce. The sample is a median rather than a mean,
so dust specks and glare do not drag a black print toward grey.

Nothing is submitted automatically. A confident reading is shown as a
suggestion beside the full manual list, and the user picks.

### 7. Observation log *(done)*

`app/src/lib/observationLog.ts`, `app/src/screens/HistoryScreen.tsx`. Local
history of what the user photographed, where and when, with what they
answered and the verdict as it stood when they left the screen. Nothing is
uploaded.

The design question is not storage, it is what a stored answer is allowed to
say later. At the moment of identification the user sees the verdict, the
refusal, the warnings and the question that would settle it; weeks later they
see a thumbnail and one line of text, and that line is what they remember. So
the log stores the verdict rather than the name, and only a `species` verdict
puts a species on a row — the lethal-pair refusal included, though the result
screen does name both halves of the pair, because a name read at a glance and
out of context is an answer.

Refusals are logged like everything else. A history that quietly kept only
the confident identifications would misrepresent the app to its own user.

Each entry also carries the model version and calibration state it was
produced under, and `caveats` compares them against `/health`. Rule 4 holds
along the time axis: a confidence recorded before calibration was fitted must
not later read as a calibrated one. `/health` now reports `model_version` so
a client can ask that without running an identification.

Still to do here: the photograph URIs are references, and the OS may evict a
camera cache file. A row survives it — the record outlives the photograph —
but copying the top view into the app's own storage would be better.

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
- **Question selection driven by the character-state table.** The engine used
  to score a question by whether candidates *declared* the character as
  diagnostic, which cannot tell a character they differ on from one they
  share. With the funeral bell and the sheathed woodtuft as the candidates its
  top recommendation was `substrate` -- both grow on dead wood -- and a spore
  print ranked above the one character that does separate them. `expected_gain`
  now simulates every answer through the real re-weighting, so selection and
  application are one model and a shared character scores near zero.
- **Spore print colour matching** (`server/app/spore_print.py`). Matches a
  photographed deposit against a reference chart in CIELAB using CIEDE2000,
  correcting exposure and colour cast against the white half of the card. It
  refuses far more often than it answers, which is the point.

- **The companion ebook, filled from the taxonomy**
  (`scripts/build_ebook.py`). The book and the app make the same claims about
  the same species; generating one from the other is what stops two copies
  drifting. It fills 114 field rows, 75 key points and all 26 field notes into
  a *new* file, never overwriting a slot the author has written, marking every
  value it writes and banner-ing the page — a printed guide carries no
  `taxonomy_reviewed: false` the way `/health` does. It prints no taste
  (rule 5 cannot be enforced on paper), and it reports every row it left
  blank, which turned out to be the useful output: see the thin-character
  table in `docs/REVIEW.md`.

- **Onboarding consent and the incident route** — the two remaining blocking
  items in `docs/SAFETY.md` that were not about the model. `GET /disclaimer`
  serves what a user acknowledges, versioned by a hash of its own text, so a
  materially changed disclaimer is re-acknowledged rather than silently
  inherited; three of its statements are conditional on `model_loaded`,
  `calibrated` and `taxonomy_reviewed`, which means training a model or
  getting the taxonomy reviewed re-asks by construction. `POST /incident`
  takes a report that the app was wrong, grades it from the taxonomy rather
  than from its wording, and returns a report of someone being unwell as an
  emergency rather than as a filed ticket. `docs/INCIDENTS.md` is the process.

  Neither is finished in the sense of shippable: the disclaimer still needs
  the legal review, and the incident route needs a named responder, rate
  limiting and a retention period. Both are now recorded where they belong
  rather than in this file.

- **Twenty-seven species added by record frequency** (`scripts/frdbi_gap.py`).
  The label space went 79 → 106 and its coverage of the hundred most-recorded
  British macrofungi went 30% → 57%. The rule followed throughout: a common
  species is never added without the dangerous thing it resembles, because
  adding the first without the second teaches a name the model will reach for
  and withholds the one it should have refused over. The batch created 14 new
  lethal pairs.

  A second batch of 129 completed the top 200. The label space is 235 species
  and 126 lethal pairs, from 79 and 53 at the start of the day. Below rank 200
  coverage falls away sharply, and `--top 300` needs the genus table extended
  first — the report says so rather than quietly undercounting.

  Two consequences worth carrying forward. The worksheet is now 1,155 rows
  rather than 289, so the mycological review is a fivefold bigger job and the
  bulk-written rows deserve less trust than the originals. And 235 classes is
  a much harder training problem than 79, with several pairs that are not
  separable from a photograph at all — which is an argument for watching
  risk-weighted error rather than accuracy, as rule 6 already requires.

## Explicitly not doing

- **Competing with iNaturalist on community or breadth.** They have won that.
  This is a focused tool for one taxonomic group.
- **Edibility guidance.** Not now, not behind a paywall, not with a
  disclaimer. See `SAFETY.md`.
- **Global coverage at launch.** UK-first with real depth beats worldwide and
  shallow. The model conditions on location, so regional expansion is a
  data problem rather than a redesign.
