# What's That Mushroom — working notes

Fungi identification that reports honest uncertainty. Read `docs/SAFETY.md`
before changing anything in `server/app/safety.py` or `data/taxonomy.seed.json`.

## What this project is

A mushroom identification app whose competitive advantage is **admitting when
it doesn't know**. It competes with PictureMushroom-class consumer apps, which
independent evaluations put at around coin-flip species accuracy and which
always answer because their business model requires confidence.

It deliberately does **not** compete with iNaturalist on community scale,
accuracy or taxonomic breadth. See `docs/POSITIONING.md`.

## Rules that must not be broken

These are product requirements, not style preferences. Each is enforced by a
test; if a change makes a test here fail, the change is wrong.

1. **Never assert edibility.** No "edible", "safe to eat", "choice" in any
   user-facing path. The safest toxicity value is `INEDIBLE`.
2. **Never resolve a lethal ambiguity from a photograph.** If top candidates
   straddle a known dangerous pair, return `dangerous_group` and name neither.
3. **Never round away a small probability of death.** 2% on a deadly species
   triggers the full warning.
4. **Never show uncalibrated confidence as confidence.** If calibration has
   not been fitted, say so.
5. **Never ask for a taste test while a deadly candidate holds mass.**
   Amatoxins are tasteless.
6. **Never select checkpoints on accuracy.** Selection is on risk-weighted
   error.

## Current status

Everything works **except the model**. There is no trained classifier; the API
serves a stub backend with deterministic fake predictions. Every other layer
is real and tested.

157 tests pass. `/health` honestly reports `model_loaded: false`,
`calibrated: false`, `taxonomy_reviewed: false`.

The training pipeline has been rehearsed end to end on synthetic data
(`python scripts/smoke_e2e.py`, ~1 minute on CPU, no dataset or network
needed). Run it before paying for GPU time and after any change to the model,
the config schema or the export path.

**Blocking for any public release: the taxonomy has not been reviewed by a
qualified mycologist.** Toxicity data, lookalike relationships and diagnostic
characters come from standard references but are unverified.

## Layout

| Path | What it holds |
| --- | --- |
| `data/taxonomy.seed.json` | 57 UK species, lookalike graph, toxicity, diagnostic characters |
| `ml/fungi_ml/taxonomy.py` | Species model and the asymmetric risk matrix |
| `ml/fungi_ml/losses.py` | Risk-weighted objective |
| `ml/fungi_ml/calibrate.py` | Temperature scaling, threshold fitting |
| `ml/fungi_ml/evaluate.py` | Safety-first metrics, model card generation |
| `server/app/safety.py` | The safety layer — read first |
| `server/app/interrogation.py` | Question selection by information gain |
| `server/app/characters.py` | How to ask a non-expert for evidence |
| `app/` | Expo React Native client |

## Commands

```bash
# Tests — run these before any commit
python -m pytest ml/tests server/tests -q

# API (stub backend)
cd server && uvicorn app.main:app --reload

# Mobile client
cd app && npm install && EXPO_PUBLIC_API_URL=http://<lan-ip>:8000 npx expo start
```

Training needs a GPU and is documented in `docs/ROADMAP.md`.

## Gotchas

- **`pandas .unique()` returns Arrow-backed strings.** `np.random.shuffle` on
  one can silently duplicate entries. Convert with
  `np.asarray(..., dtype=object)` first. This caused a real observation-leak
  bug; there is a regression test.
- **Splits are on `observation_id`, never on image.** If accuracy looks too
  good, check this before believing it.
- **`character_states` covers the 8 DEADLY species and nothing else, and is
  UNREVIEWED.** It was derived from the taxonomy's own `notes`, not from a
  mycologist, and every entry needs field-character review before release.
  The other 49 species are undescribed, which the matcher treats as *no
  evidence* rather than a mismatch, so answers about them still move nothing.
  `/health` reports `character_states_described`;
  `python scripts/character_states.py status` prints the same.
- **State lists are deliberately generous, and must stay that way.** Omitting
  a state a species can show turns a true observation into a contradiction and
  pushes a lethal candidate *down* — the one direction this project cannot
  tolerate. An extra state only makes the character less discriminating.
  Galerina lists all four ring states for this reason; the death cap lists
  five cap colours. Where the notes made no claim the entry is omitted, and
  omitted is always safe.
- **Some answer options are non-observations, not states.** `volva`'s "I cut
  it off" and `cortina`'s "Can't tell" are in `uninformative_options` and get
  a likelihood of 1.0. Without that, the commonest field mistake — cutting the
  stem base off — would have pushed the death cap from 0.50 to 0.355 against a
  field mushroom. Any new option meaning "I could not look" must be added
  there; a test asserts no committed state is one.
- **Filling the table is a worksheet job, not a code job.** `python
  scripts/character_states.py emit` writes `docs/character-states-worksheet.csv`
  (190 rows, deadliest first); `import` validates and writes back. A state
  that is not exactly one of the character's answer options is refused,
  because it would store cleanly and never match anything.
- **`notes` is rendered verbatim to users.** Rationale, policy and review
  flags go in `internal_note`, which is never surfaced.
- **Expect 50–70% species top-1** on a first training run, with genus accuracy
  notably higher. 95% means a leak.

## Related

A copy of this project also exists on the `claude/fungi-identification-ai-app-43w7xp`
branch of `mhawkes1/ibp-management-system`, kept as a frozen backup. **Do not
edit it** — this repo is the working copy. The IBP repo is an unrelated
school safeguarding system that happens to have hosted this project's first
commits.
