# Design decisions

Why the project is built the way it is. Recorded so a future contributor
does not undo a deliberate choice mistaking it for an oversight.

---

## Platform: React Native / Expo

Chosen over a web PWA because camera access, offline inference and eventual
on-device models all matter here, and woodland has poor signal. One codebase
covers iOS and Android.

Cost: slower initial setup and app-store accounts needed to distribute.
Accepted.

---

## Model: custom classifier, not a vision LLM

A vision LLM would have produced a working prototype in days with no training
data or GPU. Rejected for v1 because:

- Fine-grained species-level discrimination is where dedicated classifiers
  still win decisively.
- The risk-weighted objective (below) needs access to the loss function.
- Calibration needs access to logits. A vision LLM's stated confidence cannot
  be temperature-scaled against held-out data, which removes the entire
  basis for the safety thresholds.

A hybrid — classifier for ranking, LLM for explanation — remains the sensible
long-term architecture. The classifier is the part that has to exist first.

---

## Splitting on observation, not image

A fruiting body is typically photographed several times from several angles.
Splitting on image puts near-duplicates in both train and validation and
inflates reported accuracy substantially.

`prepare.py` splits on `observation_id` and asserts no observation straddles
splits. `test_no_observation_leaks_across_splits` enforces it.

**If a training run reports suspiciously high accuracy, check this first.**

---

## Risk-weighted loss rather than plain cross-entropy

Cross-entropy treats every error as equal. For this application it is not:
confusing two brittlegills costs nothing, confusing a death cap with a field
mushroom can kill.

`taxonomy.py` models misclassification cost asymmetrically — under-calling a
lethal species costs 1000x, over-caution costs 2x — and `losses.py` turns that
into a per-example gradient multiplier, capped so a single death-cap example
cannot destabilise a batch.

**Checkpoint selection is on risk-weighted error, not accuracy.** A model one
point more accurate that confuses death caps more often is the worse model
here.

---

## Metadata fused into the network, not applied as a post-hoc filter

Season and location carry real discriminative signal for fungi. Filtering
candidates after the fact discards the model's ability to weigh that signal
against visual evidence.

Metadata dropout during training (default 0.3) keeps the visual pathway
self-sufficient, because users skip the optional questions constantly.

Missing metadata is flagged with explicit `*_known` bits rather than imputed.
A model told "it is January" when the month is unknown will rule out autumn
species that are in fact correct.

---

## No "edible" value anywhere in the type system

The `toxicity` enum's safest value is `INEDIBLE`, rendered as "Not assessed as
safe". There is deliberately no positive category.

This is not squeamishness. Users read a best-case label as permission, and
the app has no way to verify what the user is actually holding. Enforced by
test, not convention — see `SAFETY.md`.

---

## Stub inference backend

The API ships with a backend producing deterministic fake predictions derived
from image content, so the safety layer, interrogation engine, API and mobile
client could all be built and tested before a model existed.

It is not a placeholder to be deleted — it stays as a test fixture. Swap in
`OnnxBackend` by pointing `WTM_MODEL_PATH` at a real export.

---

## Conservative answer re-weighting

`InterrogationEngine.apply_answer` applies only a weak multiplier and can
never zero a candidate. This is the weakest part of the system and it is
deliberate: there is no per-species character-state table yet, so the engine
cannot know what an answer rules *out*.

A user squinting at gills in poor light is a noisy sensor. Treating their
answer as certain would reintroduce exactly the overconfidence this project
exists to avoid.

The fix is a `character_states` block per species, which requires mycological
review first because it encodes claims users will act on. See `ROADMAP.md`.

---

## ONNX export verifies itself

`export.py` compares its output against the PyTorch model and refuses to
write a divergent file. A silently wrong export runs fine and returns
plausible numbers — the worst possible failure mode here.

---

## UK-first

Global models are mediocre everywhere. Because the model conditions on
location, regional expansion is a data problem rather than a redesign.
