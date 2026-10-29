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

1. **Never make an edibility claim, in either direction.** No "edible",
   "safe to eat", "choice" — and equally no "inedible" or "not assessed as
   safe". This identifies mushrooms; it does not rule on meals. `toxicity`
   records a *hazard*: `DEADLY`, `SERIOUS` and `TOXIC` are shown, because a
   hazard the app conceals is worse than one it names, and
   `NO_RECORDED_TOXICITY` is **never rendered** — that species shows a name
   and nothing else.
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
| `data/taxonomy.seed.json` | 244 UK species, lookalike graph, toxicity, diagnostic characters, character states |
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
| `app/src/components/AppHeader.tsx` | Front-page header; `APP_NAME` lives here |
| `server/app/disclaimer.py` | What a user acknowledges before first use; the version is the text |
| `server/app/incidents.py` | Reports that the app was wrong, and how they are graded |
| `docs/INCIDENTS.md` | Who acts on a report, and in what order |
| `scripts/build_ebook.py` | Fills the companion ebook's field slots from the taxonomy |
| `scripts/demo.py` | Drives the real safety layer, engine and matcher in a terminal |
| `scripts/frdbi_gap.py` | Label space vs. how often things are actually found |
| `scripts/species_list.py` | Generates `docs/SPECIES.md`, the label space for a human to read |
| `scripts/evidence_audit.py` | Where evidence about a dangerous species works only one way |
| `docs/evidence-audit.csv` | Its 934 findings, worst first |
| `docs/frdbi-top-250.csv` | The 250 most-recorded macrofungi, ranked, for review (`frdbi_gap.py --csv`) |
| `docs/frdbi-top-300.csv` | The same to 300; 219 covered, 81 not |
| `data/frdbi-records.csv` | Every FRDBI taxon and its record count, exported 2026-09-22 |
| `data/frdbi-genera.csv` | Genus → fungus / micro / host / slime-mould / lichen, so the ranking can be filtered |

## Commands

```bash
# Tests — run these before any commit
python -m pytest ml/tests server/tests -q
cd app && npm test && npm run typecheck

# API (stub backend)
cd server && uvicorn app.main:app --reload

# Mobile client
cd app && npm install && EXPO_PUBLIC_API_URL=http://<lan-ip>:8000 npx expo start

# The client in a browser -- how the screenshots in docs/screenshots were taken
cd app && EXPO_PUBLIC_API_URL=http://127.0.0.1:8000 npm run web

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
- **A GBIF match above species rank must never become a taxon key.** GBIF's
  occurrence search is inclusive of descendants, so a genus-rank `usageKey`
  does not fetch nothing — it fetches *the whole genus* under one species
  label. `resolve_gbif_key` used to log a warning and return the key anyway,
  which would have filed every death cap in Britain as a blusher, with
  healthy-looking counts the whole way down and nothing downstream able to
  detect it: the images really are mushrooms. `judge_match` is now a pure
  function of the payload, refuses any rank but SPECIES, refuses FUZZY
  (fungal binomials differ by a letter or two across different species) and
  is tested offline.
- **The live API broke three things the offline tests could not.** Found on
  the first real run, 2026-09-23. (1) Every licence string carries a
  `/legalcode` suffix — 300 of 300 sampled — which the positional parser read
  as `version="legalcode"` and rejected, so the fetcher would have refused
  every image and raised "Manifest is empty — check taxon keys and network
  access", pointing at the network. (2) `identificationVerificationStatus` is
  absent from GBIF's iNaturalist export entirely, so the research-grade filter
  would have discarded the whole dataset while looking like quality control;
  it now rejects only an explicitly lower grade, and the research-grade
  property comes from iNaturalist's publication policy, which this code
  cannot verify. (3) *Helvella crispa* has four competing authorships, three
  DOUBTFUL, so `/species/match` falls back to `usageKey: 5` — the **Fungi
  kingdom** — at confidence 99. The rank check caught it; a confidence check
  never would have. Synthetic fixtures were wrong in exactly these ways.
- **A synonym key returns no occurrences, not fewer.** GBIF indexes
  occurrences against the accepted usage, so `judge_match` follows
  `acceptedUsageKey`. *Inocybe erubescens* (DEADLY) matched EXACT at
  confidence 100 to a key with **0** occurrences; its accepted usage
  *Inosperma erubescens* has 82. `UnresolvedDeadlySpecies` does not fire —
  the name resolved perfectly — so the species would have fallen below
  `--min-images` and left the label space in silence.
- **Following synonyms can merge two of our species onto one key.**
  `CollidingTaxonKeys`. GBIF treats *Clitocybe dealbata* as a synonym of
  *C. rivulosa*, and *Inocybe lilacina* as a synonym of *I. geophylla*, while
  this taxonomy carries all four separately — two of them DEADLY. Downloaded
  together, every image is filed under both labels: silent label noise the
  risk-weighted objective cannot see. The build refuses. It is a taxonomy
  question, not a download one.
- **Never pass `--country GB`.** It is the intuitive choice for a British app
  and it wrecks the dataset. Measured: zero images for *Clitocybe rivulosa*,
  *Cortinarius orellanus* and *Tricholoma pardinum*, one for *Entoloma
  sinuatum*, against 38–171 globally; *Amanita phalloides* 309 vs 8,617; 52
  species below `--min-images 40`. A death cap photographed in France is the
  same fungus, and the geographic prior comes from the metadata branch.
- **`image_source: "danish_atlas"` replaced `"any"` for three species on
  2026-10-19, and it is a *restriction*, not a widening.** *Lepista nuda*
  (1,142 Danish images against 0 on iNaturalist), *Clitocybe rivulosa* (329,
  DEADLY) and *Amanita vaginata* (227). The photographs were already coming
  from the Danish atlas -- `any` reached them by dropping the dataset filter
  entirely, so they arrived with no stated determination standard attached.
  Naming the dataset recovers one: the Danish Mycological Society publishes a
  verification process (peer agreement weighted by recorder track record, then
  confirmation by the atlas's experts), which is more than `any` ever had.
  *Exidia thuretiana* and *Neoboletus luridiformis* have zero images there too
  and stay on `any`; neither is dangerous, and a test now asserts no DEADLY or
  SERIOUS species is left on an unnamed source.
- **A null `dataset_key` no longer means "not iNaturalist".** It means `any`.
  `SpeciesQuota.source` carries the name, because `if quota.dataset_key` cannot
  tell a third named source from no source at all -- the run log had been
  inferring exactly that.
- **The Danish records put the photographer one level down, and CC BY-NC needs
  a credit.** Their occurrence `rightsHolder` is null on every record sampled;
  the name is on the *media* record as `rightsHolder` and `creator`. Reading
  only the occurrence, as the code did, filed 1,995 CC BY-NC images with nobody
  to credit -- a licence breach rather than a cosmetic gap. `_attribution`
  falls back media-then-occurrence and returns None rather than an empty
  string, so a genuinely missing credit stays visible in the manifest.
- **`image_source` is per species, and defaults to iNaturalist.**
  *Clitocybe rivulosa* has 11,661 GBIF occurrences and 1,068 with images and
  **zero** in the iNaturalist dataset — iNat observers do not identify to it.
  Martin's decision, 2026-09-23: keep the ivory funnels separate and source
  them elsewhere, so both carry `image_source: "any"`, which drops the
  `datasetKey` filter for those two alone. Everything else keeps it, because
  the research-grade property comes from iNaturalist's publication policy and
  widening trades it away. The manifest records `dataset_key` per image so
  the difference stays visible rather than averaging out.
- **Both collisions were resolved by DROPPING one side, not by pinning.**
  This entry used to say the opposite — that *Clitocybe dealbata* → 2531056
  and *Inocybe lilacina* → 3331644 were pinned to their own usages so both
  halves of each pair survived. Checked against the file on 2026-10-27 while
  the first real dataset was building: **neither species is in the taxonomy,
  and the only pinned `gbif_key` in all 244 entries is *Helvella crispa* →
  2554614.** So the ivory funnels are represented by *C. rivulosa* alone
  (DEADLY) and the fibrecaps by *I. geophylla* alone. The collision cannot
  recur because there is nothing left to collide.
  That is a defensible resolution and a different one from what was written
  down, and the difference matters to a reviewer: the label space now
  **follows GBIF's synonymy** on both pairs rather than splitting against
  it. If a mycologist says the British field guides are right to treat them
  as four species, re-adding two of them is the change — and `frdbi_gap.py`
  ranks *Inocybe lilacina* at 2,883 records, missing, with two dangerous
  species already in its genus.
- **Six species have ZERO iNaturalist images, and it is not a key problem.**
  *Lepista nuda* (6,773 images elsewhere), *Amanita vaginata* (2,354),
  *Exidia thuretiana* (645), *Clitocybe rivulosa* (1,068), *C. dealbata*
  (233), *Neoboletus luridiformis* (119). All resolve to ACCEPTED
  species-rank keys; faceting iNaturalist's own records by species under
  *Lepista*, *Collybia*, *Clitocybe* and *Amanita* finds none of them. The
  likely reason is that iNaturalist carries these as **species complexes**
  ("*Amanita vaginata* group"), and a complex has no species-rank record to
  export. That is worth noticing rather than routing around: these are
  species the largest fungal photo community in the world declines to
  identify to species level, which is the same judgement this app's
  `dangerous_group` verdict makes. All six carry `image_source: "any"`.
  Check for this symptom whenever a species comes back with no images —
  `scientificName` on the occurrence API is unreliable (it returns nothing
  for *Amanita phalloides*, which has 8,617 by key), so diagnose with
  `taxonKey` and facets.
- **`image_source: "any"` means images come from arbitrary hosts.** The ivory
  funnels' photographs live on `svampe.databasen.org`,
  `mushroomobserver.org` and `www.artsobservasjoner.no`, none of which a
  restricted network policy allows by default. On the first live sample run
  all 24 of their images failed and `fetch_images` reported "Retained 59 of
  83" and carried on — two DEADLY species had silently left the dataset. It
  now names the failing hosts and raises an ERROR listing any species that
  lost every image; a test pins that.
- **Resolution is a reviewable artefact, not a step.** `--resolve-only`
  writes `data/gbif-keys.json` with every match and every refusal's reason.
  Run it before the download: it takes a minute, and it is the point where a
  name silently becomes the wrong fungus. A refusal is fixed by setting
  `gbif_key` on the species by hand, having checked the key.
- **An unresolved DEADLY species stops the build.** `UnresolvedDeadlySpecies`.
  Dropping it is not a smaller dataset, it is a hole in the safety layer — a
  species the model cannot name is one the app cannot warn about, and every
  lookalike edge pointing at it goes slack.
- **The quota is counted in images; the split is counted in observations.**
  So `max_images_per_observation` (default 4) is what stops a species
  reaching a 400-image target off twenty fruiting bodies. `--min-observations`
  reports species that clear `--min-images` on photographs of the same few
  records; their validation score says almost nothing.
- **Splits are on `observation_id`, never on image.** If accuracy looks too
  good, check this before believing it.
- **`character_states` is complete for all 244 species and UNREVIEWED
  throughout.** Derived from the taxonomy's own `notes`, not from a
  mycologist, except for the dangerous 21 above. Complete is not reviewed:
  `reviewed_by` is still null and `/health` still reports
  `taxonomy_reviewed: false`. The remaining 1,104 rows are the review left.
- **Describing a species makes it *dismissable*, never easier to confirm.**
  An undescribed species gets likelihood 1.0, so it already drifts upward
  whenever a rival is contradicted — "a consistent answer never boosts"
  cuts both ways. Measured on *Entoloma sinuatum*'s missing `gill_colour`:
  a confirming "yellow gills" answer took it 30% → 45.3% both before and
  after it was described, identically. What changed was the *contradicting*
  answer — "brown gills" left it at 45.3% before and takes it to 24.9%
  now. I first wrote this up the other way round, as though describing it
  had unlocked the confirmation; the numbers say otherwise.
- **"Both halves described" applies per *character*, not per species, and a
  missing character is invisible.** `gill_colour` was simply absent from
  *E. sinuatum*'s `diagnostic_characters`, so the worksheet never emitted a
  row to leave blank — an absent character looks like nothing rather than
  like a gap. `python scripts/evidence_audit.py` now finds these; run it
  after adding a dangerous species.
- **The audit's headline is that nothing is stranded.** All 201 dangerous
  lookalike edges share at least one character described on both sides, so
  the engine can always separate them; a test pins it. The ~900 one-way
  asymmetries it also reports are a depth backlog, not holes — each is a
  pair that is already resolvable by some other character. That also puts
  *E. sinuatum*'s gap in proportion: it was one of 507 of the same shape,
  not a unique fault. `Clitocybe rivulosa`, `C. dealbata` and
  `Galerina marginata` head the backlog.
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
- **The catalogue gained nine options on 2026-10-12, and what that bought
  is *dismissability*, not identification.** Martin's review found twelve
  rows holding a state the options could not express — soap and coconut
  smells, dark red latex, larch, a punctate stem, black bruising, pink and
  black caps, violet gills, cinnamon pores — so those rows were blank or
  forced onto the nearest wrong value. Adding the options does **not** mean
  a matching answer now confirms the species: a consistent answer never
  boosts, and the rivals are mostly undescribed for these characters, so
  "Larch" against the other boletes moves nothing at all. What changed is
  that a *contradicting* answer can now rule them out, where before no
  answer could touch them. *Suillus grevillei* on an oak answer: 34% →
  11%. Two tests pin it.
- **Adding an option contradicts every species that does not list it.**
  Which is the dangerous direction for a DEADLY species, because the
  existing lists were written against the old option set.
  `Larch` would have pushed *Cortinarius rubellus*, *Tricholoma equestre*
  and *T. terreum* down for growing where they do in fact grow; `Pink` and
  `Violet or lilac` would have done it to *Inocybe geophylla*. Six lists
  were widened to compensate, marked `claude-option-widening` rather than
  attributed to Martin, and a test asserts each one carries the new option.
  **Check this before adding any further option.**
- **Two of the twelve were declined on purpose.** `Hazel`, because
  "Mixed broadleaf" already covers it and adding single broadleaf trees as
  peer options turns that catch-all into something a hazel answer
  contradicts. And `Moderately spaced` on `gill_spacing`, because a middle
  bucket in a binary a non-expert cannot judge reliably would create a
  contradiction channel against *Clitocybe rivulosa* — DEADLY, listed
  `Crowded` — for no identification gain. *Lactarius pyrogalus*'s row stays
  blank instead.
- **Some answer options are non-observations, not states.** `volva`'s "I cut
  it off" and `cortina`'s "Can't tell" are in `uninformative_options` and get
  a likelihood of 1.0. Without that, the commonest field mistake — cutting the
  stem base off — would have pushed the death cap from 0.50 to 0.355 against a
  field mushroom. Any new option meaning "I could not look" must be added
  there; a test asserts no committed state is one.
- **Filling the table is a worksheet job, not a code job.** `python
  scripts/character_states.py emit` writes `docs/character-states-worksheet.csv`
  (1,215 rows, deadliest first, and it preserves answers already in the sheet);
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
- **The book cover was the front page until 2026-09-29, and is not any
  more.** Martin asked for the photograph off the first screen.
  `CoverHeader.tsx` and `assets/cover.jpg` are gone, replaced by
  `AppHeader.tsx`: serif title, the book's gold rule, tagline, and the
  emergency button. What mattered about the removal is what had to survive
  it — **the emergency route was pinned to the cover's top corner** because
  it is the one control that must never need a scroll, and deleting its
  host is exactly how an app silently loses its panic button.
  `app/test/emergencyRoute.test.ts` now guards it at the source level,
  because vitest cannot drive the RN renderer.
- **The app is `Funga`; the book stays *What's That Mushroom?*** Martin's
  call, 2026-10-27, after checking the UK register himself. *Funga* is the
  fungal counterpart to flora and fauna, proposed in the mycological
  literature around 2018 and pushed since by the IUCN among others toward
  "fauna, flora and funga" — so it reads, to the exact people whose review
  is blocking release, as someone who has read their literature. Two
  practical reasons it beat the alternatives. **Five characters against
  twenty**, where a home screen label truncates at about twelve: the old
  name read `What's That M…` under the icon forever. And it **promises
  nothing** — every other candidate (FungID, MycoID, Fungi Finder, Mushroom
  Finder) said "we will tell you what this is", which is the one thing this
  app refuses to do, so the name would have needed walking back on the first
  screen it appeared on. *My Mycologist* was rejected outright: claiming to
  be a mycologist while no mycologist has reviewed the taxonomy is the
  over-claim the product exists to reject.
