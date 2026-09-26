# Taxonomy review

The seed taxonomy in `data/taxonomy.seed.json` covers 57 species and has
**not** been verified by a qualified mycologist. It was compiled from standard
references. Until it is signed off, `reviewed_by` stays `null` and `/health`
reports `taxonomy_reviewed: false`.

`taxonomy-review-worksheet.csv` in this folder is the working document: one
row per species, sorted by review priority, with blank columns for the
reviewer to complete.

`character-states-worksheet.csv` is the second document, and it is the one
that now needs checking first. It records **which state of each character a
species actually shows** -- white spore print for the death cap, decurrent
gills for the deadly *Clitocybe* -- and the app uses it to decide what a
user's answer rules in or out. The 30 rows covering the 8 deadly species have
been filled in from this repository's own descriptive notes, **not by a
mycologist**, so that the mechanism could be tested. Those 30 rows are the
highest-priority thing in this folder to verify or correct. The remaining 160
rows are blank.

**All 205 rows are now filled in, and all 205 are unreviewed.** They were
compiled from this repository's own descriptive notes, not by a mycologist.
Checking them is the highest-value work in this folder: the app uses them to
decide what a user's answer rules in or out, so an error here changes what
the app tells someone holding a mushroom.

Start with the species that can kill, then the safe lookalikes opposite them,
then the rest. The worksheet is already sorted in that order.

**Note on the tier counts.** The Tier 2 list below names 20 species. Derived
from the lookalike graph, 22 species sit opposite a deadly one: the extra two
are *Paxillus involutus* and *Tricholoma equestre*, which appear in the Tier 1
table above because they are themselves SERIOUS. Both have been filled in.

### How to complete a row

**How wide the list should be depends on which side of a confusion the species
is on.** The app treats a state you list as "consistent" and anything else as
"contradicted", and a contradiction pushes that species down the list.

- For a **deadly** species, list every state it can show, including uncommon
  ones. A state left off turns a correct observation into a contradiction and
  pushes the lethal species down, which is the dangerous direction. *Galerina
  marginata* therefore lists all four ring states, because its ring is fragile
  and often gone, and nobody should be able to dismiss a funeral bell for want
  of one.
- For the **safe lookalike**, a contradiction pushes the harmless species
  down, which moves the app back toward caution. Here a tighter list is the
  careful choice: being wrong costs a false alarm rather than a missed
  poisoning.
- **If you are unsure, leave the row blank.** Blank means "not described",
  which the app treats as no evidence at all, and that is always safe.

### Two answer options were added

Two characters could not be recorded at all, because the app offered no answer
that fitted. Both have been added, and both change what users are asked:

1. **"Apricot or fruity"** on `smell`, for *Cantharellus cibarius*, whose
   apricot smell is one of its most reliable characters.
2. **"Green"** on `bruising_reaction`, for *Lactarius deliciosus*, whose latex
   stains green.

If either reads wrongly to you, say so -- they are user-facing question
wording as much as data.

### Corroboration from the First Nature UK index

A UK binomial index was checked against the label space. Only two of the app's
species failed to appear in it under the same name, and both were already open
queries here:

1. ***Clitocybe dealbata*** is **absent from that index**, which carries only
   *C. rivulosa*. That is independent support for query 1 below -- the two may
   be one species under two names, in which case the app is carrying a
   meaningless "dangerous pair". **This has not been acted on.** Merging them
   would delete a DEADLY entry from the label space on the strength of one
   index, which is a call for you rather than for us.
2. ***Chlorophyllum brunneum*** appears in the index as ***C. rhacodes***.
   Both are called Shaggy Parasol. Which name should the app carry?

### Nineteen species were added to the label space

Ten of them close a confusion the app already half-modelled -- it held the
Death Cap but not the False Deathcap people mistake for it, one lethal
*Lepiota* but not its sibling, the Blusher and the Panther Cap but not the
*Amanita* that resembles both. The other nine are the species the companion
ebook teaches and the app could not name.

Two classifications are judgement calls and want a second opinion:

- ***Pleurocybella porrigens*** recorded **SERIOUS**, not DEADLY. The fatal
  encephalopathy cases are documented but concentrated among people with
  impaired kidney function.
- ***Amanita citrina*** and ***Amanita excelsa*** carry **no recorded
  toxicity**, which is a statement about the references consulted rather
  than a claim about either species.

Two are carried under a current name where the index uses an older one, so
both spellings are worth confirming:

| Recorded as | Index uses |
| --- | --- |
| *Cerioporus squamosus* | *Polyporus squamosus* |
| *Fomitopsis betulina* | *Piptoporus betulinus* |

