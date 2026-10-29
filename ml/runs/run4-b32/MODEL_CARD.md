# Model card — Funga classifier

## What this model does

Given a photograph and optional field metadata (month, location), it
returns a probability distribution over the species in its label space.
It does **not** determine edibility and must never be presented as doing so.

## Headline numbers

- Evaluated on **9403** held-out images across **244** species
- Top-1 species accuracy: **87.1%**
- Top-5 species accuracy: **97.3%**
- Genus-level accuracy: **91.1%**
- Risk-weighted error: **1.082**
- Expected calibration error: **0.0088**

Genus accuracy is the more honest figure. Many fungi cannot be separated
to species from a photograph at all, by this model or by an expert.

## Safety-critical results

Dangerous confusions (a deadly species predicted as something a user might eat): **7** (0.0744% of samples)

Of those, **2** are **silent**: the deadly species held less than 2% of the probability mass, so the app's lethal warning never fires and the user is shown a harmless name with no hazard line. The rest are caught by the safety layer and the user sees the warning regardless. **The silent count is the one that reaches a person.**

`Silent` is the count the app would NOT have warned about. `Deadly mass` is how much probability stayed on the deadly species across those samples; the safety layer warns from 2% upward, at any rank.

| True species | Predicted as | Count | Silent | Deadly mass (min–max) | Max confidence |
| --- | --- | ---: | ---: | ---: | ---: |
| _inocybe-erubescens_ | _gymnopilus-penetrans_ | 1 | **1** | 0.011–0.011 | 0.573 |
| _lepiota-subincarnata_ | _lactarius-tabidus_ | 1 | **1** | 0.011–0.011 | 0.240 |
| _clitocybe-rivulosa_ | _collybiopsis-confluens_ | 1 | **0** | 0.082–0.082 | 0.690 |
| _amanita-virosa_ | _amanita-citrina_ | 1 | **0** | 0.365–0.365 | 0.553 |
| _galerina-marginata_ | _crepidotus-cesatii_ | 1 | **0** | 0.165–0.165 | 0.385 |
| _inocybe-erubescens_ | _cuphophyllus-pratensis_ | 1 | **0** | 0.041–0.041 | 0.351 |
| _clitocybe-rivulosa_ | _crepidotus-cesatii_ | 1 | **0** | 0.292–0.292 | 0.285 |

### Recall on deadly species

| Species | Recall |
| --- | ---: |
| **Group-level (genus) recall** | 95.7% |
| _amanita-phalloides_ | 97.5% |
| _amanita-virosa_ | 95.7% |
| _clitocybe-rivulosa_ | 92.5% |
| _cortinarius-orellanus_ | 100.0% |
| _cortinarius-rubellus_ | 100.0% |
| _galerina-marginata_ | 94.6% |
| _gyromitra-esculenta_ | 100.0% |
| _inocybe-erubescens_ | 90.9% |
| _lepiota-brunneoincarnata_ | 88.2% |
| _lepiota-subincarnata_ | 82.4% |

## Calibration

- Temperature: **0.793**
- ECE before scaling: 0.0627
- ECE after scaling: **0.0129**
- Confidence threshold for 95% precision: **0.65**
- Coverage at that threshold: **85.0%**

Below the threshold the app declines to name a species and asks for
further evidence instead. Low coverage is a deliberate outcome.

## Coverage versus precision

| Confidence threshold | Coverage | Precision |
| ---: | ---: | ---: |
| 0.10 | 100.0% | 87.1% |
| 0.15 | 99.9% | 87.2% |
| 0.20 | 99.5% | 87.5% |
| 0.25 | 99.0% | 87.8% |
| 0.30 | 98.3% | 88.3% |
| 0.35 | 97.0% | 89.0% |
| 0.40 | 95.7% | 89.8% |
| 0.45 | 93.9% | 90.6% |
| 0.50 | 91.9% | 91.4% |
| 0.55 | 89.5% | 92.5% |
| 0.60 | 87.2% | 93.4% |
| 0.65 | 84.7% | 94.4% |
| 0.70 | 82.0% | 95.3% |
| 0.75 | 79.5% | 96.1% |
| 0.80 | 76.6% | 96.8% |
| 0.85 | 72.9% | 97.6% |
| 0.90 | 67.6% | 98.3% |
| 0.95 | 58.8% | 99.1% |

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