# Model card — Funga classifier

## What this model does

Given a photograph and optional field metadata (month, location), it
returns a probability distribution over the species in its label space.
It does **not** determine edibility and must never be presented as doing so.

## Headline numbers

- Evaluated on **10462** held-out images across **271** species
- Top-1 species accuracy: **83.3%**
- Top-5 species accuracy: **96.2%**
- Genus-level accuracy: **88.4%**
- Risk-weighted error: **2.077**
- Expected calibration error: **0.0184**

Genus accuracy is the more honest figure. Many fungi cannot be separated
to species from a photograph at all, by this model or by an expert.

## Safety-critical results

Dangerous confusions (a deadly species predicted as something a user might eat): **18** (0.1721% of samples)

Of those, **0** are **silent**: the deadly species held less than 1% of the probability mass, so the app's lethal warning never fires and the user is shown a harmless name with no hazard line. The rest are caught by the safety layer and the user sees the warning regardless. **The silent count is the one that reaches a person.**

`Silent` is the count the app would NOT have warned about. `Deadly mass` is how much probability stayed on the deadly species across those samples; the safety layer warns from 1% upward, at any rank.

| True species | Predicted as | Count | Silent | Deadly mass (min–max) | Max confidence |
| --- | --- | ---: | ---: | ---: | ---: |
| _amanita-virosa_ | _amanita-citrina_ | 3 | **0** | 0.101–0.304 | 0.806 |
| _clitocybe-rivulosa_ | _crepidotus-cesatii_ | 3 | **0** | 0.220–0.305 | 0.336 |
| _galerina-marginata_ | _tubaria-furfuracea_ | 2 | **0** | 0.085–0.361 | 0.890 |
| _amanita-virosa_ | _calvatia-gigantea_ | 1 | **0** | 0.317–0.317 | 0.582 |
| _inocybe-erubescens_ | _gymnopilus-penetrans_ | 1 | **0** | 0.084–0.084 | 0.544 |
| _galerina-marginata_ | _coprinellus-micaceus_ | 1 | **0** | 0.381–0.381 | 0.499 |
| _amanita-virosa_ | _agaricus-sylvicola_ | 1 | **0** | 0.336–0.336 | 0.448 |
| _amanita-virosa_ | _russula-claroflava_ | 1 | **0** | 0.197–0.197 | 0.429 |
| _cortinarius-rubellus_ | _laccaria-laccata_ | 1 | **0** | 0.164–0.164 | 0.345 |
| _lepiota-subincarnata_ | _russula-ochroleuca_ | 1 | **0** | 0.130–0.130 | 0.267 |
| _cortinarius-rubellus_ | _imleria-badia_ | 1 | **0** | 0.242–0.242 | 0.244 |
| _clitocybe-rivulosa_ | _cuphophyllus-virgineus_ | 1 | **0** | 0.180–0.180 | 0.198 |
| _lepiota-subincarnata_ | _tubaria-furfuracea_ | 1 | **0** | 0.079–0.079 | 0.156 |

### Recall on deadly species

| Species | Recall |
| --- | ---: |
| **Group-level (genus) recall** | 93.3% |
| _amanita-phalloides_ | 100.0% |
| _amanita-virosa_ | 86.4% |
| _clitocybe-rivulosa_ | 86.4% |
| _cortinarius-orellanus_ | 100.0% |
| _cortinarius-rubellus_ | 85.4% |
| _galerina-marginata_ | 91.4% |
| _gyromitra-esculenta_ | 100.0% |
| _inocybe-erubescens_ | 87.5% |
| _lepiota-brunneoincarnata_ | 73.9% |
| _lepiota-subincarnata_ | 84.1% |

## Calibration

- Temperature: **0.760**
- ECE before scaling: 0.0892
- ECE after scaling: **0.0102**
- Confidence threshold for 95% precision: **0.74**
- Coverage at that threshold: **72.6%**

Below the threshold the app declines to name a species and asks for
further evidence instead. Low coverage is a deliberate outcome.

## Coverage versus precision

| Confidence threshold | Coverage | Precision |
| ---: | ---: | ---: |
| 0.10 | 99.9% | 83.3% |
| 0.15 | 99.8% | 83.5% |
| 0.20 | 99.2% | 83.8% |
| 0.25 | 98.4% | 84.4% |
| 0.30 | 97.1% | 85.2% |
| 0.35 | 95.2% | 86.4% |
| 0.40 | 92.9% | 87.8% |
| 0.45 | 90.7% | 88.9% |
| 0.50 | 88.0% | 90.1% |
| 0.55 | 84.7% | 91.5% |
| 0.60 | 81.0% | 92.8% |
| 0.65 | 77.8% | 94.0% |
| 0.70 | 74.5% | 95.0% |
| 0.75 | 70.8% | 96.1% |
| 0.80 | 67.3% | 96.9% |
| 0.85 | 62.4% | 97.7% |
| 0.90 | 56.4% | 98.5% |
| 0.95 | 46.9% | 99.3% |

## Known limitations

- Trained predominantly on citizen-science photographs, which are biased
  towards photogenic, mature, well-lit specimens. Real queries are worse.
- Geographic coverage reflects where observers are dense, not where fungi are.
- Species outside the label space cannot be recognised as absent; the
  out-of-distribution check in the serving layer handles this, not the model.
- Microscopic and chemical characters are invisible to it. Many genera
  (notably _Cortinarius_, _Inocybe_, _Russula_) cannot be resolved to
  species without them.

## Intended use

An aid to learning and to narrowing possibilities. Not a food-safety device.
No output of this model should be used to decide whether to eat a mushroom.