### A third answer option was added

**"Raw potato or earthy"** on `smell`, because it is what separates *Amanita
citrina* from the Death Cap and the app had no way to say it.

Related, and deliberately left alone: **the Death Cap's own smell is not
recorded**, because this repository's notes make no claim about it. That means
a user reporting a raw-potato smell cannot push the Death Cap down the list --
the safe direction, but a gap. Should *A. phalloides* carry a smell entry, and
if so which states?

### Three species were added to the label space

Closing items 10-12 below. A species the model has never seen cannot be
flagged as dangerous: it is forced into the nearest class it knows, which for
a lethal lawn mushroom means something harmless.

| Species | Recorded as | Why |
| --- | --- | --- |
| *Lepiota brunneoincarnata* | DEADLY | Amatoxins, fruits in grass and parks, repeated fatal poisonings in Europe. REVIEW item 10 called this the most significant gap. |
| *Amanita pantherina* | SERIOUS | Present in the UK, hospitalisation usual, deaths rare. Recorded SERIOUS rather than DEADLY — please confirm. |
| *Cortinarius orellanus* | DEADLY | The other orellanine webcap; only *C. rubellus* was present. |

All three need the same checking as the rest, and the *A. pantherina*
classification in particular is a judgement call worth a second opinion.

## Priority tiers

### Tier 1 — Critical (12 species)

Species that can kill or hospitalise. An error here is the most direct route
to harming a user.

| Species | Current | In lethal pairs |
| --- | --- | ---: |
| *Amanita phalloides* — Death Cap | DEADLY | 8 |
| *Amanita virosa* — Destroying Angel | DEADLY | 7 |
| *Clitocybe rivulosa* — Fool's Funnel | DEADLY | 4 |
| *Cortinarius rubellus* — Deadly Webcap | DEADLY | 4 |
| *Galerina marginata* — Funeral Bell | DEADLY | 4 |
| *Clitocybe dealbata* — Ivory Funnel | DEADLY | 2 |
| *Gyromitra esculenta* — False Morel | DEADLY | 2 |
| *Inocybe erubescens* — Deadly Fibrecap | DEADLY | 2 |
| *Paxillus involutus* — Brown Roll-rim | SERIOUS | 1 |
| *Tricholoma equestre* — Yellow Knight | SERIOUS | 1 |
| *Entoloma sinuatum* — Livid Pinkgill | SERIOUS | 0 |
| *Rubroboletus satanas* — Devil's Bolete | SERIOUS | 0 |

### Tier 2 — High (20 species)

The *safe half* of a lethal confusion. **Wrongly reassuring here is the fatal
direction**: if the app says "this is the field mushroom" and it is not, the
consequence falls on the user. These need their separating characters checked
as carefully as Tier 1.

Highest exposure first:

- *Calocybe gambosa* — confusable with 4 deadly species
- *Agaricus campestris* — 3
- *Agaricus arvensis*, *Amanita muscaria*, *Amanita rubescens*,
  *Armillaria mellea*, *Marasmius oreades*, *Volvopluteus gloiocephalus* — 2 each
- *Cantharellus cibarius*, *Clitopilus prunulus*, *Cortinarius violaceus*,
  *Hypholoma fasciculare*, *Kuehneromyces mutabilis*, *Lactarius deliciosus*,
  *Lycoperdon perlatum*, *Macrolepiota procera*, *Morchella esculenta*,
  *Pholiota squarrosa*, *Russula cyanoxantha*, *Verpa bohemica* — 1 each

### Tier 3 — Standard (25 species)

Everything else. Still needs checking for current nomenclature and accurate
characters, but an error is less likely to be directly harmful.

## Specific queries for the reviewer

These are the entries the compiler was least confident about. Each is a
question, not an assertion.

### Data that may be wrong

1. **`Clitocybe rivulosa` and `Clitocybe dealbata` are both present as
   separate DEADLY species.** These are taxonomically entangled and several
   authorities treat *dealbata* as a synonym of *rivulosa*. Should they be
   merged? Carrying both may create a meaningless "dangerous pair" between
   two names for the same fungus.

2. **`Paxillus involutus` is classified SERIOUS.** It has caused fatalities
   through cumulative immune-mediated haemolysis. Should it be DEADLY?

3. **`Amanita rubescens` is classified TOXIC.** This is a deliberate policy
   choice (toxic raw, and the margin for error sits inside *Amanita*), not a
   claim that it is dangerous when properly cooked. Is that the right call?

4. **`Volvopluteus gloiocephalus` is classified TOXIC.** Often listed as
   edible-but-poor. Deliberately conservative, or simply wrong?

