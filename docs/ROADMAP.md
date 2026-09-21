# Roadmap

## Status

Working: taxonomy and risk model, dataset pipeline, training loop,
calibration, evaluation and model card generation, safety layer,
interrogation engine, HTTP API, Expo client. 80 tests pass.

Not working: there is no trained model. The API serves a stub backend that
produces deterministic fake predictions so the rest of the system can be
developed and tested. Everything except the predictions themselves is real.

## Next, in order

### 1. Train the first model

```bash
pip install -r ml/requirements.txt
python scripts/build_dataset.py --target 400 --country GB
cd ml && python -m fungi_ml.train --config configs/default.yaml
python -m fungi_ml.calibrate --checkpoint runs/baseline/best.pt \
    --manifest ../data/processed/manifest.parquet --split test
python -m fungi_ml.export --checkpoint runs/baseline/best.pt
```

Needs a GPU. A single A10G or 4090 handles the default config; roughly
6-10 hours for 30 epochs on ~20k images. Rent rather than buy at this stage.

Expect species-level top-1 somewhere in the 50-70% range on a first pass with
this label space, and genus accuracy substantially higher. If the first run
reports 95%, there is a leak — check the observation-level split first.

### 2. Replace the answer-weighting stub

`InterrogationEngine.apply_answer` currently applies a weak, conservative
re-weighting because there is no per-species character-state table. It should
never have been more aggressive than that without one, but it is the weakest
part of the system.

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

### 3. Species-level claims the evidence cannot support

Adding the small *Lepiota* species exposed a gap that is about honesty rather
than safety. When every candidate is a deadly Lepiota the app will name one,
which is safe -- it names a deadly species and warns -- but the species-level
claim is not supportable, because those species genuinely cannot be separated
from a photograph without microscopy.

The fix is a per-species `photo_resolvable: false` flag in the taxonomy, with
the safety layer reporting at genus level for anything carrying it. Populating
it is a mycological judgement, so it waits on review. *Cortinarius*, *Inocybe*
and the small *Lepiota* species are the obvious candidates.

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

## Explicitly not doing

- **Competing with iNaturalist on community or breadth.** They have won that.
  This is a focused tool for one taxonomic group.
- **Edibility guidance.** Not now, not behind a paywall, not with a
  disclaimer. See `SAFETY.md`.
- **Global coverage at launch.** UK-first with real depth beats worldwide and
  shallow. The model conditions on location, so regional expansion is a
  data problem rather than a redesign.
