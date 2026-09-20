# Positioning

Why this project exists, who it competes with, and what it deliberately
does not try to win.

## The competitive landscape

### iNaturalist / Seek

Excellent, and not the target. They have 100M+ observations, a large
community of expert verifiers, a CV model trained on more data than this
project will ever see, and records that feed real biodiversity science.

**Do not compete on accuracy, community or taxonomic breadth. That fight is
already lost, and it was never worth having.**

Where they leave room: iNaturalist is a naturalist's record-keeping tool, not
a field identification tool. It is not fungi-specialised, and fungi are
genuinely harder than birds or plants — many species cannot be separated from
a photograph of the cap by anyone. Its CV frequently offers a confident
species where only a genus is warranted. Verification takes days. It offers no
guidance on what additional evidence would resolve an ambiguity, because that
is not what it is for.

### PictureMushroom and the wider consumer app category

This is the target, and the category is weak.

Independent evaluations have repeatedly measured consumer mushroom
identification apps at around or below coin-flip accuracy at species level,
and poisoning cases have been linked to their use.

The core flaw is structural rather than technical. These apps are
incentivised to always produce an answer: confidence drives engagement,
engagement drives subscription revenue, and "I don't know" converts poorly.
So they return a single species with a reassuring percentage, thin or absent
lookalike handling, and in some cases edibility guidance.

**That incentive is the opening.** An app whose competitive advantage is
honest uncertainty cannot be copied by a competitor whose business model
depends on false confidence.

## The core insight

The differentiator cannot be "more accurate". You will not out-data
iNaturalist, and marginal accuracy gains do not solve the problem anyway,
because for a large fraction of fungi a confident species-level answer is not
available to *anyone* from a photograph.

**The differentiator is what happens when the model is unsure — which, with
fungi, is most of the time.** That is genuinely open territory.

## The seven differentiators

### 1. Evidence-driven diagnosis, not one-shot guessing

The largest one. Every existing app treats identification as
`photo in → answer out`. No mycologist works that way. They gather evidence
progressively: cap → gills or pores → **stipe base** (is there a volva? that
is the question that kills people) → spore print → substrate → smell →
bruising reaction → chemical spot tests.

So the app is built as an active interrogator. The classifier runs, the engine
identifies which character best separates the remaining candidates, and asks
for exactly that character — with instructions, an effort estimate, and the
reason it is asking.

This is the difference between an oracle and a diagnostic assistant, and it is
the one thing in this list that no competitor ships.

Implemented in `server/app/interrogation.py` and `server/app/characters.py`.

### 2. Calibrated uncertainty and honest refusal

Be the app that says *"I can't tell from this photo, and here's why."*

Temperature-scaled probabilities, an out-of-distribution check, and a hard
rule that a candidate set spanning a dangerous pair yields no species-level
answer at all.

Positioning line: **"The mushroom app that tells you when it doesn't know."**
In a category this distrusted, that is marketing as much as ethics.

Implemented in `ml/fungi_ml/calibrate.py` and `server/app/safety.py`.

### 3. Confusion-aware training, not accuracy-aware

Standard ML optimises top-1 accuracy, which scores "confused two *Agaricus*"
identically to "confused a death cap with a field mushroom". Those are not the
same error.

Training and evaluation use an explicit asymmetric risk matrix with lethal
confusions weighted orders of magnitude higher, and the model card publishes
per-dangerous-pair metrics. No consumer competitor publishes a model card at
all. This is a technical moat and a credibility claim simultaneously.

Implemented in `ml/fungi_ml/taxonomy.py` and `ml/fungi_ml/losses.py`.

### 4. Season, substrate and host as first-class model inputs

Fungal fruiting is far more seasonal and substrate-bound than plants. A model
that knows *UK, late October, chalk downland, under beech* faces a
dramatically narrower candidate space.

Competitors collect this as display metadata their CV ignores. Here it is fed
into the network through a fusion branch. "Growing on wood or on soil?" alone
eliminates half the candidates, and any user can answer it.

Implemented in `ml/fungi_ml/models/build.py`.

### 5. Regional depth over global shallowness

Launch UK-first with genuine completeness rather than globally with thin
coverage everywhere. Because the model conditions on location, regional
expansion later is a data problem rather than a redesign.

### 6. Transparent provenance

Show *why*: which characters drove the assessment, which lookalikes were
considered, what separates them. Serious foragers do not trust black boxes,
and they are the ones who evangelise an app.

### 7. Genuinely unserved niches

- **Guided spore print workflow.** Capture, timer, colour matching against a
  reference chart under controlled white balance. The single most diagnostic
  cheap test in mycology, and nobody has built it.
- **Chemical spot test logging** (KOH, ammonia, iron salts) for serious users.
- **True offline field mode.** Signal in woodland is poor, and woodland is
  where the app is used. On-device inference means it works where the
  mushrooms are.

## What we deliberately do not chase

- **Community scale and expert verification.** iNaturalist's, unassailable.
- **Taxonomic breadth.** This is a focused tool for one group.
- **Free forever.** Not a differentiator, and not sustainable.
- **Edibility guidance.** Not now, not behind a paywall, not with a
  disclaimer. See `SAFETY.md`.

## How the positioning shows up in the product

The result screen inverts the competition's information hierarchy on purpose:

1. The verdict — including a refusal, when that is the honest answer
2. The next diagnostic question, so the user can actually resolve it
3. The candidate list, with toxicity on every row
4. Warnings

Leading with a species name and a large percentage is precisely the design
that gets people poisoned, so the candidate list is deliberately **not** the
headline. There is no green in the palette and no "edible" value in the type
system; the safest toxicity label renders as "Not assessed as safe", because
users read a best-case label as permission.