- **The name is written in two places, not one, and the second is the one
  users see most.** `APP_NAME` in `AppHeader.tsx` is the in-app title;
  `expo.name` in `app/app.json` is the **home screen label**, and nothing
  keeps them in step. Change both. The tagline beside `APP_NAME` now carries
  the work the name used to do — "Funga" tells a beginner nothing about
  mushrooms, which is the accepted cost, paid for by the tagline in the app
  and the subtitle in the store.
- **`slug`, `package.json` name, the bundle identifiers and the dataset
  builder's `USER_AGENT` were deliberately left as `whats-that-mushroom`.**
  They are infrastructure identifiers no user reads, and changing a slug
  breaks the Expo project link.
- **The bundle identifiers are `uk.co.funga.app`, and deliberately not
  `com.funga.*`.** Changed 2026-10-27, which was the last free moment: a
  bundle id is permanent once published to either store. Reverse-DNS
  convention says use a domain you control, and `funga.com` belongs to
  Funga PBC, a US forestry startup -- taking their namespace would be
  squatting and invites an argument that costs more than a domain.
  `funga.co.uk` is the one to register, and registering it is what makes
  this identifier honest rather than merely unused.
- **The title's typeface is loaded but never awaited.** `useFonts` reports an
  error as well as a loading state, and a front page that will not render
  because a font did not arrive is worse than a title in the platform serif.
  `theme.cover.display` names the family; React Native falls back on its own.
  `theme.cover` keeps its unused values (`ground`, `byline`, `displayItalic`)
  because the ebook generator shares them.
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
- **The label space holds all 200 of the most-recorded British macrofungi,
  plus the twelve from the top 300 whose genus already held something
  dangerous.** 244 species, 135 lethal pairs. `frdbi_gap.py --top 300` now
  runs; the genus table was extended for it. The skeleton is still the danger
  graph; frequency filled it in.
- **The grisette is why the twelve were added.** *Amanita vaginata* has a
  clear white volva and no ring, so "a bag at the base means danger" — the
  first rule anyone learns about *Amanita* — is wrong about it, and the
  label space had no name for it at all. Demo scene 8: the engine asks about
  the ring, not the volva (all three candidates have a volva, so it
  separates nothing), "No ring" moves it 44% → 57%, and the verdict stays
  `dangerous_group` because a deadly candidate still holds 23.6%. Rule 3 is
  not a threshold on the leader.
- **Raising a species' toxicity can invalidate the width of its state
  lists.** *Tricholoma terreum* and *Entoloma rhodopolium* went TOXIC →
  SERIOUS on 2026-09-23 (Martin's call, both had been flagged here as open
  review questions). Their lists had been written **tight**, because the
  convention makes lists tight for the safe half of a pair — which they were
  no longer. *E. rhodopolium* listed only `Pink` gills when *Entoloma* gills
  are pale before the spores mature, so a young one would have contradicted
  itself and pushed a SERIOUS species down. Widened. The contradiction tier
  moves on its own (`SERIOUS_INCONSISTENT` 0.40 rather than `INCONSISTENT`
  0.25); the list width does not, and has to be revisited by hand.
- **All twelve were added as the non-deadly half, so their state lists are
  tight.** They exist to give the mass somewhere accurate to go inside a
  genus whose dangerous members were already there and, in several cases,
  were the genus's *only* members: every small tawny *Galerina* was a funeral
  bell, every common webcap was an orellanine one.
- **244 species is a much bigger training problem than 79.** The 50–70% top-1
  expectation below was set for a label space a third of this size and is now
  optimistic. Many of the additions are separable only under a microscope
  (the two Crepidotus, the two Ganoderma) or are resupinate crusts with no
  cap, gills or spore print for the interrogation engine to ask about. That is
  a reason to watch risk-weighted error rather than accuracy, which is rule 6
  anyway.
- **`scripts/demo.py` hands its rankings in, so it does not notice the label
  space changing.** Tripling it from 79 to 235 left the output byte-identical,
  because no scene asks the taxonomy how big it is. If a change ought to show
  up there, add a scene that exercises it — scenes 7 and 8 exist for that.
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
  guard it: no unclassified taxon may out-record the `GUARDED_DEPTH`th
  macrofungus, and every genus in the label space must be classified `fungus`
  however rare it is. Cortinarius and Galerina were both unclassified on the
  first pass — the orellanine webcaps and the funeral bell.
- **`GUARDED_DEPTH` must track the depth actually in use.** It sat at 100
  while the working depth was 250, and eight unclassified taxa were sitting
  above the 250 cutoff the whole time — four of them real macrofungi (dog
  stinkhorn, beech tarcrust, leafy brain, conifercone cap). The test passed
  throughout. A guard shallower than the working depth reports on somewhere
  nobody is standing.
