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