5. **`Laetiporus sulphureus` is classified TOXIC.** The reasoning is host
   dependence — specimens from yew, eucalyptus and conifers are regarded as
   unsafe. Is host-dependence handled correctly here?

6. **`Tricholoma equestre` is classified SERIOUS** on the basis of the
   rhabdomyolysis cases. Does the dose-dependence change how this should be
   recorded?

7. **`Inocybe erubescens`** — is this the current accepted name? The older
   *Inocybe patouillardii* appears in some references.

### Possible coverage errors

8. **`Omphalotus olearius`** is included but is rare or absent in the UK. For
   a UK-first label space, should this be excluded, or replaced with a
   species that actually occurs here?

9. **`Verpa bohemica`** — is this genuinely present in the UK, or is it
   carried over from North American references?

### Possible coverage gaps

A species the model has never seen cannot be flagged as dangerous — it will be
forced into the nearest class it knows, which may be something harmless.

10. ~~**`Lepiota brunneoincarnata`** and the small brown *Lepiota* species.~~
    **Added**, along with *L. subincarnata*. The classification still needs
    checking; the gap does not.
11. ~~**`Amanita pantherina`** — Panther Cap.~~ **Added**, as SERIOUS rather
    than DEADLY, which is the judgement call flagged above.
12. ~~**`Cortinarius orellanus`**.~~ **Added**, beside *C. rubellus*.
13. Any other UK species the reviewer considers a common cause of poisoning
    that is missing.

### Coverage against how often things are actually found

`scripts/frdbi_gap.py` measures the label space against the Fungal Records
Database of Britain and Ireland — the full export, 17,536 taxa, 2026-09-22.
**All 200 of the most-recorded British macrofungi are now in it.** The label
space went 79 → 235 in two batches on 2026-09-22, and the worksheet went 289
rows → 1,155.

That is the review queue, and it grew fivefold. The compiler's own confidence
did not grow with it: the first 289 rows were derived from notes written for
species chosen one at a time, and the 866 new ones were written in bulk
against a ranking. **Treat the new rows as weaker than the old ones.**

That is the expected shape rather than a failure: the label space was
assembled around danger, not frequency, so it holds eleven species that can
kill and the ordinary ones each is confused with. But a beginner on a walk
meets the frequent ones, and sixty-nine of them currently have no class to
land in.

**A second batch of 129 followed**, completing the top 200. The toxicity
grading across all of them is explicitly deferred: Martin will check it once a
mycologist has signed the species off. Until then every value is the
compiler's conservative reading, and the distribution is 11 DEADLY,
10 SERIOUS, 59 TOXIC, 155 with no recorded toxicity.

Three things in that batch are worth a reviewer's attention before the rest:

- ***Helvella crispa* recorded TOXIC.** It contains hydrazines of the same
  family as *Gyromitra*. Graded conservatively; commonly eaten after cooking.
- ***Psilocybe semilanceata* is in the label space.** It is common, and the
  small brown mushrooms it is confused with include *Galerina marginata*.
  Possession and picking are controlled in the UK.
- **Several additions are not separable from a photograph.** The two
  *Crepidotus*, the two *Ganoderma*, most of the resupinate crusts. They are
  in because they are recorded in their thousands and the model will otherwise
  force them into something else — but the app should be expected to refuse on
  them, and that is the right outcome.

**Twenty-seven were added on 2026-09-22**, chosen by record count and by
whether they land next to something already dangerous. They created 14 new
lethal pairs, which is the point of the exercise: *Coprinellus micaceus* vs
*Galerina marginata*, *Cuphophyllus virgineus* vs the white *Clitocybe*
species, *Amanita fulva* vs *A. phalloides* and *A. virosa*, *Inocybe
geophylla* against both the *Clitocybes* and *Inocybe erubescens*.

Every one of them needs the same review as the rest, and three carry a
judgement the compiler is least sure of:

| Species | Recorded as | The call |
| --- | --- | --- |
| *Amanita fulva* | TOXIC | Toxic raw; graded by the same policy as *A. rubescens*. |
| *Inocybe geophylla* | SERIOUS | Muscarine — rarely fatal, usually a hospital matter. Right tier? |
| *Hygrocybe conica* | TOXIC | A contested record, read conservatively. Please confirm. |

The reviewer's question is not "should these be added" — it is **which
additions would change what the app refuses**. A common species added without
the dangerous thing it resembles is worse than no addition at all: it teaches
a name the model will reach for and withholds the one it should refuse over.
The script prints, for each candidate, the dangerous species already known in
its genus and a compiled note on what it is confused with. Both are
UNREVIEWED.

### Characters that are described too thinly to be asked about