- **The top 250 says what to add; the danger graph says what cannot be
  dropped.** 208 of the label space's 244 are in FRDBI's top 250; the other
  36 are too rarely recorded to reach it, and **9 of the 10 DEADLY species
  are among them** — only the death cap makes the ranking. A label
  space trimmed to the top 250 would hold the field mushroom without the
  destroying angel and honey fungus without the funeral bell. Rarity is
  part of why those species poison people.
- **Nothing that writes a toxicity into a file may use `.value`.**
  `Toxicity` is an `IntEnum` with DEADLY 4 and NO_RECORDED_TOXICITY 1, so
  `.value` in a spreadsheet is an unlabelled 1–4 scale whose dangerous end
  reads like the good one. `.name` everywhere.
- **A report must not reassure past its own warning.** `frdbi_gap.py`
  correctly printed that eight unclassified taxa out-recorded the cutoff and
  then, forty lines later, printed a hardcoded "All below the cutoff, so none
  of them belongs in the top N". The `--csv` output now refuses to write at
  all while intruders exist: a spreadsheet outlives the terminal warning it
  came with.
- **Lichens are a fourth kind, added at `--top 300`.** *Xanthoria parietina*
  is recorded 1,443 times and is on every churchyard wall in Britain. It is a
  fungus with no cap, no gills and no spore print, so calling it a macrofungus
  would put it in a list of species to add, and calling it a leaf spot would
  be false. Same argument as slime moulds, same out-of-scope answer, same free
  source of OOD negatives. *Lichenomphalia* is the edge case and goes the
  other way — lichenised, but what it puts up is an omphalinoid mushroom with
  a cap and gills.
- **`INEDIBLE` became `NO_RECORDED_TOXICITY`, and stopped being rendered.**
  Refusing to say "edible" was only half of rule 1: "Not assessed as safe"
  was still a safety verdict, attached to 157 of the 244 species, and the
  app cannot see what the user is holding in either direction. Silence
  cannot be misread as an endorsement, cannot be misread as a warning, and
  cannot be disputed — which is the liability argument as well as the honest
  one. The value still exists because the risk matrix, the dangerous-pair
  logic and incident grading all need it;
  `test_no_user_facing_path_makes_an_inedibility_claim` pins both halves,
  including that the category has not quietly disappeared.
- **Slime moulds are neither fungi nor hosts, and are photographed anyway.**
  Fuligo, Lycogala, Ceratiomyxa. They can never be identified here, so what
  the app owes them is the out-of-scope answer rather than the nearest
  mushroom — which makes them a free source of the negatives `ood.py` is
  otherwise short of.
- **Expect 50–70% species top-1** on a first training run, with genus accuracy
  notably higher. 95% means a leak.
  **Measured 2026-10-27: 87.9% top-1, 97.4% top-5.** The band above was
  written pessimistically and the first real run cleared it by twenty
  points. `scripts/check_splits.py` came back clean on the manifest that
  produced it -- no observation, image URL or file in two splits -- so it is
  not the leak the 95% line warns about. A ViT-Base pretrained on
  ImageNet-21k, fine-tuned on 244 visually distinctive species, simply does
  better than the note assumed.

## Related

A copy of this project also exists on the `claude/fungi-identification-ai-app-43w7xp`
branch of `mhawkes1/ibp-management-system`, kept as a frozen backup. **Do not
edit it** — this repo is the working copy. The IBP repo is an unrelated
school safeguarding system that happens to have hosted this project's first
commits.
- **The client had never been rendered until 2026-10-19, and three things were
  broken that no test could see.** Every one was invisible to vitest, which
  cannot drive the RN renderer, and to the Python suite, which never loads the
  client. (1) `expo-font@57.0.4` against Expo SDK 51 threw
  `registerWebModule is not a function` before the first frame — the version
  Metro had been warning about on every start. (2) `Alert.alert` with buttons
  is native-only, so `chooseSource` was a no-op in a browser and every photo
  slot was dead. (3) `appendPhoto` sent React Native's `{uri, name, type}`
  FormData shape, which a browser stringifies to `"[object Object]"`, so the
  upload failed in a way the server reads as a malformed request rather than a
  missing file. The lesson is the obvious one: a suite that is green on a
  client nobody has launched is green about something else.
- **`docs/screenshots/` is generated by driving the real client**, not mocked
  up — Playwright against `npm run web` with the stub backend, which is why
  the species names in it are meaningless and the refusal logic around them is
  not. Regenerate rather than edit. Two gotchas if you do: react-navigation
  keeps earlier screens mounted but hidden, so a text selector must filter on
  `isVisible()` or it resolves to a twin on a previous screen; and
  `fullPage: true` stops at the viewport because React Native Web scrolls an
  inner container rather than the document, so the viewport has to be made
  tall enough for the whole screen and the result trimmed.
- **Every `Pressable` now declares an `accessibilityRole`**, and
  `app/test/accessibility.test.ts` keeps it that way. Eleven of thirty-six
  were missing one — the primary action on the field-notes screen, the
  "I can't tell / skip this" control, and *every* control on the spore print
  screen, which is the flow that asks a user for twelve hours. Without a role
  the control is readable but not announced as activatable, and it is skipped
  by element-type navigation.
  **The first audit of this said 31, and that was wrong.** A regex scanning
  to the first `>` ends the tag at the `>` inside `onPress={() => …}`, so it
  reported controls that *do* declare a role. The test tracks brace depth.
  Any future count of JSX attributes has the same trap in it.
- **Rule 1 reaches the consent text, and a test did not.**
  `test_no_user_facing_path_makes_an_inedibility_claim` scans what `assess`
  returns, which is where `INEDIBLE` used to surface. It never read
  `disclaimer.py`, where "the strongest thing it says about any species is
  that the risk has not been assessed" survived the September purge — a soft
  edibility verdict in the most-read text in the app, shown to every user
  before first use. `test_the_disclaimer_makes_no_inedibility_claim_either`
  now covers it across all eight service states.
- **The palette went from near-black to paper on 2026-10-19, and inverting it
  broke every primary button at once.** Screens wrote
  `color: theme.colour.background` for the label on a filled gold button,
  which was only ever correct because the background happened to be
  near-black; on paper each one turned cream on cream. `onAccent` and
  `onDisabled` now name the role instead of borrowing a colour. The same
  inversion also made the *no-hazard* candidate stripe darker than a TOXIC
  one — it fell through to `textMuted` — so the species the app has nothing
  to say about was the loudest thing in the list. `app/test/theme.test.ts`
  pins the emphasis ordering and the contrast ratios, including AAA (7:1)
  for `danger` on every ground it appears on: the dark theme's `#e5484d`
  reads at about 3:1 on paper, so the warning that matters most would have
  been the hardest thing on the screen to read.
- **Green is chrome, never a verdict.** `POSITIONING.md` kept green out of
  the palette altogether because green is the colour of permission. The light
  theme brings woodland greens back for the header ground and the
  how-to-photograph advice, and bars them from anything that names a species
  or states an outcome. A hue test in `theme.test.ts` fails on any new
  palette colour that is dominantly green and not declared chrome, which is
  how `confident` — a teal-green meaning "reasonably confident in the
  identification" — was caught and replaced with slate blue.
- **`POST /incident` is rate limited, and a medical report is never limited.**
  `server/app/ratelimit.py`, five an hour per client by default. A report
  declaring that someone ate it or is unwell bypasses the limiter entirely,
  is not counted against the ordinary quota, and so cannot lock the reporter
  out of filing the defect report afterwards. The check reads the request's
  own flags rather than the triaged severity, so it happens before any work.
  A limiter that silently discarded those would turn the one route that must
  always work into the one that fails under exactly the conditions that
  produce a flood. Six of the thirteen tests are about that exemption.
  Two deliberate limitations, written down so they are not read as
  oversights: the counter is in memory, so more than one worker makes the
  limit `n_workers x limit`; and `X-Forwarded-For` is ignored unless
  `WTM_TRUST_FORWARDED_FOR` is set, because a caller-supplied header would
  hand anyone a fresh quota while reading as protection.
- **A refused attempt is not counted.** Otherwise a buggy client in a retry
  loop holds itself out forever, which punishes the broken caller far harder
  than the malicious one — who simply changes address.
- **`server/tests/conftest.py` resets the limiter between tests.** Without it
  the eighth test in a module to file a report fails because the third one
  spent the allowance, and the failure moves whenever tests are reordered. It
  resets rather than disables, so a test filing more reports than a real
  client would still meets the limit.
- **The client shows the server's `detail`, not the raw body.** `handle` in
  `api.ts` used to render `Request failed (429). {"detail":"..."}`. On the
  report screen that message is the one telling a frightened person how to
  get through, so the JSON around it is not acceptable noise.
- **`accepted_name` records a synonym without displaying one.** Nine species
  carry a name both the GBIF backbone and Species Fungorum Plus call a
  synonym — *Inocybe erubescens*, DEADLY, among them. Martin's call,
  2026-10-19: keep displaying the familiar name, which is what the British
  field guides and the companion book use and the one a beginner can look up,
  and record the accepted one alongside so the data is not quietly wrong.
  **"Alongside" means invisible.** Showing a user two names for one mushroom,
  in an app whose job is reducing confusion, is the opposite of the point —
  and it would put a name beside a species that no identification here was
  made against. Same mechanism as `internal_note`: the loaded `Species` never
  carries it, pinned at both the object level and the HTTP level. The
  training data is unaffected either way, because the fetcher resolves
  through `acceptedUsageKey` and already downloads the accepted taxon.
  A test keeps the field in step with `docs/nomenclature-check.csv`, since
  the CSV is regenerated against GBIF and the field is written from it by
  hand; and another refuses an `accepted_name` equal to the name already
  shown, because a synonym of itself reads to a reviewer as a checked name.
- **One of the nine is not routine, and is for the reviewer.**
  *Russula nigricans* is a synonym of *R. adusta* in both sources, while
  British field guides treat the blackening and winecork brittlegills as two
  species — so the fetcher is currently filing *adusta* images under this
  label. Deliberately not resolved: accept the merge, split by pinning
  `gbif_key` as the ivory funnels were, or leave it. Neither is dangerous, so
  it is data honesty rather than safety. `docs/SPECIES.md` asks for a view on
  it under "Names the nomenclators have moved".
