# Palette variants

Three lighter, greener alternatives to the committed palette, rendered from
the real client on 2026-10-20 for Martin to choose between. **None of them is
applied** — `app/src/lib/theme.ts` is unchanged.

`palettes.json` holds the eleven tokens each variant overrides, so applying
one is a mechanical substitution into `theme.colour`.

| | What it does |
| --- | --- |
| **A — Birch** | Near-white paper, white cards. Lighter than the current palette, but the white cards push the green back rather than forward. |
| **B — Moss** | The page goes green, cards stay white. The green reads as a choice rather than an accent, and the white cards gain definition. |
| **C — Fern** | The strongest green that passes the contrast thresholds. |

## Why C is as pale as it is

The first attempt at C failed three checks in `app/test/theme.test.ts`:
`danger` on the green chrome at 6.88:1 against a floor of 7, body text at
11.27:1 against a floor of 12, and a border heavy enough to compete with the
cards it outlines. The greens were lightened until it passed rather than the
thresholds being relaxed.

**That is the ceiling on how green this app can be.** Push the chrome darker
and the lethal-ambiguity warning stops clearing AAA — and that warning is the
one thing on a screen that has to be the easiest thing to read.

## What none of them change

The accent stays gold. A green accent fails the hue test in `theme.test.ts`,
and the test is right to refuse it: the accent is the primary action — the
control that advances an identification — and green there is the one place in
this app where green genuinely reads as permission. Green is chrome, never a
verdict. See `docs/POSITIONING.md`.