Filling the companion ebook from the taxonomy measured this, because a book
row that comes back blank is a character the taxonomy never describes. Across
235 species:

| Character | Species describing it |
| --- | --- |
| `habitat` (surroundings, trees) | 11 |
| `season` (time of year) | 5 |
| `smell` | 12 |
| `growth_form` | 12 |

`character_states` was compiled from each entry's own `notes`, and the notes
were written to separate a species from its lookalikes rather than to
describe it. The consequence is not cosmetic: a user answering *Surroundings:
beech* moves almost nothing, because for 68 species the answer is neither
consistent nor contradictory — it is undescribed, which the evidence layer
correctly treats as no evidence at all.

14. **Are `habitat` and `season` worth describing for every species, or worth
    dropping as questions?** Either is defensible. What is not defensible is
    asking a question that cannot move an answer. A forager filling these two
    columns for all 235 species would make two of the cheapest observations a
    user can make — where they are standing, and what month it is — actually
    count.

## What a reviewer is being asked to confirm

For each species, per the worksheet columns:

- **`REVIEW_name_current`** — is the scientific name current and correctly
  spelled?
- **`REVIEW_toxicity_agreed`** — is the toxicity classification right? Note
  that the scale records a *recorded hazard*, not a verdict on eating: the
  app makes no edibility claim in either direction, and
  `NO_RECORDED_TOXICITY` is never shown to a user.
- **`REVIEW_characters_agreed`** — are the listed diagnostic characters the
  ones that actually separate this species in the field?
- **`REVIEW_lookalikes_agreed`** — is the lookalike list right, and is
  anything dangerous missing from it?
- **`REVIEW_notes`** — free text; anything the entry gets wrong or omits.

## Two kinds of review

These are separable, and it is worth recording them separately.

## Field-character review of the dangerous species: DONE, 2026-09-26

Martin Hawkes reviewed every character of all 21 DEADLY and SERIOUS species
— 96 rows — and signed each one. `docs/QA-dangerous-species-completed.xlsx`
is his return, kept as received. Eight states changed; the rest he agreed,
often adding field description the seed data did not have.

This is **field-character review only**. It says nothing about toxicity
grading or nomenclature, both of which still need qualified sign-off, so
`/health` still reports `taxonomy_reviewed: false` and the release blocker
in `SAFETY.md` is still open. What it does mean is that the characters the
interrogation engine asks about, for the species where a wrong answer kills,
have been checked by somebody who finds these mushrooms.

The remaining 1,104 rows — everything TOXIC and below — are still
`unreviewed-seed-fill`.

### What he changed

| Species | Character | Was | Now |
| --- | --- | --- | --- |
| *Galerina marginata* | ring | three states | all four |
| *Inocybe erubescens* | smell | blank | apricot/fruity; ink/chemicals |
| *Lepiota subincarnata* | size | under 2 cm – 10 cm | 2–5 cm |
| *Tricholoma pardinum* | gill colour | white | white; yellow/green |
| *Tricholoma pardinum* | habitat | beech; mixed | + birch |
| *Tricholoma terreum* | gill colour | white; grey | + yellow/green |
| *Tricholoma equestre* | habitat | pine/spruce | + birch |

Two are worth a second look by whoever does the mycological sign-off:

- **`Lepiota subincarnata` size narrows a DEADLY species.** Cap 2–3.5 cm is
  his measurement, and it is surely right, but it means a 6 cm specimen is
  now pushed away from this label where before it was not. That runs against
  the generous-list convention for deadly species. Accepted on his
  authority.
- ***Cortinarius orellanus* under conifers was NOT added**, though his note
  records it. `habitat` is the only character separating it from
  *C. rubellus*, and both cause the same delayed kidney failure; listing
  conifers for both would leave the app unable to say which webcap a forager
  is holding. A test pins that separation and caught the change when it was
  briefly made. The conifer records are real, so the note is kept as prose.

**Field-character review** asks whether the diagnostic characters are usable
in practice — the right things to look at, described the way a non-expert
would recognise them. An experienced forager is often *better* at this than
an academic mycologist.

**Toxicity and nomenclature review** asks whether the classifications and
names are correct against current literature. This needs qualified sign-off
and is the part that blocks public release.

The first unblocks internal development and testing. Only the second unblocks
publication.

## Where to find a reviewer (UK)

- A local fungus group affiliated to the **British Mycological Society**;
  county fungus recorders are often very experienced
- **University mycology departments** — frequently receptive to public-good
  projects
- **The Association of Foragers** — professional teaching foragers
- A **paid consultation**. Reviewing 57 species is a bounded piece of work.