- **The training config had ten keys nothing read, and was missing two the
  code does.** Audited 2026-10-19 before the first paid GPU run;
  `ml/tests/test_config.py` now checks both directions, because neither
  failure shows up in a run that completes successfully.
  The misleading ones: `mixup_alpha: 0.2` and `cutmix_alpha: 1.0` sat there
  for months while the training loop used hard targets throughout, so anyone
  reading the file would conclude the model had seen augmentation it has
  never seen — `losses.SoftTargetRiskLoss` is written and **nothing calls
  it**. They are 0.0 now, with the allowlist in the test carrying the reason.
  The duplicated ones: `min_images_per_class`, `max_images_per_class`,
  `val_fraction`, `test_fraction` and `split_on` are decided by
  `fungi_ml.data.prepare`'s own CLI flags, not here. The values matched
  prepare's defaults, so the mirror was invisible — editing one here would
  silently have had no effect. `eval.topk` was the same trick:
  `evaluate.py` takes `(1, 3, 5)` as a function default and no caller passes
  the config value.
  **The two that were missing matter more.** `train.risk_strength` is what
  makes the model different from an ordinary classifier, and `train.py` read
  it with a `.get(..., 1.0)` fallback, so nobody tuning a run ever saw it.
  `data.taxonomy` likewise, defaulting to a relative `../data/...` that only
  resolves because the documented command is run from `ml/`.
- **Checkpoint selection really is on risk, not accuracy.** `best_risk` /
  `metrics["risk"]` in `train.py`, asserted by a test that also refuses
  `best_acc`. `output.save_top_k` was removed rather than implemented: a
  top-k selected on the wrong metric is a footgun, not a feature.
- **A colour that is not a token escapes every contrast test.**
  `SporePrintScreen` set a patch label's background to a hardcoded
  `rgba(0,0,0,0.6)` with `theme.colour.text` on top. Correct while the
  palette was near-black; near-black ink on a near-black scrim the moment it
  went to paper — invisible, on the labels telling a user which box holds the
  spore deposit and which holds the white card. `theme.test.ts` now fails on
  any colour literal outside `theme.ts`, which is the only way the palette
  stays a one-file change.
- **`photoScrim` is dark in every palette, because what is under it is not
  themed.** It dims a user's photograph so a label can be read against
  whatever they happened to photograph, so text on it is `onAccent` and never
  `text` — asserted, in both directions.
- **A reporter is told what happened without anyone storing their address.**
  `GET /incident/{id}`; the reference is the whole credential. That is the
  privacy answer as much as the engineering one — writing to people later
  means holding personal data on somebody whose only involvement was telling
  us we were wrong. The response carries an outcome and a note a person wrote
  and nothing else: no free text of theirs, no contact, no species, nothing
  about any other report, because a uuid4 is unguessable but is exactly the
  sort of string people paste into a forum.
- **An outcome is appended, never written over the report.** The log is
  evidence, and that applies to the outcome too: a status quietly changed
  from `fixed` to `no_change` is the record nobody could trust. Status is a
  fold over every line for an id. `IncidentStore.all()` filters on the
  *update* marker rather than a report one, because lines written before
  updates existed carry no `record_type` and a positive test would have
  silently dropped every historical report.
- **A `medical` report is never shown a ticket state**, and
  `scripts/incidents.py answer` refuses to touch one. "Investigating" shown
  to somebody who said their child had eaten something is the same mistake as
  a confirmation that thanks people for their feedback.
- **`scripts/incidents.py list` sorts worst first, then oldest first.** A
  newest-first queue buries the report that has been waiting longest, which
  is the one most likely to be the one you are failing.
- **`./scripts/try_it.sh` is one command from a fresh clone to the app in a
  browser.** It exists because the project had instructions for running each
  piece and nothing that ran the whole thing — and because every screenshot
  in `docs/screenshots/` was produced by a machine driving the app, which is
  not the same as anybody having *used* it. A safety argument you have only
  read is one you have not checked. That gap is what let three fatal client
  bugs sit behind a green suite for months.
- **The launcher is `scripts/try_it.py`, not the `.sh` beside it.** The bash
  version came first and quietly assumed macOS or Linux — Windows has no bash
  unless you install one, and the person this was written for is on Windows
  and has never opened a terminal. Python is already a hard requirement, so
  the launcher may as well be written in it. Two Windows details the shell
  version hid: `npm` is a `.cmd` shim that `subprocess` will not find bare,
  and `sys.executable` is the only reliable way to re-enter the interpreter
  that is actually running.
- **`docs/walkthrough.html` is a *recording*, not a demo, and that was the
  whole decision.** Martin is on Windows and has never opened a terminal, so
  he asked whether the app could be shown through a link. Three options: a
  mock-up, a JavaScript reimplementation of the safety layer, or a recording
  of real responses. The reimplementation is the tempting one and the worst —
  two copies of the one piece of code this project cannot afford to get
  wrong, drifting apart silently. A recording cannot drift; it can only go
  stale, and it stamps its own capture date so you can tell.
  `scripts/capture_walkthrough.py` hits a running API (start it with
  `scripts/try_it.py` first) and writes every response verbatim to
  `docs/walkthrough.json`; `scripts/build_walkthrough_page.py` slims that into
  the page's single JSON block. Same arrangement as `build_ebook.py`, same
  reason. **Regenerate both after anything that changes what a user reads** —
  a trained model, a disclaimer edit, a toxicity change — or the page is
  showing last month's app over this month's claims.
- **The page's chrome is themed and the phone inside it is not.** `--app-*`
  tokens are copied from `theme.ts` and are never redefined under
  `prefers-color-scheme: dark`, because the app is paper in every palette and
  a dark mock-up is a picture of something that does not exist.
- **It renders rule 1 rather than describing it.** No hazard line appears on a
  `NO_RECORDED_TOXICITY` row — the slimmer passes the enum *name* through and
  the page's `HAZARD` map simply has no entry, exactly as `hazardLabel` has
  none. If a future edit adds one "for completeness", that is the rule broken
  on the most-shared surface the project has.
- **The follow-up section exists because the honest result was the
  surprising one.** Answering the `dangerous_group` question lifts the
  refusal to `uncertain` on all four answers *and* moves the destroying angel
  **up**, 24% to 26–27%, with the deadly warning still on screen. The pair
  partner was contradicted, so the mass had to go somewhere. Showing only the
  verdict improving would have been the flattering half of a true thing.
- **The production mark is `docs/logo/funga-mark.svg`, written by
  `docs/logo/mark.py`.** Martin's round-five outline, picked 2026-10-27,
  with exactly one stroke removed. `python scripts/build_icons.py` derives
  `app/assets/{icon,adaptive-icon,splash-icon,favicon}.png` from it and
  nothing is touched by hand, for the same reason the ebook's field data is
  generated -- a set kept by hand drifts, and the drift shows up as a
  slightly different mushroom in the one place a user looks every day.
- **The stem is an *open* path, and reclosing it puts a line back across the
  mushroom.** A closed stem draws its own top edge as a straight line
  spanning the stem, hidden under the cap -- Martin spotted it in the
  rendered 1024 icon. Dropping the `Z` leaves an open U; the geometry is
  otherwise untouched, every control point original. Two follow-ons that
  only show at large sizes: the open ends moved from y=290 to y=292, the cap
  underside's own centreline, so each sits mid-stroke rather than just
  inside its lower edge; and they take a **butt** cap, the only ones in the
  drawing, because a round cap is a half-disc of radius 15 that bulged below
  the cap as a nub on each side. `app/test/icons.test.ts` pins the cap
  closed, the stem open and the butt cap present.
- **That fix is invisible at icon sizes**, checked with `truepx.py`: at a
  true 29 and 16 px the before and after are indistinguishable, because the
  offending line sat under the cap's own stroke. It matters at 1024, on a
  website and in print, which is where it was noticed. Do not take "looks
  identical in the app" as a reason to undo it.
- **Four things about icons that fail late, so `app/test/icons.test.ts`
  checks them now.** A missing asset stops an Expo build. **An alpha
  channel on the iOS icon is rejected by App Store Connect at upload**,
  after a build has been made, so `icon.png` is flattened to RGB and the
  test reads the PNG's IHDR colour-type byte to prove it. The Android
  foreground must *keep* its alpha, because the launcher composites it over
  `adaptiveIcon.backgroundColor` and a flattened one paints its own square
  through the mask. And both backgrounds are `#f6f3ea` rather than white:
  the mark is drawn on paper, and a white plate shows as a ring of the
  wrong cream once a launcher masks to a circle.
- **The Android foreground is drawn smaller than the iOS icon on purpose.**
  An adaptive icon is 108dp of which the central 72dp is visible and only a
  66dp circle is guaranteed, because the launcher picks the mask. Content
  sits inside about 58% of the canvas against the iOS composition's 62%. It
  looks undersized in a file browser and correct on a phone.
- **The mark is not centred in its own viewBox**, and composing icons
  without checking that is how everything ends up hanging low on every
  platform at once. Its ink box centres at (257, 288) against a canvas
  centre of (256, 256) -- 32 units low. `build_icons.py` measures the box in
  a browser, adds half a stroke on each side because `getBBox` ignores
  stroke, and recentres.
- **A comparison sheet lies about small sizes, and it fooled me.** Every
  logo sheet is screenshotted at deviceScaleFactor 2 or 3, so a tile
  labelled "29" is really 58 or 87 device pixels -- flattered four to nine
  times in area. On that evidence I reported that the round-five outline
  clogged at 29 px and spent a round rescuing it. It does not clog, and the
  rescue (merging cap and stem into one path) was a regression that removed
  the cap's full-width underside and turned the mushroom into a tree.
  `python docs/logo/truepx.py <mark>...` renders at one device pixel per CSS
  pixel and magnifies with nearest-neighbour. **Judge any small size with
  that, never with a sheet.**
- **The palette was reviewed on 2026-10-27 and deliberately not changed.**
  Martin liked **A (current, shipping)** and **B (deep chrome)** and chose
  to leave `theme.ts` alone for now, so `scripts/palette_variants.py` is a
  shortlist rather than a proposal. B is the one to reach for: same paper,
  but the header band is painted with solid `canopy` and cream on it rather
  than the pale `canopySurface` tint. Applying it is a `theme.ts` edit plus
  the header's ground, and the variants script scores any change against
  the real rules first -- `python scripts/palette_variants.py` then
  `python scripts/palette_sheet.py`.
- **Darkening `canopy` alone changes almost nothing a user sees.** The band
  on screen is `canopySurface`, the pale tint; `canopy` is a rule and
  divider colour. The first comparison sheet rendered the current palette
  and the "darker greens" one as near-identical and I read that as a result
  rather than a bug. Any future "make it greener" asks which of the two it
  means.
- **Inverting to a dark palette re-creates the October emphasis bug by
  itself.** On paper, heavier means darker; on a dark ground it means
  *lighter*. A deadly red of `#ff9a92` scores 7.86 against the dark surface
  while a toxic amber scores 9.11, so the TOXIC row draws heavier than the
  DEADLY one — exactly the failure `theme.test.ts` was written for. It only
  passes once `danger` becomes the palest thing on the screen (`#ffb3ab`, a
  pale pink). That is the cost of a dark theme here, not a detail to tune.
