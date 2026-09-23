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

### 1. The app makes no edibility claim, in either direction

There is no "edible" category anywhere in the system, and since 2026-09-23
there is no "inedible" one either. This is an identification app: it reports
what a mushroom is and what hazard is on record for it, and it does not
adjudicate meals.

The `toxicity` field records a **known hazard** and exists solely to drive
warnings. `DEADLY`, `SERIOUS` and `TOXIC` are shown to users, because a
hazard somebody is not told about is a hazard the app is concealing.
`NO_RECORDED_TOXICITY` is **never shown**: the row carries a name and
nothing else.

The value it replaced was `INEDIBLE`, rendered as "Not assessed as safe".
That wording was written to avoid sounding like permission, and it still put
a safety verdict on all 157 species that carried it. Saying nothing is the
stronger position. Silence cannot be read as an endorsement, cannot be read
as a warning, and cannot be disputed — which matters for liability as much
as for honesty.

This is enforced by test, not by convention. `test_no_output_path_ever_asserts_edibility`
scans every user-facing string produced by the safety layer for affirmative
edibility claims across a range of scenarios,
`test_species_notes_never_recommend_eating` scans the reference data itself,
and `test_no_user_facing_path_makes_an_inedibility_claim` covers the other
direction.

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

Saying this once, at the time, is not enough. The observation log outlives
the sentence: an entry stores the model version and the calibration state it
was recorded under, and the log compares them against the service as it
stands now (`app/src/lib/observationLog.ts`, `caveats`). A confidence
recorded before calibration was fitted must never later read as a calibrated
one, and a number produced by a model the app no longer runs is not
comparable to one produced today.

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
- [x] **Onboarding consent** recorded, with the disclaimer shown and
      acknowledged before first use. `GET /disclaimer` serves the statements;
      the client gates on them (`app/src/lib/consent.ts`). The version is a
      hash of the text, so a materially changed disclaimer is re-acknowledged
      rather than silently inherited — and while `model_loaded`, `calibrated`
      or `taxonomy_reviewed` is false, each of those is one of the statements.
      Still needs the legal review below; this records consent, it does not
      make the wording sufficient.
- [ ] **Legal review** of the disclaimer and terms, covering the jurisdictions
      of launch.
- [x] **An incident route**: a way for users to report a suspected
      misidentification, and a documented process for acting on it.
      `POST /incident` and `docs/INCIDENTS.md`. Reports are triaged from the
      taxonomy rather than from how they are worded, are never applied to the
      data automatically, and a report of someone being unwell is returned as
      an emergency rather than filed as a ticket. `docs/INCIDENTS.md` carries
      its own short list of what is still owed before launch — a named
      responder, rate limiting, and a retention period.

## Two screens that work differently from the rest

**The emergency page is hardcoded and reachable before consent.** Every other
string a user reads is served, so that one copy of it exists and cannot drift.
This one is not, because the screen that must never fail is this one and a
wood is exactly where the network is not. It also sits above the consent gate:
someone opening the app because a child has eaten something in the garden is
not going to work through an onboarding flow first, and a safety gate standing
between a frightened person and the words "call 999" is not a safety gate.

**The report form refuses to be a triage channel.** Its first two questions
are whether anyone ate it and whether anyone is unwell. A yes to either turns
the screen into the emergency guidance before anything is submitted — the
client checks for itself rather than waiting on the server's reply, because
the reply needs the network. An incident form that files a medical emergency
as a ticket and thanks the user for their feedback is worse than no form.

## What is stored on the device

The observation log (`app/src/lib/observationLog.ts`) keeps, locally and
without uploading anything: the photograph URIs, the time, the coordinates if
the user granted location, what they answered, and the verdict with its
warnings as it stood when they left the screen.

Two things follow from that.

**A history row says what the app was willing to say, not what the mushroom
was.** Only a `species` verdict names a species; every other verdict, the
lethal-pair refusal included, describes the refusal instead. The result
screen names both halves of a dangerous pair because the refusal is on the
screen beside it. A list row six weeks later has no such context, and a name
read out of context is an answer.

**Where someone forages is the most sensitive thing here.** Deleting the
locations is a separate control from deleting the log, because "stop keeping
where I was" and "delete my history" are different requests. Any future sync
must coarsen coordinates rather than send them: a patch is findable from one
accurate fix.

## What to do if someone is poisoned

The app should surface this prominently. In the UK: call 999 for emergencies,
or NHS 111. Take the mushroom, or what remains of it, to hospital. Photographs
are a poor substitute for the specimen. Do not wait for symptoms — amatoxin
poisoning has a deceptive latent period of 6 to 24 hours, and early treatment
substantially improves outcomes.
