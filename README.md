# What's That Mushroom?

Fungi identification that reports honest uncertainty.

Point a camera at a mushroom and the app tells you what it might be — and,
when it genuinely cannot tell, it says so and tells you what to go and look at
instead.

> **This app never tells you whether a mushroom is safe to eat.**
> Never eat a wild mushroom identified only by an app.

## Why another mushroom app

Because the existing ones are structurally unsafe.

Consumer mushroom identification apps have been repeatedly measured at around
or below coin-flip accuracy at species level, and poisoning cases have been
linked to their use. The reason is incentive rather than incompetence:
confidence drives engagement, and "I don't know" converts badly. So they
always answer, and they answer with a single species and a reassuring
percentage.

Meanwhile iNaturalist is excellent and has already won on community scale,
expert verification and taxonomic breadth. There is no point competing there.

The open ground is what happens when the model is *unsure* — which, with
fungi, is most of the time. That is what this project is built around.

## What makes it different

**It interrogates rather than pronounces.** Every other app maps a photograph
to an answer and stops. No mycologist works that way: they find the character
that separates the remaining candidates and go and look at it. This app does
the same. It runs the classifier, sees that the top candidates are separated
by a specific character, and asks for exactly that character — with
instructions, an effort estimate, and the reason it's asking.

> Your top two candidates are separated by spore print colour. Here's how to
> take one — it takes 4 hours. Faster alternative: dig up the base and
> photograph it. If there's a cup-like sac, that changes everything.

**It refuses to resolve lethal ambiguities from a photograph.** When the
leading candidates include both halves of a known fatal confusion — death cap
and field mushroom, funeral bell and sheathed woodtuft, false morel and true
morel — it names neither and explains why.

**Its confidence is calibrated.** Raw softmax output is not a probability;
networks are systematically overconfident. Temperature scaling is fitted on
held-out data and the threshold for naming a species is chosen empirically to
hit a target precision. Until that is fitted, the app says its numbers are
rough ordering only.

**It weights errors by consequence.** Top-1 accuracy cannot distinguish
confusing two brittlegills from confusing a death cap with a field mushroom.
The risk matrix makes that asymmetry explicit — under-calling a lethal species
costs 1000x — and it drives both the training loss and checkpoint selection.

**It publishes a model card**, including per-dangerous-pair confusion counts
and a coverage-versus-precision curve. No consumer competitor publishes
anything comparable.

**It feeds season and location to the model**, not just to the display.
Fungal fruiting is intensely seasonal and substrate-bound, so this narrows the
candidate space more than incremental backbone capacity does.

## Layout

```
whats-that-mushroom/
├── data/taxonomy.seed.json    57 UK species, lookalike graph, risk data
├── ml/                        dataset pipeline, training, calibration, export
│   ├── fungi_ml/
│   │   ├── taxonomy.py        species model and the risk matrix
│   │   ├── losses.py          risk-weighted objective
│   │   ├── train.py           training loop
│   │   ├── calibrate.py       temperature scaling, threshold fitting
│   │   ├── evaluate.py        safety-first metrics and model card
│   │   └── export.py          ONNX export with verification
│   └── tests/
├── server/                    FastAPI inference service
│   └── app/
│       ├── safety.py          the safety layer — read this first
│       ├── interrogation.py   question selection by information gain
│       ├── characters.py      how to ask a non-expert for evidence
│       └── main.py            HTTP API
├── app/                       Expo React Native client
└── docs/
    ├── SAFETY.md              the policy that governs the product
    └── ROADMAP.md             what's next, and what's deliberately not
```

## Current status

Everything works **except the model itself.** There is no trained classifier
yet; the API serves a stub backend producing deterministic fake predictions so
the safety layer, interrogation engine, API and mobile client can all be
developed and tested. Every other layer is real and tested.

80 tests pass, covering split integrity, the risk asymmetry, calibration, and
the classic fatal confusions end to end.

## Running it

**API**

```bash
pip install -r server/requirements.txt
cd server && uvicorn app.main:app --reload
```

`GET /health` reports whether a model is loaded, whether calibration has been
fitted, and whether the taxonomy has been through mycological review. All
three are `false` until the work in `docs/ROADMAP.md` is done.

**Mobile client**

```bash
cd app && npm install
EXPO_PUBLIC_API_URL=http://<your-lan-ip>:8000 npx expo start
```

**Tests**

```bash
python -m pytest ml/tests server/tests -q
```

**Training** — see `docs/ROADMAP.md`. Needs a GPU.

## Before this goes anywhere near the public

`docs/SAFETY.md` carries a blocking checklist. The most important item: **the
taxonomy has not been reviewed by a qualified mycologist.** The toxicity data,
lookalike relationships and diagnostic characters are drawn from standard
references, but reference data that users will act on needs expert sign-off
before release. `reviewed_by` is `null` and the API reports that honestly.