- **The green hue test has a blind spot at the dark end, and it is not
  fixed.** It flags `g > r + 12 && g > b + 12`, but channel gaps shrink with
  luminance: a near-black forest green such as `#121a10` reads `g-r=8` and
  is **not** flagged. So the rule catches a mid green and misses the one
  that would make green the ground of the whole app, which is precisely
  what `POSITIONING.md` barred. Left alone because nothing currently depends
  on changing it — but a dark-green ground would pass the letter of the rule
  and break its point, so **judge that by eye, not by the test**.
- **The connection pool was ten against sixteen workers, and the cost was
  the log rather than the data.** First real dataset build, 2026-10-27:
  thousands of "Connection pool is full, discarding connection" from
  urllib3. `_session()` returned a bare `requests.Session()`, which carries
  urllib3's default pool of 10, while `fetch_images` runs 16 threads against
  that one shared session. Nothing was lost -- a discarded *connection* is
  not a discarded *request*, the download just opened a fresh socket -- so
  the real price was a TLS handshake per image and **a log too noisy to find
  a real warning in**. That second one is what made it worth fixing: the
  error this build must never swallow is a species that lost every image,
  and six species source from arbitrary hosts where exactly that happens.
  `_session(pool_size=...)` now mounts an adapter on both schemes, and
  `fetch_images` passes its own `workers`. A test asserts that coupling by
  reading the source, because a pool that stops tracking the worker count
  re-creates the bug the moment either is tuned.
- **Count the file before quoting a number from these notes.** As of
  2026-10-27 the taxonomy holds **244** species — 157 `NO_RECORDED_TOXICITY`,
  66 `TOXIC`, 11 `SERIOUS`, 10 `DEADLY`. Several entries above said 247 and
  one said eleven DEADLY; both were stale, and the derived figures around
  them had drifted with them. The counts moved when a species was dropped
  during the October character review (245 → 244 at `b65480c`) and nobody
  re-read the prose. `python -c "import json; print(len(json.load(open(
  'data/taxonomy.seed.json'))['species']))"` settles it in a second.
- **The config carried two data paths that wanted different working
  directories.** `manifest: data/processed/manifest.parquet` resolved
  against the repo root while `taxonomy: ../data/taxonomy.seed.json`
  resolved against `ml/`, so no single cwd satisfied both — and
  `build_dataset.py` ends by printing "Next: python -m fungi_ml.train
  --config configs/default.yaml", which only finds its config from `ml/`,
  where the manifest does not exist. The documented next command therefore
  failed from every directory, **two hours into a paid run**. Every `data:`
  entry now resolves through `train._data_path` against the repo root;
  `output.dir` deliberately does not, so `runs/baseline` keeps landing in
  `ml/runs/baseline` where the run-book's later steps look for it.
- **`torch.from_numpy` on an Arrow-backed array warns once per sample.**
  Martin's first real training log, 2026-10-27, was unreadable: pandas
  `to_numpy()` handed `FungiDataset` a **read-only** array, and
  `torch.from_numpy` warns about every read-only buffer it is given --
  ~75,000 times an epoch, ~2.2 million times over thirty, with the thirty
  `epoch` lines buried somewhere inside. Same family as the `.unique()`
  gotcha: pandas backed by Arrow returns arrays that do not behave like the
  numpy ones the caller assumes. `dataset.py` now `.copy()`s **once at
  construction**; a copy inside `__getitem__` silences the warning just as
  well and adds an allocation per sample, which is the version that looks
  like a fix and is a slow leak. A test pins which one.
- **The first real run measured 354 s per epoch on a 4090**, so thirty
  epochs is about **3 hours**, not the 4.6 estimated from an assumed
  140 img/s. The real figure is nearer 210. `scripts/gpu_cost.py
  --img-per-sec 210` reprices the exercise; it comes out under £5.
- **Batch size 32 uses 8.5 GB of a 4090's 24 GB.** Measured mid-run at
  100% utilisation and 418 W, so the card is working rather than starved --
  but two thirds of its memory is idle and `train.batch_size` could roughly
  double before it is tight. Free speed on the next run; not worth
  restarting a run that is already going.
## The first real training run, 2026-10-27

Curve in `docs/runs/2026-10-27-baseline.csv`. 244 species, 93,534 images,
ViT-B/16 at 384 px, 30 epochs, 354 s each on a 4090.

- **Accuracy settles at epoch 4 and never moves again.** Across epochs 4-29
  top-1 spans 0.8749 to 0.8841 -- **0.92 of a percentage point**.
- **Risk nearly doubles over the same stretch**, 1.665 to 3.113. Best is
  **epoch 5 at 1.665**, matched at epoch 8 (1.684), then twelve epochs of
  steady deterioration before a partial recovery to 2.854 at the end.
- **Shipping the final epoch would have been 71% more dangerous for 0.40 of
  a point LESS accuracy.** Rule 6 is not a style preference; it earned its
  keep on the first run, visibly.

**The mechanism matters more than the numbers.** Validation risk reads the
*argmax* only -- confidence does not enter it. So with accuracy flat, the
same ~12% of errors are simply landing differently. What the extra epochs
buy is the conversion of "uncertain, spread across the genus" into
"confidently the common one", and when the truth is a rare deadly species
and the common neighbour is harmless, that is the 1000x cell of the risk
matrix. The model does not make more mistakes with training. It makes the
same number of far worse ones.

**Risk is noisy epoch to epoch** -- 1.665, 1.975, 1.809, 1.684 across 5-8 --
so the single lowest epoch is partly luck. Read it as "minimised around
epochs 5-8 at roughly 1.7" rather than trusting the argmin.

**What run two should change.** Train about ten epochs rather than thirty:
same result, a third of the time and cost. And look hard at regularisation
before reaching for `risk_strength`, because `mixup_alpha` and
`cutmix_alpha` are declared `0.0` and `losses.SoftTargetRiskLoss` is
written and **called by nothing** -- a strong regulariser, already in the
repo, dormant, aimed squarely at the overfitting this curve shows.
- **The 4090 billed $0.90/hr, not the $0.34 every pricing roundup quotes.**
  Martin's pod, EUR-IS-2, 2026-10-27 -- a different tier or region, nearly
  three times the advertised Community rate `scripts/gpu_cost.py` was
  defaulting to. He was quoted about £1 for the evening and spent nearer
  £6. The default is now what was actually billed, because an estimate that
  comes in under the bill is worse than no estimate: it is the one people
  act on. **Read the hourly rate off the pod card before deploying** and
  pass `--usd-per-hour` if it differs.
- **A pod without a volume disk loses everything on stop, not just on
  terminate.** The run-book says to mount 60 GB at `/workspace`; if that
  field is missed at deploy time, `/workspace` is an ordinary directory on
  the ephemeral container disk and RunPod warns "all data will be lost" when
  you try to stop. There is then no cheap pause -- it is keep paying the
  full hourly rate or lose the dataset. Nothing irreplaceable was lost here
  because `model.onnx` and the text artefacts were already down, but the
  16 GB of images and `best.pt` went with the pod.
- **A dangerous confusion count measures the *model*; the app is model plus
  safety layer, and until 2026-10-28 nothing measured the join.** Asked what
  the app would actually show for the first run's worst confusion --
  *Galerina marginata* called *Crepidotus cesatii* at 0.850 -- neither
  `report.json` nor the model card could answer, because `dangerous_confusions`
  recorded `count` and `max_confidence` and not **the deadly probability
  mass**, which is the only number that decides. `safety.py` warns whenever
  the deadly species hold `dangerous_mass_threshold` (2%) between them, at
  **any rank** (`deadly_probability_mass` sums the whole distribution; only
  `straddles_dangerous_pair` is limited to the top five). Simulated through
  the real `SafetyLayer` at the fitted 0.69: Galerina at 0.020 shows the full
  lethal warning beside the species verdict even from rank 6; at 0.019 it
  shows **nothing** -- a harmless name, and because rule 1 renders nothing
  for `NO_RECORDED_TOXICITY`, no hazard line either. So a confusion where the
  deadly species kept 30% and one where it kept 0.4% were tallying
  identically, and the metric that gates release was blind to the layer that
  does the protecting. `dangerous_confusions` now records `silent`,
  `min_deadly_mass` and `max_deadly_mass`, sorts **silent first**, and the
  report carries `silent_dangerous_confusion_count` / `_rate`. The card
  states the split in prose and in the table, because present in
  `report.json` is not the same as visible to a reviewer.
- **The 2% is duplicated between `evaluate.py` and `safety.py`, and the test
  reads the source.** `ml/` and `server/` are separate packages with no
  import path between them, so `DEADLY_MASS_THRESHOLD` is a copy;
  `ml/tests/test_evaluate.py` greps `safety.py` for the default rather than
  importing it, because a test that cannot run is not a guard. If the
  warning trigger moves and the copy does not, the card reports silence
  against a line the app no longer uses.
- **Read the silent count before the dangerous-confusion count.** Both are
  in the report. The first is how many people the model would have reached;
  the second includes the ones the app caught anyway, which are worth fixing
  and are not the release question.
- **`report.json` could never have answered it, and that is the real
  finding.** Asked for the first run's silent count, the obvious move was to
  get `report.json` off Martin's machine. It does not contain the answer and
  never did: the deadly probability mass was computed inside `evaluate()`,
  used for the ranking, and **discarded**. Nothing wrote the predictions.
  So the question needed the test images and `best.pt` — and both went with
  the pod. **Run one's silent count is not recoverable.** It gets measured
  on run two, natively, because the measurement now exists.
- **`make_model_card.py --probs-out` is the fix, and it is not optional in
  practice.** ~4 MB of float16 for 9,000 images × 244 species, plus labels,
  classes, split and the temperature applied. Every later "what would the
  app have shown" question is then answerable with no GPU, no dataset and no
  pod. A summary cannot be re-interrogated; a recording can. Same argument
  as `docs/walkthrough.html` being a recording rather than a
  reimplementation.
- **The script now gates on the silent count SEPARATELY from the total.**
  `--max-silent-dangerous-confusions`, default 0. Run one had 10 dangerous
  confusions against SAFETY.md's required zero, so passing a pipeline means
  raising the total — and one dial governing both would have let a raise
  that admits nine caught-by-the-safety-layer confusions admit a silent one
  in the same breath. The summary prints both, silent second and labelled.
- **`manifest.parquet` is the one artefact of a training run that cannot be
  regenerated, and it was the one not kept.** The run-book listed it under
  what to take off the box but not under what to commit, and `*.parquet` is
  gitignored, so there was nowhere for it to go. It went with the pod.
  Rebuildable is not reproducible: GBIF moves, so rebuilding months later
  gives a *different* dataset and `prepare` gives a different split at the
  same seed — which retrospectively made `check_splits.py`'s clean bill of
  health unverifiable and run two incomparable to run one.
  `prepare` now always writes `data/processed/splits.csv.gz`: five columns
  (`species_key`, `observation_id`, `image_url`, `path`, `split`), ~3 MB,
  committed. It is exactly what `check_splits.py` reads, and that script
  falls back to it when the parquet is absent, so the leak checks still run
  from a fresh clone. The parquet is still worth taking; it will never be
  committable.
