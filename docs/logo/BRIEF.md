# Logo brief — What's That Mushroom?

Six concepts, drawn as SVG so a designer can open and rework them. Rendered
at app-icon size and at 88, 48 and 29 px in `concepts.png`, because **a mark
that dies at 29 px is not an app icon** and most mushroom logos do.

Regenerate the sheet with `concepts.html` (it inlines the SVGs, so rebuild it
after changing one — rendering a stale copy is a mistake already made once).

## What the mark has to do

1. **Survive 29 px.** One dominant shape. No fine detail, no text, no gradient.
2. **Not be a fly agaric.** The red cap with white spots is what most of this
   category uses, and it is a *toxic* species — an odd thing for an app whose
   entire position is honest hazard reporting to put on its icon.
3. **Not say "safe".** No green as the dominant colour, no tick, no thumbs up,
   no basket, nothing that reads as permission to eat. `docs/POSITIONING.md`
   has the long version; in this app green is chrome and never a verdict.
4. **Work in one colour.** It will be embossed, printed small on the book,
   and shown as a silhouette in places. If it needs two colours to read, it
   is not finished.

## Palette

Ink `#231e17` · Paper `#f6f3ea` · Gold `#9a6a24` (the book's rule) ·
Red `#941613`, which in this product means danger and is used nowhere else.

## The six, and what I think of them

| | Concept | Verdict |
| --- | --- | --- |
| 1 | **Gill Rose** — a cap's underside, eighteen gills, long and short alternating as they really do | **Strongest.** Survives 29 px as a clean starburst, looks like nothing else in the category, and is the view the app keeps asking users for |
| 2 | **Spore Print** — half-white, half-black paper with the deposit across the join | **Strongest concept.** It is the app's own feature as a mark; a competitor cannot borrow it without building the feature. The split survives at any size |
| 3 | **Ask** — the stem is the question mark | **Most commercially obvious.** Instantly readable, friendly, works to 48. The `?` goes slightly soft at 29 and wants thickening |
| 4 | **The Pair** — one mushroom solid, one outlined in warning red | Good idea, fiddly execution. Two objects at 29 px is one too many. A designer could rescue it by making the red one much more ghostly and overlapping them far more |
| 5 | **Cap and Rule** — a plain mushroom over the book's gold rule | **Safest.** Survives everything, ties to the printed guide, and is the most generic — it is a mushroom |
| 6 | **Half Known** — the mushroom dissolving into stipple | **Best idea, weakest drawing.** "I'll tell you when I can't tell" as a picture. My stipple still turns to noise below 48 px; the fix is probably far fewer, much larger dots, or a hard-edged dissolve rather than a dotted one |

If I had to pick two to develop: **Gill Rose** for distinctiveness and
**Half Known** for meaning — and a designer is far more likely than I am to
make the second one work.

---

# Round two — `round2/`

Martin liked the plain mushroom and the gills, so round two develops only
those two threads, and adds colour. `sheet-marks.png` is the eight shapes in
ink and paper; `sheet-colour.png` is the five best across six colourways.

## The shapes

| Mark | Verdict |
| --- | --- |
| **Gill Rose** | Unchanged from round one. Still the most distinctive thing here |
| **Gill Ring** | The same idea made geometric — open ring, twelve gills, no centre. Colder, more corporate, survives small |
| **Gill Cap** | **Both liked things in one mark**: a whole mushroom with the gills knocked out of the cap. Soft at 29 px and worth a designer's attention |
| **Toothed** | The cheapest gill cue — the cap's underside is a row of teeth. The teeth vanish at 29 px but the silhouette holds, so it degrades gracefully |
| **Solo** | The mushroom and nothing else. Survives everything, says nothing clever |
| **Badge** | Knocked out of a filled disc. **The best small-size performer of the lot** — at 29 px it is still unmistakably a mushroom |
| **Fan** | A tilted cap from below. Pretty, but the stem reads as detached |
| **Two Tone** | Outlined stem. Reads hollow rather than light |

## The colourways

**One of them is a mistake, and it is worth knowing why.** *Oxblood & Oat* is
very close to `danger` (`#941613`), the colour this app uses for "a species
that can kill is in play" and for nothing else. Making that the brand colour
spends the one colour whose meaning the product depends on. Shown for
completeness; do not pick it.

Of the rest:

- **Forest & Cream** and **Saffron on Char** are the two **dark-field** icons,
  and on a store page full of white icons that is most of the battle. Forest
  is the on-theme one, saffron the loud one.
- **Rust & Bone** is the bookish one and sits closest to the printed guide.
- **Slate & Sand** is the clinical, trustworthy one, and the least foraging-ish
  of the six — which may be exactly right for an app that declines to tell
  anyone what is safe to eat.
- **Ink & Paper** matches the app's own palette and is the safe answer.

On green: a *bright* green mushroom icon says "natural, wholesome, safe", which
is the opposite of this product's position. A deep forest green behind a cream
mark does not — it reads as woodland at dusk. That is the distinction to hold
if the forest route is taken.
