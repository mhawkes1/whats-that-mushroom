# Moss on white — the agreed visual format, 2026-10-31

Martin's call, after the 31 October review: *"save the current format of the
app as it looks brilliant."* This file is that save. **It is a
specification, not the implementation** — `app/src/lib/theme.ts` still holds
the paper palette, and applying this is a separate change (see *What
applying it costs* below).

## Where it came from

Three measured findings, in the order they mattered.

1. **The old icon was 18.1% ink at a true 48 px tile, luminance 211 against
   a store page's white.** It had no edge and nothing to see. Filling the
   same paths took it to 32% without touching the silhouette.
2. **Every surface in the app was 1.09:1 against its background.** Cards
   were not visually objects; the whole screen read as text on one flat
   field. `canopy` and `accent` filled were worth 6.68:1 and 4.24:1 and were
   used only as hairlines.
3. **A launcher masks to a circle, and the flat cap sits badly in one.**
   Reach from the tile centre: 0.82 sideways against 0.53 upward, a spread
   of 0.29. The domed cap reaches 0.62 and 0.71 — spread 0.09, near enough
   concentric. It does not clip; the margin is lopsided, which reads as a
   drawing both too big and floating.

## The palette

| Token | Value | Role |
| --- | --- | --- |
| background | `#ffffff` | the app's ground |
| border | `#dde3d6` | the only separation a card gets |
| tint | `#eef4e8` | advisory panels |
| moss | `#4e6e3f` | the brand. Filled tiles, the action button, tab glyphs |
| moss deep | `#3a5230` | eyebrows, active tab, headings on the tint |
| moss ink | `#1f2b1a` | the thesis panel, the darkest thing on screen |
| text | `#1b1f17` | body |
| text muted | `#4a5544` | secondary |
| text faint | `#646b5a` | timestamps, footnotes |
| danger | `#941613` | unchanged |
| caution | `#7d5206` | unchanged |

Contrast, all AAA except where noted: text on white 16.7:1, muted 7.9:1,
moss deep on white 8.6:1, moss deep on tint 7.7:1, danger on white 8.8:1,
cream on moss ink 13.3:1. **White on moss is 5.8:1 — AA, not AAA** — so moss
is a ground for large text and filled tiles and never carries small body
copy.

**Gold is gone.** It had become an accent appearing on exactly one control,
which is an orphan rather than a system. The app is moss, ink, white and the
two hazard colours.

**White costs the warmth the cream was chosen for.** Photographs of brown
mushrooms were meant to sit on a warm ground without looking jaundiced; on
white they read slightly cooler. Worth checking on the result screen, which
is mostly photographs. It also removes the last separation cards had —
1.09:1 on paper becomes 1.00:1 — so structure now comes entirely from
borders and the two filled elements.

## The rule that comes with the green

Moss now marks **the observations the app could name**: the filled count
tile is *species named*, and in the log a moss left-edge marks rows where it
committed to a name while refusals get a plain grey edge. Martin's call.

It is a short step from *I identified this* to *this one is fine*, which is
the misread the product exists to prevent. So:

> **Moss may mark confidence in an identification. It may never mark the
> standing of a species.**

It can edge a row, fill a count, or sit in the chrome. It must never appear
on or beside a hazard line, in the verdict text on the result screen, or
anywhere a user could read it as the app's opinion of a meal. The first row
of the log is the test case: *Amanita rubescens*, moss edge, **TOXIC RAW**
chip on the same row. The green says the app knows what it is; the chip says
what it is.

This does not loosen `POSITIONING.md`. That rule is about colour attached to
a verdict, and it still holds.

## The mark

`docs/logo/candidates/dome-cream-on-moss.svg` — the domed cap, cream on
`#4e6e3f`. Chosen 31 October from nine ranked candidates.
`dome-canopy-on-paper.svg` is the in-app lockup, for the masthead and
anywhere there is no tile to sit in.

## What applying it costs

- `theme.ts` takes the eleven values. `accent` becoming moss removes gold
  from every screen at once, because it is already a named role.
- **`app/test/theme.test.ts` will fail, and should.** It bars any palette
  colour that is dominantly green and is not declared chrome; moss is now
  the brand, so that declaration has to be re-stated rather than bypassed.
  It also pins the emphasis ordering, which must still put a DEADLY row
  heavier than a TOXIC one on the new ground, and the AAA floor for
  `danger` on every ground it appears on.
- `app.json`'s `adaptiveIcon.backgroundColor` moves from `#f6f3ea` to the
  mark's ground, and `app/test/icons.test.ts` pins it.
- `docs/screenshots/` and `docs/walkthrough.html` both show the old palette
  and need regenerating from the real client afterwards.

None of that is hard. All of it is a separate commit from this one, because
a palette change that drags its own tests with it should be reviewable on
its own.

## The masthead, 2026-10-31

`app/assets/masthead.jpg`, generated by `scripts/build_masthead.py` from one
of Martin's frames: a red *Russula* on a sphagnum bank, cropped to the bottom
third, which holds no mushroom.

**It took three frames to get a clean one, and the reason is worth keeping.**
The first two were cut from a bolete-on-moss photograph, and both had debris
lying across the moss just above the title — a conifer needle in one, twigs
in both corners of the other. Neither is a flaw in the photograph. Both are
fatal in a masthead, because the eye goes to a stick before it goes to the
name, and no amount of crop-hunting fixed it: the band is a third of the
frame, so there is nowhere to hide.

**Why a photograph of moss rather than of a mushroom.** The masthead this
replaced was the book cover — a cep, filling the frame, lit as a portrait.
That is the composition every foraging app opens with, and here it is an
implication: a prize edible as the first thing you see, on the product whose
whole claim is that it will not tell you what is safe to eat. It makes no
claim and breaks no rule, and it says the wrong thing. It is also the one
band of the nine whose green is visibly the brand's green, because the brand
colour is called moss and this is moss.

**The darkening is in the asset, not in a render-time filter.** A filter is
a second thing that has to arrive; on a slow decode the photograph can paint
before the overlay does, and for that frame the title is cream on sunlit
moss. Shipping it dark makes the worst case a dark band with no text yet.

**This frame needs almost no darkening, and that was not true of the last
two.** Unmodified, its worst case over `theme.colour.photoScrim` is
**7.50:1** — already AAA on the brightest moss a letter can land on. It ships
at 0.92 brightness, which is headroom rather than legibility, and measures
8.4:1.

The frame before it did need darkening, and I got that wrong in a way worth
recording: it was baked against the gradient in a mock-up instead of against
the token the app actually uses, so it arrived **double-darkened** — AAA at
11.64:1, with the moss gone almost black. A photograph of nothing. Found by
driving the real client and looking at it, which is the only way this class
of fault has ever been found here. **Measure the frame; do not inherit the
last frame's numbers.**

**The rule under the title went from gold to cream.** The book's gold reads
at about 3.9:1 against the scrimmed moss, which made the one surviving
thread back to the printed guide the faintest thing on the screen.

`app/test/masthead.test.ts` pins the assets' presence, the scrim token, that
every word over the photograph is `onAccent`, that the cover does not come
back, that the tagline survives, and that both images are hidden from screen
readers.