- **A gitignore rule ending in `/` makes every negation under it dead, and
  this project has now been bitten three times.** `ml/runs/` swallowed
  MODEL_CARD.md and report.json while the pod billed; `data/processed/`
  would have swallowed `splits.csv.gz`; `ml/runs/**` without a negation
  would have swallowed `predictions.npz` that the run-book tells you to
  commit. The failure is silent in the worst way — `git add <path>` exits
  **0** having added nothing. Both directories now use `**` plus explicit
  negations, and `test_the_split_record_is_not_gitignored` shells out to
  `git check-ignore` to assert the kept files are kept and `best.pt`,
  `model.onnx` and the parquet are still ignored. **Check `git status` lists
  them before committing after a run.**
- **Wiring the trained model is a file copy, and that is also what made the
  launcher lie.** `server/app/config.py` points `model_path` at
  `ml/runs/baseline/model.onnx` and `main.py` picks `OnnxBackend` when it
  exists, so dropping `model.onnx`, `labels.json` and `calibration.json`
  into that directory is the whole of it — no code change, no flag, and
  `/health` flips `model_loaded` and `calibrated` by itself. But
  `scripts/try_it.py` printed "the classifier is a stub, so whatever it
  names is meaningless" **unconditionally**, which is true of the stub and
  is dangerous advice about a trained model: it tells the reader to
  disregard a real identification of something that might be lethal. The
  one step that turns the stub into the real thing was the step that turned
  the instructions into a lie. `closing_advice(health)` is now a pure
  function of what `/health` reported, `server/tests/test_try_it.py` pins
  all three states, and rule 1 is asserted over the launcher's text as well
  — the same omission that left a soft edibility verdict in `disclaimer.py`
  through the September purge, because a test that scans what `assess`
  returns never reads what a script prints.
- **`labels.json` is the only thing that turns the model's answer into a
  name, and two places were willing to invent one.** A classifier outputs an
  *index*. `main.py` fell back to `sorted(taxonomy.species)` whenever
  `labels.json` was absent -- correct for the stub, whose names are
  meaningless by construction, and a **guess** for a trained model. The
  checkpoint's order is `sorted(species that survived --min-images)`; the
  taxonomy's is `sorted(all 244)`. They coincide only while nothing was
  filtered out, which is true of run one by luck, and the moment one species
  is dropped every class after the gap is named as its neighbour -- confident
  output, plausible names, nothing downstream able to notice, and a DEADLY
  species potentially served under a harmless one. Same shape as the GBIF
  genus-key gotcha. It surfaced the day a trained model first had to be
  installed by copying three files into a directory by hand: two of three is
  a silent relabelling. `main.py` now **refuses to start** when a model
  exists and `labels.json` does not, and `OnnxBackend` compares the graph's
  output width against `len(classes)` and refuses a mismatch -- reporting
  "unknown" rather than passing when the dimension is symbolic, because an
  unverifiable check must not read as a passed one.
  `server/tests/test_label_space.py` exports a real tiny ONNX model and
  pins both refusals, plus that the stub's fallback survives (removing it
  breaks every fresh clone and every CI job).
- **Installing the trained model is a three-file copy into
  `ml/runs/baseline/`**: `model.onnx`, `labels.json`, `calibration.json`.
  `config.py` already points there and `main.py` selects `OnnxBackend` when
  the file exists, so there is no code change and no flag -- `/health` flips
  `model_loaded` and `calibrated` by itself. It runs on CPU at a second or
  two per photograph; no GPU and no pod.
- **`docs/WINDOWS-START.md` is the from-nothing route, and the trick in it is
  the File Explorer address bar.** Typing `powershell` over the path opens a
  terminal already in that folder, which removes `cd` from a guide written
  for someone who has never opened a terminal. The other two traps it names
  are the Python installer's "Add python.exe to PATH" checkbox (missing it
  is the `python is not recognised` everyone hits) and browsing a .zip
  instead of extracting it, which fails later as permission errors. Getting
  the code is a **Download ZIP**, not a clone: git is one more thing to
  install and explain, and GitHub Desktop is offered for anyone who will do
  it twice.
- **The 16 GB that died with the pod is rebuildable, and the run-book's
  advice about it was inverted by the real hourly rate.** Nothing
  irreplaceable went: `build_dataset.py` re-derives the images from the
  taxonomy and GBIF, and `model.onnx` plus the text artefacts were already
  down. What is gone for good is the *particular* dataset — GBIF moves, so a
  rebuild is a different 93,000 images and a different split, which is why
  `splits.csv.gz` now exists. Cost to rebuild: 2–3 hours, **network-bound,
  no GPU involved**.
  That is the part the run-book had backwards. It said building on a cheap
  CPU box was "optional tidiness rather than real saving", reasoning that at
  $0.34/hr two idle hours cost 70p. At the **$0.90/hr actually billed**, and
  with training down from 30 epochs to 10 (~1 hour), the download costs
  **more than the training run it precedes** — $2.50 against $1.32.
  `gpu_cost.py` now prints which hours need a 4090 at all and what the split
  saves; step 5 of the run-book says to build the dataset on a CPU pod
  against a RunPod **network volume** and attach that volume to the GPU pod
  for the training hour.
- **`EPOCHS` in `gpu_cost.py` is 10, and `ml/configs/default.yaml` still
  says 30.** Deliberate for now: the config is what a run executes and
  changing it belongs with the regularisation work, while the cost script is
  what gets read before deploying. `--epochs` prices any other number. If
  you change one, check the other — this is the second pair of numbers in
  this project that wanted different working directories to agree.
- **The labels.json refusal fired on the real thing, one day after it was
  written.** 2026-10-28: Martin copied `model.onnx` onto his laptop without
  `labels.json`, and the server refused to start instead of naming 244
  species off a derived order. The file had never been committed -- the
  run-book's step 9 listed it, the token was unresolved at the time, and the
  pod that held it has been destroyed. That is the exact scenario the
  fallback used to paper over.
- **`scripts/recover_labels.py` rebuilds it only where the model proves the
  order.** It performs the same derivation the fallback did and then
  *checks* it: `build_label_map` orders classes as `sorted(species that
  survived --min-images)`, so the derived order is right **iff** nothing was
  filtered out -- and the ONNX graph states its own output width. Width ==
  taxonomy size means nothing was dropped and the two sorted lists are the
  same list; anything else means species went, which ones is recorded only
  in the manifest, and the script refuses with no "probably fine" branch. It
  also refuses to overwrite an existing `labels.json`, because a derivation
  must not replace the thing it stands in for. Run one is recoverable
  because all 244 cleared the filter; a run with a stricter `--min-images`
  will not be. **Commit the real one next time.**
- **"Look in .try_it_api.log for why" was not help, and the failure proved
  it.** The launcher pointed at a dotfile and asked someone who has never
  opened a terminal to read it, at the moment they had no working tools and
  no reason to trust what had just failed. `tail()` now prints the last 20
  lines, prefixed with `|` so they read as quoted output rather than as the
  launcher's own words, and says so plainly when the log is empty or missing
  -- a process that wrote nothing died differently from one that wrote a
  traceback, and the failure path must not itself fail.
- **Step 9 was a list, and a list is not a check.** The run-book named the
  seven small artefacts to commit and the three large ones to transfer, and
  it depended on somebody reading it at the end of a long day, on a machine
  billing by the hour, with the interesting part already over. It did not
  survive that. `calibration.json` was never taken off the first real run
  and **cannot be reconstructed** -- temperature scaling is fitted on the
  validation split, so remaking it needs the images and the checkpoint, and
  both went with the pod. The app runs at `calibrated=False` as a result:
  temperature 1.0 instead of 0.8177, naming threshold 0.80 instead of the
  fitted 0.69, and `ood.py` back on the weak top-1 rule. A few hundred
  kilobytes. `scripts/finish_run.py` now reports every artefact as present
  or missing, asks **git itself** whether each small one is ignored, prints
  the `git add` and `runpodctl send` lines ready to paste, and exits
  non-zero while anything is missing -- at the one moment it is still
  fixable. It changes nothing; it is step 9's first command.
- **`calibrated=False` is not neutral, and it fails in the cautious
  direction.** The model measured under-confident, so the fitted T=0.8177
  *sharpens*; without it probabilities stay flat, fewer candidates clear the
  threshold and the app declines more often than the model warrants. That is
  the right way round for a failure and it is still a failure: rule 4 means
  the app says every percentage is uncalibrated rather than presenting it as
  confidence, and the disclaimer's conditional statements re-ask by
  construction because the terms genuinely changed.

## Run two's changes, 2026-10-28 (not yet run)

- **Mixup and CutMix are WIRED and ON.** `ml/fungi_ml/mixup.py`; `Mixer`
  runs on the batch and `losses.SoftTargetRiskLoss` takes over whenever
  either alpha is above zero, so 0.0/0.0 still trains exactly as run one
  did. They are aimed at the first run's specific finding -- accuracy flat
  from epoch 4 to 29 while risk nearly doubled, the model converting
  "uncertain, spread across the genus" into "confidently the common one".
  Mixup trains flatter distributions on inputs between classes, which is
  the opposite transformation, so it beats raising `risk_strength`: it
  attacks the failure rather than pricing it higher afterwards.
- **Everything gets mixed, deadly species included.** Excluding them is
  superficially attractive and would apply *less* regularisation to exactly
  the classes whose overconfidence costs most. The risk weighting handles
  the consequence; the mixer does not also make policy.
- **Mixing dilutes the risk multiplier by about a tenth, not a half.**
  `soft_targets @ risk` means a half death cap carries half the cost -- 500
  rather than 1000 -- but the multiplier is
  `1 + strength * log1p(expected_risk)` and log1p compresses: 6.22 against
  6.91. A test pins the figure, because a dilution of the one mechanism
  this project is built on is worth knowing the size of.
- **The mixer draws its permutation from its OWN generator**, not
  `torch.randperm`. Drawn from the global torch RNG the pairing would move
  with every unrelated change to how many random numbers the rest of the
  loop consumed, so `seed: 1337` would not reproduce a run's mixing -- the
  one way nobody checks. Self-pairing is normal and means that example was
  simply not mixed.
- **`epochs: 10` and `batch_size: 64`.** Risk was minimised around epochs
  5-8 and deteriorated to 3.113 by 29 while top-1 moved 0.92 of a point;
  32 used 8.5 GB of a 4090's 24 at full utilisation.
