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

210 tests pass. `/health` honestly reports `model_loaded: false`,
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
| `data/taxonomy.seed.json` | 79 UK species, lookalike graph, toxicity, diagnostic characters, character states |
| `ml/fungi_ml/taxonomy.py` | Species model and the asymmetric risk matrix |
| `ml/fungi_ml/losses.py` | Risk-weighted objective |
| `ml/fungi_ml/calibrate.py` | Temperature scaling, threshold fitting |
| `ml/fungi_ml/evaluate.py` | Safety-first metrics, model card generation |
| `server/app/safety.py` | The safety layer — read first |
| `server/app/interrogation.py` | Question selection; gain computed in `evidence.py` |
| `server/app/evidence.py` | Answer likelihoods, the safety floors, expected gain |
| `server/app/ood.py` | Free-energy check for "that isn't something I know" |
| `server/app/spore_print.py` | Reads a photographed spore print against a colour chart |
| `server/app/characters.py` | How to ask a non-expert for evidence |
| `app/` | Expo React Native client |
| `app/src/lib/observationLog.ts` | Local history; what a stored verdict may say later |
| `app/src/components/CoverHeader.tsx` | The book's cover as the app's front page |
| `server/app/disclaimer.py` | What a user acknowledges before first use; the version is the text |
| `server/app/incidents.py` | Reports that the app was wrong, and how they are graded |
| `docs/INCIDENTS.md` | Who acts on a report, and in what order |
| `scripts/build_ebook.py` | Fills the companion ebook's field slots from the taxonomy |
| `scripts/demo.py` | Drives the real safety layer, engine and matcher in a terminal |
| `scripts/frdbi_gap.py` | Label space vs. how often things are actually found |
| `data/frdbi-records.csv` | Every FRDBI taxon and its record count, exported 2026-09-22 |
| `data/frdbi-genera.csv` | Genus → fungus / micro / host / slime-mould, so the ranking can be filtered |

## Commands

```bash
# Tests — run these before any commit
python -m pytest ml/tests server/tests -q
cd app && npm test && npm run typecheck

# API (stub backend)
cd server && uvicorn app.main:app --reload

# Mobile client
cd app && npm install && EXPO_PUBLIC_API_URL=http://<lan-ip>:8000 npx expo start

# Companion ebook -- fill its field data from the taxonomy
python scripts/build_ebook.py --ebook <book>.html --out draft.html

# See it work -- no GPU, no dataset, no network, nothing mocked
python scripts/demo.py
```

Training needs a GPU and is documented in `docs/ROADMAP.md`.

## Gotchas

- **`pandas .unique()` returns Arrow-backed strings.** `np.random.shuffle` on
  one can silently duplicate entries. Convert with
  `np.asarray(..., dtype=object)` first. This caused a real observation-leak
  bug; there is a regression test.
- **Splits are on `observation_id`, never on image.** If accuracy looks too
  good, check this before believing it.
- **`character_states` is complete for all 79 species and UNREVIEWED
  throughout.** Derived from the taxonomy's own `notes`, not from a
  mycologist. Complete is not reviewed: `reviewed_by` is still null and
  `/health` still reports `taxonomy_reviewed: false`. A forager's eye over
  `docs/character-states-worksheet.csv` is the highest-value review left.
- **Both halves of a lethal pair must be described, or evidence only works
  one way.** With just the deadly half described, nothing could contradict the
  safe lookalike, so answers could move mass *away* from a lethal candidate
  but never toward one: a user describing a death cap (volva, white spore
  print, white gills) moved it 0.300 → 0.300. With both halves, 0.300 → 0.965.
  There is a test pinning this; don't strip the safe-half states as redundant.
- **The list-width convention differs by role, and follows from the risk
  matrix.** For a *deadly* species a contradiction pushes it down, so lists are
  **generous** — omitting a state it can show would falsely dismiss something
  lethal. Galerina lists all four ring states; the death cap lists five cap
  colours. For the *safe half* of a pair a contradiction pushes the safe
  species down, moving mass back toward the deadly one, so lists are **tight**
  — the cost of error there is a false alarm, not a missed poisoning. Where
  the notes make no positive claim, the entry is omitted.
