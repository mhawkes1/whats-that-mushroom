# Real photographs

Photographs a person took, with the answer known, run through the running
app rather than through the model.

## Why this is separate from the model card

Every number in `ml/runs/*/MODEL_CARD.md` is measured on held-out
**iNaturalist** images. They were never trained on, so they are a fair test
of the model. They are not a fair test of the product, because they share a
distribution with the training set: good light, the mushroom filling the
frame, photographed by somebody who set out to photograph mushrooms and knew
which features mattered.

A user's photograph is none of those. Measuring the gap needs photographs
from the other population, and there is no way to get those except to take
them.

## Adding a photograph

1. Add it with the script, which strips the metadata:

   ```bash
   python scripts/add_eval_photo.py ~/Pictures/IMG_4821.jpg
   ```

   **Every one of the first eight real photographs carried GPS.** They were
   never committed -- this directory is ignored and git has never held an
   image -- but "safe because the gitignore is right" is one attached file
   away from false, and deleting them afterwards is a fix somebody has to
   remember every time. The script removes location, camera, serial number
   and timestamp, and **applies the orientation to the pixels first**: a
   phone stores a portrait photograph as landscape plus a flag, and
   dropping the flag without rotating hands the model a sideways mushroom.

   The runner also warns about any photograph that still has GPS, for the
   case where somebody copied a file in by hand.
2. Add a row to `real-photos.csv`:

   | column | meaning |
   | --- | --- |
   | `filename` | the file in `eval/photos/` |
   | `species_key` | the true species, as keyed in `data/taxonomy.seed.json`, or `not-in-label-space` |
   | `confirmed_by` | who checked the label. **Blank means nobody has.** |
   | `visible` | what the photograph actually shows: `cap`, `gills`, `stem`, `base`, `bruising`, `spore-print` |
   | `source` | whose camera, or where it came from |
   | `notes` | anything about the photograph worth knowing later |

**Only add a row you are sure of**, and record in `confirmed_by` who
decided. A wrong label here is worse than a missing one: it reports the app
as failing where it was right, and the point of the set is to be believed.
The runner prints a warning and marks every unconfirmed row with `?`,
because a guess and a determination are not the same evidence.

**A photograph of something outside the 244 is a row, not a problem.** Use
`not-in-label-space` as the key and name the species in `notes`. The right
answer for those is a refusal, and naming anything is the failure, so the
runner scores them that way. The first eight real photographs produced one
immediately -- *Craterellus tubaeformis*, the yellowfoot, an ordinary
British species that is simply not among the 244 -- so this is not an edge
case to handle later. Dropping such a row would hide a gap in the label
space; labelling it with the nearest species in the label space would be a
lie about what is in the picture.

`visible` is the column that will earn its keep. The interesting question is
not the overall score, it is whether the app is honest about photographs
that do not show the diagnostic feature -- a yellow stainer with no visible
yellow should produce a refusal, not a confident field mushroom.

## Running it

```bash
python scripts/try_it.py            # in another window
python scripts/real_photo_eval.py
```

It refuses to run while the API is serving the stub backend. That is not
caution: a measurement against deterministic fakes is fabricated rather than
noisy, and on 2026-10-29 an hour went into analysing one.

## What it reports

Coverage, accuracy when the app named something, and -- the one that
decides anything -- how many hazardous species were shown with **no hazard
line at all**. An error the safety layer refuses on is the product working.
An error it names confidently is the product failing. They are not the same
event and are not counted together.

## The photographs are not in git

`eval/photos/` is ignored: they are large, they are personal, and some will
have location metadata in them. The manifest and the results are committed,
so a run is reviewable without the images being published.