- **`DECLARED_BUT_UNREAD` in `test_config.py` is now EMPTY**, and the test
  that guarded the alphas is unconditional. It used to read `if not wired:`
  and assert they were 0.0 -- so wiring them up made it pass **vacuously**
  rather than fail. A guard that silently stops guarding is the exact
  failure that file exists to catch.
- **The temperature fit had no bounds, and a degenerate fit serves
  p=1.000.** Log-space stops LBFGS going negative; nothing stopped it
  walking to zero, and `fit` logged whatever it reached for the caller to
  write into `calibration.json`. `logits / 0` is infinite, softmax
  collapses to one-hot, and the app then reports **total confidence on
  anything, including noise** -- rule 4 broken by the calibrator itself.
  Found by the rehearsal, which served `p=1.000` on random pixels at
  T=0.0000. `fit` now refuses outside [0.05, 10] and refuses earlier and by
  name when the split has **no errors at all**: with nothing wrong there is
  no over- or under-confidence to measure, NLL falls without limit as the
  temperature drops, and the optimiser is going where the objective
  genuinely leads. Not a synthetic-data curiosity -- a mixup-trained model
  is more under-confident than run one's 0.8177, so run two's fit moves
  toward this corner.
- **The smoke test rehearsed the path that was not changing.** It hardcoded
  `mixup_alpha: 0.0` while `default.yaml` was about to turn mixing on, so
  the `Mixer`/`SoftTargetRiskLoss` path would have met real data two hours
  into a paid run -- the one thing that script exists to prevent. It now
  reads the real config's mixing keys, and catches `DegenerateTemperature`
  and names it rather than writing a degenerate temperature, which is how
  this went unnoticed before. `PIPELINE OK` with
  `temperature: refused -- no errors on the split` is the correct outcome
  on noise.
- **The *Lepiota* problem is supply, not quota, and measuring it changed the
  plan.** *L. brunneoincarnata* (DEADLY) reached 47.1% recall on run one off
  165 images from 74 observations, which reads like a quota to raise. It is
  not: measured on GBIF 2026-10-28, iNaturalist holds **74** occurrences with
  images for it, full stop, against a `--target` of 400. Raising the target
  does nothing. The whole world, every source, is 189.
  | | iNat | Danish atlas | any source |
  | --- | ---: | ---: | ---: |
  | *L. brunneoincarnata* | 74 | +29 (1.4x) | 189 (2.6x) |
  | *L. subincarnata* | 258 | +125 (1.5x) | 603 (2.3x) |
  `any` is the bigger number and the wrong trade: it drops the determination
  standard entirely, on a genus where misidentification is routine and the
  label is lethal. The Danish atlas is 1.4x **with** a published standard, so
  both species now carry `image_source: ["inaturalist", "danish_atlas"]`.
- **`image_source` may be a list, drawn in order until the target is met.**
  `SpeciesQuota.extra_sources` plus `all_sources`; `_collect_from_source` was
  extracted from `build_manifest` so the paging can run per dataset. The
  target and `max_images_per_observation` are **shared across sources** and
  do not reset -- the target counts images for the species and the cap counts
  photographs of one fruiting body, so resetting either would quietly double
  both. That is the failure that looks like a bigger dataset and is label
  noise; a test pins it by giving one observation id six media in each of two
  datasets and asserting four images survive, not eight. A repeated source is
  refused, because re-paging one dataset adds nothing while reading in the
  taxonomy as though it widened the supply.
- **Seven of the eight dangerous confusions have NO lookalike edge, and that
  is the finding to act on.** Checked against the taxonomy on 2026-10-28:
  only *L. brunneoincarnata* -> *Macrolepiota procera* is a registered pair.
  *Galerina marginata* -> *Crepidotus cesatii* at 0.850 is not, nor
  *A. virosa* -> *A. citrina*, nor any of the *Lepiota* -> *Agaricus
  sylvaticus* / *Clavulinopsis* / *Fuscoporia* errors.
  The reason is structural rather than an oversight: `lookalikes` encodes
  **what humans confuse in the field**, taken from field guides, and a
  classifier confuses different things. Nobody picks a *Crepidotus* thinking
  it is a funeral bell; a network looking at a small brown thing on wood
  does. So `straddles_dangerous_pair` is blind on 7 of 8 real failures, and
  the entire protection on those is `deadly_probability_mass >= 2%` -- which
  is exactly the `silent` metric added this morning. The two findings are the
  same finding from different ends.
  **Do not fix this by adding the edges.** `lookalikes` is a mycological
  claim that a reviewer will read and the ebook renders; writing a model
  artefact into it makes the data wrong in the one place it is meant to be
  right, and every new dangerous edge needs both halves described or
  `evidence_audit.py`'s "nothing is stranded" guarantee breaks. If the safety
  layer should know about empirical confusions, that is a **second graph**,
  built from `predictions.npz`, and a decision for Martin.
- **The second graph exists: `data/model-confusions.json`.** Built by
  `scripts/confusion_graph.py` from a run's `predictions.npz`, loaded by
  `server/app/confusions.py`, and unioned into `straddles_dangerous_pair`
  alongside the taxonomy's field lookalikes. Run one's worst confusion --
  *Galerina marginata* called *Crepidotus cesatii* at 0.850 -- now produces
  `dangerous_group` instead of a confident name.
  Four properties it is built to keep.
  **It is not mycology and never says it is.** The pair detail branches:
  "These are confused with each other in the field" stays for a taxonomy
  pair and is replaced for an empirical one with "I have mistaken one for
  the other before on photographs like this -- they are not lookalikes, I am
  simply unreliable here." Saying the first about *Crepidotus* and a funeral
  bell would teach a resemblance that does not exist, which is the opposite
  of the point. A test pins both wordings.
  **It belongs to ONE checkpoint.** `load` compares the graph's
  `checkpoint` against the model being served and ignores a mismatch
  loudly, because a stale graph refuses pairs this model does not confuse
  while missing the ones it does -- and would read in `/health` as though
  the protection were live. Compared on file name, so `best.pt` and
  `model.onnx` from one run are not treated as different models.
  **Absent and empty are different claims.** `ConfusionGraph.loaded` is
  separate from `len(pairs)`, and `/health` reports `confusions_loaded` and
  `confusion_pairs` separately. A model with no dangerous confusions is a
  result; a graph nobody generated is an absence, and collapsing them would
  let the second read as a clean bill of health.
  **A single error does not become a permanent refusal.** `--min-count 2`,
  or once if the deadly species held `--min-mass 0.10`. One misclassification
  in nine thousand must not stop the app ever naming a species again.
  The disclaimer deliberately does **not** mention it: its version is a hash
  of its own text, so adding a line would restate every stored consent for
  an internal detail the user was never told.

## Run two, 2026-10-28: mixup made it MORE dangerous, for no accuracy gain

Curve in `docs/runs/2026-10-28-mixup.csv`. Same 244 species, 93,622 images
(rebuilt), ViT-B/16 at 384 px, **10 epochs, batch 64, mixup 0.2 / cutmix 1.0
at p=0.5**, 551 s an epoch on an **A40 at $0.60/hr**.

**Accuracy is the same and risk is not.** Epoch by epoch against run one,
top-1 is within half a point throughout and ahead from epoch 5 (0.8843 vs
0.8789, ending 0.8900 vs 0.8838). Risk oscillates around **1.8 in run one
and 3.0 in run two** -- about a **65% rise, with no accuracy cost at all**.
Mixup did not make the model worse at identifying mushrooms. It made the
same number of mistakes land in worse cells of the risk matrix, which is
precisely the failure run one was diagnosed with and precisely what this
change was supposed to fix.

**The shipped 80.1% was a SELECTION consequence, not a capability one.**
Rule 6 picks the lowest-risk epoch; run two's risk never trended down, so
the argmin landed on **epoch 1** (top-1 0.8046) and dragged every reported
number with it. Epoch 8 reached 0.8903. Read run two's model card knowing
the card describes epoch 1.

Test split: top-1 80.1%, top-5 94.9%, genus 85.2%, risk-weighted error
2.0745 against run one's 1.3876.

- **My explanation for it is wrong, and the measurement says so.** I argued
  mixing dilutes the risk multiplier because `soft_targets @ risk` halves a
  death cap's cost, and measured ~10% from log1p compression. Re-measured
  under run two's actual settings -- sampling lambda from the real Beta
  mixtures, mix_prob 0.5, partner almost always harmless -- the mean
  multiplier falls from 7.909 to 7.182: **9.2%**, matching this morning's
  figure. A 9% dilution cannot produce a 65% rise in risk. **The mechanism
  is unexplained.** Possibilities not yet separated: smoother decision
  boundaries moving errors toward different (more dangerous) neighbours;
  the 10.9% of deadly examples trained at under a tenth of full cost signal
  mattering more than the mean suggests; or batch size.
- **Three variables moved at once, which is my methodology error.** Mixup
  on, epochs 30 -> 10, batch 32 -> 64, and a rebuilt dataset. Run two
  therefore proves a regression and not its cause. Run three (`run3-nomix`)
  changes exactly one thing back.
- **And the two runs are not measured on the same validation split**, because
  run one's died with the pod. The comparability loss `splits.csv.gz` was
  built this morning to prevent is already biting, one run later.

### What DID work: the Lepiota data fix

| DEADLY species | Run one recall | Run two recall |
| --- | ---: | ---: |
| *Lepiota brunneoincarnata* | **47.1%** | **88.2%** |

70 Danish atlas images on top of 165 from iNaturalist -- the multi-source
`image_source` list written the same morning, untested against anything but
fixtures. Nearly doubled recall on the worst deadly species, in a run whose
other changes all went backwards. **Keep this and the rebuilt dataset.**

*L. subincarnata* reached its 400 from iNaturalist alone, so the second
source was never queried for it: the ordering rule working as designed, and
confirmed live rather than only in a test.

**My prediction about *Cortinarius orellanus* was wrong.** I flagged it as
the thinnest deadly species (37 observations, 65 images) and predicted weak
recall. It came back at **100%**. Thin is not the same as hard.

### The first silent count ever measured

```
dangerous confus.  14
  of which SILENT   1    <- the ones a user would see unwarned
```

One case in 9,403 test samples where the deadly species held under 2% of
the mass, so the app names a harmless species with no warning and no hazard
line. `make_model_card.py` refused the run on it, separately from the total,
exactly as the two dials were built to.

This number has never existed before. Run one's is **not recoverable** -- it
needed `predictions.npz`, which run one did not write.

### The confusion graph, on fresh data