- **Contradiction has three tiers, mirroring the risk matrix's 1 / 100 / 1000.**
  `INCONSISTENT` 0.25, `SERIOUS_INCONSISTENT` 0.40, `DEADLY_INCONSISTENT` 0.55.
  The probability floor applies to DEADLY only, because rule 3 is about death.
- **A consistent answer never boosts.** Evidence eliminates; it cannot
  manufacture confidence the classifier did not supply. So an answer matching
  a species moves nothing on its own — it only bites by contradicting rivals.
  Tests that expect a matching answer to promote a species are wrong.
- **Question selection and answer application are one model, deliberately.**
  `expected_gain` simulates every answer through the real `reweight`, so the
  engine cannot recommend a character its own update would ignore. Before
  this, selection scored characters by whether candidates *declared* them,
  and the top question for the funeral bell against the sheathed woodtuft was
  `substrate` — which both show identically. Don't reintroduce a separate
  heuristic for selection.
- **Two likelihoods, for two different jobs.** `likelihood_for` is the
  safety-floored one used to *update* a ranking; `PREDICTIVE_MISMATCH` (0.05)
  is the sharp one used only to guess *what a user will say* when averaging
  over possible answers. Reading the floors as probabilities implies a blusher
  is 25% likely to look blue, which buries the informative answers under
  absurd ones.
- **`Question.expected_information_gain` is bits; `Question.priority` is the
  sort key.** They were one field, which let the dangerous-pair bonus publish
  a near-zero-information question to the client as a high-scoring one.
- **Some answer options are non-observations, not states.** `volva`'s "I cut
  it off" and `cortina`'s "Can't tell" are in `uninformative_options` and get
  a likelihood of 1.0. Without that, the commonest field mistake — cutting the
  stem base off — would have pushed the death cap from 0.50 to 0.355 against a
  field mushroom. Any new option meaning "I could not look" must be added
  there; a test asserts no committed state is one.
- **Filling the table is a worksheet job, not a code job.** `python
  scripts/character_states.py emit` writes `docs/character-states-worksheet.csv`
  (289 rows, deadliest first, and it preserves answers already in the sheet);
  `import` validates and writes back. A state that is not exactly one of the
  character's answer options is refused, because it would store cleanly and
  never match anything.
- **`import` is authoritative and wipes states not in the sheet.** Writing
  `character_states` straight into the JSON and then running `emit`/`import`
  silently removes them. Add a species' states by filling its worksheet rows,
  not by editing the taxonomy — a round trip must be lossless or the sheet
  stops being the source of truth.
- **`lookalikes` may only reference species in the label space**, and a test
  enforces it. A lookalike outside the label space goes in `internal_note`
  instead, where it doubles as the candidate list if the label space grows.
- **Softmax cannot detect out-of-distribution input, and that is why
  `ood.py` exists.** Softmax depends only on *differences* between logits, so
  shifting every logit down leaves it byte-identical while the network has
  recognised nothing. The old check read top-1 probability and accepted both
  cases at p=0.98. Free energy (`-logsumexp(logits)`) keeps the magnitude and
  separates them. Compute it on **raw logits** — before temperature scaling
  and before softmax — or the signal is gone.
- **The energy threshold is fitted on known species only, not on negatives.**
  `fit_energy_threshold` takes the rate of *false unknowns* it will accept
  (default 5%), because the out-of-distribution inputs that matter are the
  ones nobody thought to collect. An unfitted detector reports
  `fitted: False` and the safety layer falls back to the old top-1 rule
  knowingly; it must never invent a threshold.
- **Views are averaged, not minimised.** One well-framed photo must not vouch
  for a set that is otherwise unreadable.
- **The client never reads pixels; the server samples the patches.** Pixel
  access is awkward in React Native, so `/spore-print/match` takes the photo
  plus two regions as fractions (`x,y,w,h`) and samples them with PIL. The
  statistic is a **median**, not a mean — a deposit on paper picks up dust
  specks and glare, and one bright speck on a black print drags a mean toward
  grey, which is a different chart entry.
