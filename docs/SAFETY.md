# Safety policy

This document governs the product. Where it conflicts with a feature request,
a growth metric or a design preference, this document wins.

## Why this exists

Mushroom misidentification kills people. *Amanita phalloides* alone accounts
for most fatal mushroom poisonings worldwide, and it has common lookalikes
that inexperienced foragers collect deliberately. *Galerina marginata*
contains the same amatoxins and grows in clusters on dead wood, exactly where
foragers look for edible woodland species. Several *Cortinarius* species
destroy the kidneys two to three weeks after the meal, by which point the
victim no longer connects the illness to the mushroom.

Independent evaluations have repeatedly found consumer mushroom identification
apps to be around or below coin-flip accuracy at species level, and poisoning
cases have been linked to their use. Those apps are not badly built by
accident. They are badly built by incentive: confidence drives engagement,
engagement drives subscriptions, and "I don't know" converts poorly.

This project takes the opposite position deliberately.

## The rules

### 1. The app never asserts edibility

There is no "edible" category anywhere in the system. The `toxicity` field
records the consequence of eating a species and exists solely to drive
warnings. Its safest value is `INEDIBLE`, which the UI renders as "Not
assessed as safe".

This is enforced by test, not by convention. `test_no_output_path_ever_asserts_edibility`
scans every user-facing string produced by the safety layer for affirmative
edibility claims across a range of scenarios, and
`test_species_notes_never_recommend_eating` scans the reference data itself.

### 2. A lethal ambiguity is never resolved from a photograph

When the leading candidates include both members of a known dangerous pair,
the app returns `dangerous_group` and names neither. It explains what the two
possibilities are, states plainly that one can kill, and asks for the
character that separates them.

This is the single biggest behavioural difference from competing apps. Where
they return "Field Mushroom, 87%", this returns "I can't safely narrow this
down" and tells the user to dig up the stem base.

### 3. Small probabilities of death are not rounded away

A deadly species holding 2% of the probability mass triggers the full warning.
A one-in-fifty chance of death is not noise. The threshold is deliberately
low, because the cost of a false alarm is a wasted foraging trip and the cost
of a miss is a liver transplant.

Membership of a genus containing a deadly species also counts. A user cannot
safely reason "it's an *Amanita*, but a harmless one".

### 4. Confidence is calibrated, or it is not shown as confidence

Raw softmax output is not a probability. Networks are systematically
overconfident, and presenting that number as a percentage is the mechanism by
which apps mislead users.

Temperature scaling is fitted on held-out data (`ml/fungi_ml/calibrate.py`),
and the confidence threshold for naming a species is chosen empirically to
hit a target precision, rather than picked because a round number sounds
reassuring. Until calibration has been fitted, the API reports
`calibrated: false` and the UI says the percentages are rough ordering only.

### 5. Declining to answer is a correct answer

Below the calibrated threshold the app says it does not know. Low coverage is
a deliberate outcome, and coverage-versus-precision is published in the model
card rather than hidden.

### 6. Errors are weighted by consequence, not counted

Top-1 accuracy cannot distinguish confusing two brittlegills from confusing a
death cap with a field mushroom. The risk matrix in `ml/fungi_ml/taxonomy.py`
makes the asymmetry explicit: under-calling a lethal species costs 1000x,
over-caution costs 2x. Checkpoint selection during training is on
risk-weighted error, not accuracy — a model one point more accurate that
confuses a death cap more often is the worse model.

### 7. No question puts the mushroom near the user's mouth while a deadly
species is in play

Taste tests are suppressed entirely whenever a deadly candidate holds
meaningful probability. Amatoxins are tasteless, odourless, and not destroyed
by cooking; asking for a taste test would imply otherwise.

## Before any public release

These are blocking, not aspirational.

- [ ] **Qualified mycological review of the entire taxonomy.** The seed data
      is drawn from standard references but has not been reviewed by a
      mycologist. `reviewed_by` is `null` and `/health` reports
      `taxonomy_reviewed: false`. Do not ship while that is the case.
      See `REVIEW.md` for the prioritised species list, the specific queries
      raised, and `taxonomy-review-worksheet.csv` for the working document.
- [ ] **Model card published**, including per-dangerous-pair confusion counts
      and the coverage/precision curve.
- [ ] **Zero dangerous confusions on the held-out test set**, or a documented
      justification for each one that remains.
- [ ] **Calibration fitted** on a split not used for model selection.
- [ ] **Onboarding consent** recorded, with the disclaimer shown and
      acknowledged before first use.
- [ ] **Legal review** of the disclaimer and terms, covering the jurisdictions
      of launch.
- [ ] **An incident route**: a way for users to report a suspected
      misidentification, and a documented process for acting on it.

## What to do if someone is poisoned

The app should surface this prominently. In the UK: call 999 for emergencies,
or NHS 111. Take the mushroom, or what remains of it, to hospital. Photographs
are a poor substitute for the specimen. Do not wait for symptoms — amatoxin
poisoning has a deceptive latent period of 6 to 24 hours, and early treatment
substantially improves outcomes.
