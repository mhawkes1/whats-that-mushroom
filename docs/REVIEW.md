# Taxonomy review

The seed taxonomy in `data/taxonomy.seed.json` covers 62 species and has
**not** been verified by a qualified mycologist. It was compiled from standard
references. Until it is signed off, `reviewed_by` stays `null` and `/health`
reports `taxonomy_reviewed: false`.

Two working documents accompany this note, both in this folder:

- **`fungi-taxonomy-review-pack.docx`** — a printable Word document with the
  species split into priority tiers, blank columns to mark up by hand, the
  specific queries below, and a sign-off page. Best for handing to a reviewer.
- **`taxonomy-review-worksheet.csv`** — the same 62 species as a spreadsheet,
  one row each, for anyone who would rather type than annotate.

Both are generated from `data/taxonomy.seed.json`, so regenerate them if the
taxonomy changes rather than editing them as the source of truth.

## Priority tiers

### Tier 1 — Critical (16 species)

Species that can kill or hospitalise. An error here is the most direct route
to harming a user.

| Species | Current | In lethal pairs |
| --- | --- | ---: |
| *Amanita phalloides* — Death Cap | DEADLY | 9 |
| *Amanita virosa* — Destroying Angel | DEADLY | 8 |
| *Lepiota brunneoincarnata* — Deadly Dapperling | DEADLY | 5 |
| *Clitocybe rivulosa* — Fool's Funnel | DEADLY | 4 |
| *Cortinarius rubellus* — Deadly Webcap | DEADLY | 4 |
| *Galerina marginata* — Funeral Bell | DEADLY | 4 |
| *Lepiota subincarnata* — Fatal Dapperling | DEADLY | 3 |
| *Clitocybe dealbata* — Ivory Funnel | DEADLY | 2 |
| *Gyromitra esculenta* — False Morel | DEADLY | 2 |
| *Inocybe erubescens* — Deadly Fibrecap | DEADLY | 2 |
| *Lepiota castanea* — Chestnut Dapperling | DEADLY | 1 |
| *Amanita pantherina* — Panther Cap | SERIOUS | 2 |
| *Paxillus involutus* — Brown Roll-rim | SERIOUS | 1 |
| *Tricholoma equestre* — Yellow Knight | SERIOUS | 1 |
| *Entoloma sinuatum* — Livid Pinkgill | SERIOUS | 0 |
| *Rubroboletus satanas* — Devil's Bolete | SERIOUS | 0 |

### Tier 2 — High (22 species)

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

### Tier 3 — Standard (24 species)

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

These are **not** in the label space and arguably should be. A species the
model has never seen cannot be flagged as dangerous — it will be forced into
the nearest class it knows, which may be something harmless.

10. ~~*Lepiota brunneoincarnata* and the small brown *Lepiota* species~~ —
    **added.** The label space now carries *L. brunneoincarnata*,
    *L. subincarnata* and *L. castanea* as DEADLY, plus *L. cristata* as
    TOXIC because it is the common species people will actually photograph
    and the natural entry point to the genus. Please confirm the
    classifications, and in particular whether *L. subincarnata* and
    *L. josserandii* should be treated as one species.
11. ~~*Amanita pantherina*~~ — **added** as SERIOUS, linked to *A. rubescens*
    as its principal confusion. Please confirm the severity and the
    separating characters, especially the reliance on flesh not reddening.
12. **`Cortinarius orellanus`** — still missing. The other
    orellanine-containing webcap; only *C. rubellus* is currently included.
13. Any other UK species the reviewer considers a common cause of poisoning
    that is missing.

## What a reviewer is being asked to confirm

For each species, per the worksheet columns:

- **`REVIEW_name_current`** — is the scientific name current and correctly
  spelled?
- **`REVIEW_toxicity_agreed`** — is the toxicity classification right? The
  scale records *recorded harm from eating* and nothing else. Its lowest
  value, `NONE_RECORDED`, means no toxicity is recorded and is not a
  statement that the species is safe to eat — nor that it is not.
- **`REVIEW_characters_agreed`** — are the listed diagnostic characters the
  ones that actually separate this species in the field?
- **`REVIEW_lookalikes_agreed`** — is the lookalike list right, and is
  anything dangerous missing from it?
- **`REVIEW_notes`** — free text; anything the entry gets wrong or omits.

## Two kinds of review

These are separable, and it is worth recording them separately.

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
- A **paid consultation**. Reviewing 62 species is a bounded piece of work.