- **The spore print timer is a stored timestamp, not a countdown.** The wait
  is 2–12 hours, far longer than an app session, so everything derives from
  one `startedAt` in AsyncStorage. A countdown does not survive the process
  being killed. `waitStatus` is pure and the storage accessors each swallow
  their own failure.
- **A matched spore colour is never auto-submitted.** The match returns a
  suggestion beside the manual list and the user picks. Spore print colour is
  what separates an *Amanita* from a young *Agaricus*, so the app proposes and
  the person decides.
- **The front page is the book's cover, with three deliberate departures.**
  `CoverHeader.tsx` reproduces Martin Hawkes's cover — same photograph, same
  Fraunces setting, same gold rule. It is *not* full-screen (on an app that
  puts the thing the user came to do below the fold); the emergency route is
  pinned to the top corner (the one control that must never need a scroll);
  and the book's "1st Edition · 25 most common species" flag is dropped,
  because the app's label space is 79 and on that screen the line would be
  false. The scrim is a real gradient, not stacked translucent views — flat
  bands leave visible edges across the photograph.
- **The cover's typeface is loaded but never awaited.** `useFonts` reports an
  error as well as a loading state, and a front page that will not render
  because a font did not arrive is worse than a cover set in the platform
  serif. `theme.cover` names the family; React Native falls back on its own.
- **A history row names a species only under a `species` verdict.** Including
  `dangerous_group`, where the result screen *does* name both halves of the
  pair — naming both is a warning while the refusal is on the screen beside
  it, but in a scrolling list weeks later it is two guesses to choose between.
  `summarise` in `observationLog.ts` enforces this and a test pins it.
- **A stored confidence carries the model version and calibration state it was
  produced under.** Rule 4 along the time axis: saying "uncalibrated" once, at
  the time, does not survive into a history row. `caveats` compares an entry
  against `/health` and reports both facts separately rather than picking a
  worst case. When the service is unreachable it still reports the
  calibration one — that needs nothing to compare against — and stays silent
  about drift rather than guessing either way.
- **Log writes are serialised.** Every one is read-modify-write over a single
  AsyncStorage blob, and the result screen saves on arrival and again after
  each answer. Without the queue, twenty overlapping saves collapse to one;
  there is a test that fails if the queue is removed.
- **The client has a test suite now** (`cd app && npm test`, vitest).
  AsyncStorage is aliased to an in-memory double in `vitest.config.ts`, so
  storage behaviour is tested rather than mocked away. Only modules free of
  the RN renderer are covered.
- **The disclaimer's version is a hash of its own text.** Change a word and
  every stored consent goes stale and is asked again, because agreeing to an
  older statement is not agreeing to a newer one. Three of the statements are
  conditional on `model_loaded`, `calibrated` and `taxonomy_reviewed`, so
  training a model or getting the taxonomy reviewed re-asks by construction —
  that is intended, the terms genuinely changed.
- **Each acknowledgement is ticked on its own; there is no "accept all".** One
  blanket agreement is a formality, and a formality is what people learn to
  tap past. `isComplete` requires every key individually and a test pins that
  an empty list cannot satisfy it — a disclaimer that failed to load must not
  read as one with nothing to agree to.
- **The emergency screen is the one hardcoded, offline, ungated string in the
  app.** Everything else a user reads is served so one copy exists. This is
  the exception: the screen that must never fail is this one, a wood is where
  the network is not, and it sits above the consent gate because someone
  whose child has eaten something is not going to complete an onboarding flow.
- **The report form checks for a medical emergency before it submits.** Not
  only on the server's reply — the reply needs the network. A yes to "has
  anyone eaten it" or "is anyone unwell" turns the screen into the emergency
  guidance. The server flags it too, and its confirmation text deliberately
  does not thank anyone for their feedback.
