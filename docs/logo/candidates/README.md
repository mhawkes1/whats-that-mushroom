# Mark candidates, 2026-10-31

**None of these is the production mark.** That is still
`docs/logo/funga-mark.svg`, written by `docs/logo/mark.py`, and
`scripts/build_icons.py` still derives every icon from it. These are
Martin's shortlist from the 31 October review, kept so that choosing one
later is a copy rather than a redrawing.

## What changed from the production mark

Two things, and they are independent.

**The cap is domed rather than flat**, which is the only change to Martin's
round-five geometry anywhere in the project. The reason is the circular
launcher mask, which nothing had ever been tested against. A circle has the
same margin in every direction, so a drawing fits it when its own reach is
even. Measured as a fraction of the tile's radius:

| | left | right | up | down | spread |
| --- | ---: | ---: | ---: | ---: | ---: |
| flat cap (production) | 0.82 | 0.82 | 0.53 | 0.78 | **0.29** |
| domed cap (these) | 0.62 | 0.62 | 0.71 | 0.71 | **0.09** |

The flat cap does **not** clip — an earlier note here said it did and that
was wrong. It comes within 18% of the rim at the sides while leaving twice
that gap above, and a lopsided margin inside a perfect circle reads as a
drawing that is too big and floating at once. The dome is near enough
concentric.

The stem keeps its open path and its butt caps, so `app/test/icons.test.ts`
passes against any of these unchanged. Only the cap's two curves moved.

**The ground is filled and coloured.** The production mark is an outline on
paper: 18.1% of a true 48 px tile is ink, and the tile's luminance is 211
against a store page's white. Filling the same paths takes it to about 32%
without touching the silhouette.

## The files

| File | Ground | Mark | vs mark | vs white page |
| --- | --- | --- | ---: | ---: |
| `dome-cream-on-canopy.svg` | `#3f5d37` | `#f6f3ea` | 6.7:1 | 7.4:1 |
| `dome-cream-on-moss.svg` | `#4e6e3f` | `#f6f3ea` | 5.2:1 | 5.8:1 |
| `dome-canopy-on-white.svg` | `#ffffff` | `#3f5d37` | 6.7:1 | 1.0:1 |
| `dome-moss-on-white.svg` | `#ffffff` | `#4e6e3f` | 5.2:1 | 1.0:1 |
| `dome-canopy-on-paper.svg` | `#f6f3ea` | `#3f5d37` | 6.7:1 | 1.1:1 |

The first two are Martin's picks. `canopy` is `theme.ts`'s own green, so an
icon using it matches the app's header band; `moss` is lighter and the one
to watch, because it is the only green here drifting toward the saturated
green that reads as permission.

**The white-ground versions carry a measured cost**: tile luminance 208,
within three points of the production outline's 211, which is the figure
that started this review. A white tile on a white store page has no edge.
iNaturalist can do it because their mark is already known; a new app in a
list of white tiles is the one that disappears.

## Rule 1 and the green

`POSITIONING.md` barred green because green is the colour of permission, and
`theme.ts` still bars it from anything that names a species or states an
outcome. That rule is unchanged and these do not touch it: it governs colour
*inside* the app, beside a verdict. A launcher icon states no outcome.

What makes it tolerable here specifically is that the permission green is a
*bright* green. `#3f5d37` and `#4e6e3f` are dark and desaturated — the
colour of a wet beech wood, not of a go-light.

## If one of these is chosen

1. Its two paths and its colours replace the ones in `docs/logo/mark.py`.
2. `adaptiveIcon.backgroundColor` in `app/app.json` moves with it. It is
   `#f6f3ea` today, chosen when the mark was drawn on paper, and the
   launcher composites the foreground over it.
3. `app/test/icons.test.ts` pins that background, so the test changes in the
   same commit. That is the test working, not an obstacle.
4. `python scripts/build_icons.py` regenerates all four PNGs. Nothing is
   edited by hand.
5. Judge the result with `python docs/logo/truepx.py`, never from a
   comparison sheet — a sheet at deviceScaleFactor 2 or 3 flatters a 29 px
   icon by four to nine times in area, and that mistake has already cost
   this project a round.