`scripts/confusion_graph.py`: 13 dangerous confusions, 8 above the bar, and
**8 of 13 are NOT field lookalikes** -- the same structural finding as run
one, on a different model and a different dataset. *Galerina marginata* ->
*Sarcoscypha austriaca* (scarlet elf cup), *Amanita virosa* -> *Mucidula
mucida*, *Clitocybe rivulosa* -> *Crepidotus cesatii*. No human makes those
mistakes, so `lookalikes` could never have caught them and the
`dangerous_group` refusal was blind on all eight.

## Run three, 2026-10-28: mixup was 40% of it, and 60% is still unexplained

Curve in `docs/runs/2026-10-28-nomix.csv`. Identical to run two except
`mixup_alpha` and `cutmix_alpha` back to 0.0 -- one variable, which is what
run two should have been. Same dataset, same split, same batch size, same
10 epochs, 552 s each.

Mean validation risk over epochs 2-9, where the early noise has settled:

| | risk, epochs 2-9 | best | final top-1 |
| --- | ---: | ---: | ---: |
| Run one (30ep, batch 32, no mix) | **1.845** | 1.665 | 0.8838 |
| Run three (10ep, batch 64, no mix) | **2.571** | 1.911 | 0.8926 |
| Run two (10ep, batch 64, mixup) | **3.047** | 2.372 | 0.8900 |

**Mixup cost +0.477, which is 40% of the gap. The remaining +0.726 -- 60%,
the larger half -- is still unexplained**, and the two variables I bundled
with it are untested: `batch_size` 32 -> 64, and the rebuilt dataset.
Turning mixup off recovered less than half the regression.

**Accuracy is the same in all three runs** from epoch 2 onward, and run
three ends *highest* at 0.8926. Across every run this week, accuracy has
been almost invariant to everything tried while risk has moved by 65%.
That is the project's whole thesis arriving as an experimental result
rather than an argument: **top-1 is nearly useless as a tuning signal
here.**

**Risk no longer falls with training, and that is new.** Run one's fell to
epoch 5 (1.665) before wobbling. Runs two and three both have their minimum
at **epoch 1** and rise afterwards, so rule 6 selects a barely-trained
checkpoint in each. Something about the current setup inverts the curve's
early shape; batch size is the obvious suspect, since 64 halves the
optimiser steps per epoch (1,169 against 2,338) and moves what "epoch 1"
means.

**Run four, if it happens, is batch 32 and nothing else changed.** If risk
returns to ~1.85 it was batch size; if it stays near 2.5 it is the dataset,
and that is a harder problem because the dataset is also what fixed the
*Lepiota*.

**And run one cannot be rebuilt.** Its images and split died with its pod,
so "just ship run one's model" means shipping a checkpoint nobody can
retrain, re-split or re-measure. That is an argument for landing a good run
on the current dataset even at a slightly worse risk figure, and it is the
cost of the thing `splits.csv.gz` now prevents.

### Correction: validation risk badly overstated the gap

I judged run three off **validation** risk and reported it as 39% worse than
run one (mean 2.571 against 1.845). On the **test** split, which is what
gates release, it is **2.0% worse with FEWER dangerous confusions**.

| | top-1 | test risk | confusions | silent | *L. brunneoincarnata* | group recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Run one | 88.1% | **1.3876** | 10 | -- | 47.1% | 95.3% |
| Run two (mixup) | 80.1% | 2.0745 | 14 | 1 | 88.2% | 92.6% |
| **Run three** | 81.5% | **1.4151** | **9** | 2 | **88.2%** | 94.4% |

**The one valid comparison is runs two against three**, which share a test
split: **mixup cost 0.6594 of test risk, 47%**. One variable, same data.
Run one's split died with its pod, so every comparison against it is
indicative only -- and the validation-risk gap I quoted was, on the evidence
that counts, almost entirely an artefact of comparing across splits.

**Read the test card, not the validation curve.** The validation number is
for selecting a checkpoint within a run; it is not a figure to compare
between runs, and I used it as one for most of an afternoon.

**Where run three is genuinely behind: coverage.** Calibration fitted
T=0.7179 with a 0.74 threshold and **69.5% coverage**, against run one's
0.8177 / 0.69 / **84.5%**. The app would decline to name a species on about
one photograph in three rather than one in six, and raw ECE is 0.1172
against 0.0502. Both follow from the checkpoint being epoch 1: an
undertrained model is less confident, so fewer predictions clear the bar.
Coverage is the most user-visible number in the whole card and it is not
on the terminal summary -- read it off `calibration.json`.

**Two silent confusions**, against run two's one, on the same split.
SAFETY.md wants zero and `make_model_card.py` refused both runs for it.

## Run four, 2026-10-28: THE MODEL. batch 32, no mixup, rebuilt dataset

Curve in `docs/runs/2026-10-28-b32.csv` (epochs 2-9; 0 and 1 scrolled off the
only record of them, which is itself an argument for `nohup` and a log file).
Identical to run three except `batch_size` 64 -> 32. 588 s an epoch.

**Best on every axis that matters, against the model that has stood since
2026-10-27:**

| | Run one | Run three | **Run four** |
| --- | ---: | ---: | ---: |
| Risk-weighted error | 1.3876 | 1.4151 | **1.0820** |
| Dangerous confusions | 10 | 9 | **7** |
| Silent confusions | unknown | 2 | **2** |
| Coverage | 84.5% | 69.5% | **85.0%** |
| *L. brunneoincarnata* | 47.1% | 88.2% | **88.2%** |
| Deadly group recall | 95.3% | 94.4% | **95.7%** |
| Top-1 | 88.1% | 81.5% | 87.1% |
| Genus | 91.9% | 86.3% | 91.1% |

**22% safer than run one, for one point of top-1** -- which is the trade
rule 6 exists to make, now paid in the direction the rule predicted.

**Batch size was crushing coverage, through checkpoint selection.** At 64
the risk minimum landed on epoch 1, so rule 6 shipped a barely-trained model
(top-1 0.8171) that was too unconfident to clear its own threshold: coverage
69.5%, raw ECE 0.1172. At 32 the minimum moved to **epoch 3** (top-1 0.8768)
and coverage went to 85.0% with raw ECE 0.0627. The lesson is not "32 is
better" -- it is that **a hyperparameter can wreck the product through the
selection rule without touching model quality at all**, and coverage is
where you see it. Nothing in the terminal summary shows coverage; it is in
`calibration.json`.

**Decomposition of run two's regression, using only same-split, one-variable
comparisons (mean validation risk, epochs 2-9):**

```
run2  3.047   mixup on,  batch 64
run3  2.571   mixup off, batch 64     mixup          +0.477
run4  2.361   mixup off, batch 32     batch 64 vs 32 +0.210
```

Mixup was the larger half and is **not** coming back without a specific
reason: it cost 0.66 of *test* risk on the one clean comparison available.

**Run one remains +0.516 away on validation and is BEHIND on test**, which
is the third reminder today that cross-split validation comparisons mislead.
Run one's split died with its pod; its validation figure is not comparable
to anything and never will be.

### What is still wrong: 2 silent confusions

SAFETY.md wants zero and `make_model_card.py` refused the run. Two cases in
9,403 where a deadly species held under 2% of the mass, so the app names a
harmless species with no warning and no hazard line.

**I expected `data/model-confusions.json` to cover them. Measured
2026-10-29: it covers NEITHER.** The reasoning was that the empirical pair
rule fires on *rank* rather than mass, so a silent confusion whose deadly
species is anywhere in the top five becomes a `dangerous_group` refusal.
The qualifier was doing all the work and I did not check it. Run four's
two silent confusions put the deadly species at **rank 40** and **rank
21**, and `straddles_dangerous_pair` reads `ranked[:5]`. Simulated through
the real `SafetyLayer` with the fitted 0.65 threshold, adding the graph
changes neither verdict by a single character.

**What the app actually shows is better than the earlier note said, and
the note was wrong in the reassuring direction.** It claimed these two
cases "name a harmless species with no warning and no hazard line". They
do not:

| true species | deadly rank | mass | verdict | headline |
| --- | ---: | ---: | --- | --- |
| *Inocybe erubescens* (deadly fibrecap) | 40 | 1.07% | `GROUP` | "This looks like a *Gymnopilus* species" |
| *Lepiota subincarnata* (fatal dapperling) | 21 | 1.11% | `UNCERTAIN` | "I'm not sure what this is" |

So one is a full refusal -- the app doing exactly its job -- and the other
names a *genus*, not a species, at 57%. Neither is the confident harmless
name the note described. The fatal dapperling case needs no exception at
all. The fibrecap one does: a user told "a *Gymnopilus* species" has been
given something to act on, and it is wrong.

**The remedy is the mass threshold, not the graph, and it is cheap.** Both
sat just under the 2% line. Sweeping it on run four's test split:

| threshold | photographs warned | false alarms | deadly left unwarned |
| ---: | ---: | ---: | ---: |
| 2.00% (current) | 8.5% | 1 in 20 | **4** |
| 1.50% | 9.3% | 1 in 17 | 3 |
| **1.00%** | 10.5% | 1 in 14 | **0** |
| 0.50% | 13.0% | 1 in 10 | 0 |

One percent takes the unwarned deadly count to zero for one extra false
alarm in roughly every seventy photographs. Against this project's own
stated asymmetry -- a false alarm costs a wasted foraging trip, a miss
costs a liver -- that is not a close call.

**But it has not been done, because the number came off the TEST split.**
Choosing a safety parameter because it zeroes the misses on the split that
gates release is fitting to the gate, which is the same error as selecting
a checkpoint on the data you then report. 2% was picked a priori as a
deliberately low round number; 1% would be picked by looking at the answer.
The honest version is to sweep it on **validation** and report test, which
needs validation predictions -- `make_model_card.py --probs-out` writes the
test split only. That is the change to make before run five, and it is a
one-flag change.
- **The confusion graph's threshold was filtering out exactly the silent
  confusions, which is the one thing it exists to catch.** Found on run
  four's real output: all three pairs it kept were single occurrences with
  high deadly mass, and **both silent confusions were dropped**. The rule
  was `count >= 2 OR max_deadly_mass >= 0.10` -- so it kept what
  `safety.py`'s 2% mass rule already warns about and discarded what the mass
  rule cannot see. The graph is the only cover a silent confusion has,
  because its pair rule fires on **rank** rather than mass.
  `silent` now short-circuits both thresholds: a confusion the mass rule
  would miss is kept however rare, and each pair records how many of its
  occurrences were silent. That is rule 3 applied to this file -- a
  one-in-nine-thousand chance of a user being shown a harmless name for a
  deadly mushroom, with no warning and no hazard line, is not noise to
  threshold away. The false refusal costs a wasted foraging trip; the miss
  is the reason the project exists. The guard against one error becoming a
  permanent refusal still applies to everything that is not silent.
  **Regenerating the graph needs no GPU and no pod** -- `predictions.npz` is
  committed, which is what committing it was for.