- **Incident severity is derived from the taxonomy, never claimed.** A report
  naming a DEADLY species the app did not warn about is `dangerous_miss`
  whatever the wording; a dispute of a warning is `dangerous_false_alarm`,
  which is lower priority and never zero, because a warning nobody believes
  protects nobody. Nothing ever writes a report into the taxonomy.
- **The observation log stores `speciesKey`, not just the name.** Reports are
  graded by looking those up server-side. With names in place of keys every
  candidate is unrecognisable, and a disputed warning grades as a warning that
  never happened — the opposite classification.
- **`notes` is rendered verbatim to users.** Rationale, policy and review
  flags go in `internal_note`, which is never surfaced.
- **The ebook's field data is generated, never hand-copied.** The book and
  the app make the same claims about the same species, and two hand-kept
  copies drift. `scripts/build_ebook.py` fills the empty slots from
  `data/taxonomy.seed.json` and writes a *new* file: it never overwrites a
  slot that already has content, so the author's words survive a re-run, and
  it marks everything it writes plus a page banner, because a printed guide
  carries no `taxonomy_reviewed: false` the way `/health` does.
- **The book prints no taste.** `OMITTED_CHARACTERS` in the generator. The app
  can ask for a taste because the interrogation engine checks first that no
  deadly candidate holds mass (rule 5); a page cannot make that check, so
  "Taste: mild" under a bolete is an unconditional instruction to eat. The
  author's own `notes` may still mention one — that is their prose, rendered
  verbatim here exactly as the app renders it.
- **Most of the book's rows come back empty, and that is the taxonomy talking.**
  114 of 338 field rows fill. `character_states` holds only what separates a
  species from its lookalikes — it was built as a classifier tiebreaker, not
  as a field guide — so `habitat`, `season` and `smell` are thin. The run
  prints the per-row tally of what it left blank; that list is the review
  queue, not a bug. Filling it means the worksheet and a mycologist, not code.
- **The label space covers 30% of what people actually find.** 30 of the 100
  most-recorded British macrofungi (`python scripts/frdbi_gap.py`, over the
  full 17,536-taxon FRDBI export). That is the expected shape, not a failure:
  it was assembled around danger, not frequency. But it is the number to
  quote when someone asks why a common mushroom is not recognised.
- **Never add a common species without the dangerous thing it resembles.**
  The label space is a graph. Adding the field mushroom without the death cap
  makes the app *more* dangerous, not less: it teaches a name the model will
  reach for and withholds the one it should have refused over. `frdbi_gap.py`
  prints, for every candidate, the dangerous species already known in its
  genus, precisely so this is hard to forget.
- **FRDBI ranks host plants above every fungus.** It records associations, so
  beech leads the whole database at 124,946 — and cattle, horses and rabbits
  are in there too, because dung fungi are recorded against what produced the
  dung. A "top 100" taken without filtering is a list of trees.
- **Filtering happens at genus, and an unclassified genus counts as nothing.**
  `data/frdbi-genera.csv`. Eighteen thousand species cannot be judged by hand;
  a genus can be checked by somebody. The failure mode is silent, so two tests
  guard it: no unclassified taxon may out-record the hundredth macrofungus,
  and every genus in the label space must be classified `fungus` however rare
  it is. Cortinarius and Galerina were both unclassified on the first pass —
  the orellanine webcaps and the funeral bell.
- **Slime moulds are neither fungi nor hosts, and are photographed anyway.**
  Fuligo, Lycogala, Ceratiomyxa. They can never be identified here, so what
  the app owes them is the out-of-scope answer rather than the nearest
  mushroom — which makes them a free source of the negatives `ood.py` is
  otherwise short of.
- **Expect 50–70% species top-1** on a first training run, with genus accuracy
  notably higher. 95% means a leak.

## Related

A copy of this project also exists on the `claude/fungi-identification-ai-app-43w7xp`
branch of `mhawkes1/ibp-management-system`, kept as a frozen backup. **Do not
edit it** — this repo is the working copy. The IBP repo is an unrelated
school safeguarding system that happens to have hosted this project's first
commits.
