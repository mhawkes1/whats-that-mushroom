import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import { theme } from '../src/lib/theme';

/**
 * The palette went from near-black to paper on 2026-10-19, and two things
 * about it are safety properties rather than taste.
 *
 * A hazard colour chosen for a dark ground is too light for a pale one. The
 * old `danger` (#e5484d) reads at about 3:1 against paper, which is below
 * the threshold for body text at any size -- so the warning that matters
 * most would have been the hardest thing on the screen to read. These tests
 * exist so a future palette change cannot quietly undo that.
 *
 * And green: `POSITIONING.md` kept it out of the palette because green is
 * the colour of permission. The light theme brings woodland greens back as
 * chrome, which is a different thing -- but only if nothing semantic uses
 * them, which is what the second test pins.
 */

function luminance(hex: string): number {
  const v = hex.replace('#', '');
  const channels = [0, 2, 4].map((i) => {
    const c = parseInt(v.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

describe('hazard colours stay readable on their own surfaces', () => {
  const pairs: [string, string, string][] = [
    ['danger on its surface', theme.colour.danger, theme.colour.dangerSurface],
    ['danger on the page', theme.colour.danger, theme.colour.background],
    ['danger on a card', theme.colour.danger, theme.colour.surface],
    ['caution on its surface', theme.colour.caution, theme.colour.cautionSurface],
    ['caution on a card', theme.colour.caution, theme.colour.surface],
  ];

  // AA for body text is 4.5:1. A lethal-ambiguity warning gets AAA.
  it.each(pairs)('%s clears 4.5:1', (_label, fg, bg) => {
    expect(contrast(fg, bg)).toBeGreaterThanOrEqual(4.5);
  });

  it('danger clears AAA, 7:1, on every ground it appears on', () => {
    for (const bg of [
      theme.colour.dangerSurface,
      theme.colour.background,
      theme.colour.surface,
    ]) {
      expect(contrast(theme.colour.danger, bg)).toBeGreaterThanOrEqual(7);
    }
  });

  it('body and muted text are readable on paper', () => {
    expect(contrast(theme.colour.text, theme.colour.background)).toBeGreaterThanOrEqual(12);
    expect(contrast(theme.colour.textMuted, theme.colour.background)).toBeGreaterThanOrEqual(4.5);
  });
});

describe('labels on filled controls stay readable', () => {
  /**
   * The light palette broke every primary button at once, because screens
   * wrote `color: theme.colour.background` for a label on a gold button.
   * That was only ever correct while the background was near-black. The
   * role is now named, and these pin it.
   */
  it('onAccent reads on every filled control it sits on', () => {
    for (const bg of [
      theme.colour.accent,
      theme.colour.danger,
      theme.colour.canopy,
      theme.colour.confident,
    ]) {
      expect(contrast(theme.colour.onAccent, bg)).toBeGreaterThanOrEqual(4.5);
    }
  });

  it('a disabled label reads on the disabled ground', () => {
    expect(
      contrast(theme.colour.onDisabled, theme.colour.surfaceRaised),
    ).toBeGreaterThanOrEqual(3);
  });

  it('onAccent is not usable as body text, so it cannot be misapplied', () => {
    expect(
      contrast(theme.colour.onAccent, theme.colour.background),
    ).toBeLessThan(1.5);
  });
});

describe('green never states an outcome', () => {
  /**
   * The hue test, rather than a list of names: any future colour that is
   * dominantly green has to come here and justify itself.
   *
   * **`accent` joined this list on 2026-10-31 and that is a real
   * loosening**, so it is worth being exact about what it does and does not
   * licence. Green became the brand: the masthead, the tab glyphs, the count
   * tile for species the app could name, and the button that opens the
   * camera. None of those states an outcome about a mushroom. The original
   * argument in `POSITIONING.md` was about green *attached to something* --
   * a verdict, a hazard line, a confidence marker -- and that is untouched.
   *
   * Because an allowlist that grows is an allowlist that stops meaning
   * anything, the test below this one names the colours that can never be
   * green whatever anyone adds here. If a future change wants `confident` or
   * a hazard colour in moss, it has to delete an assertion with a reason
   * written next to it, rather than appending a string.
   */
  const GREEN_BY_DESIGN = new Set([
    'accent', 'canopy', 'lichen', 'canopySurface', 'canopyInk', 'onCanopyInk',
  ]);
  const CHROME = GREEN_BY_DESIGN;

  function isGreen(hex: string): boolean {
    const v = hex.replace('#', '');
    const [r, g, b] = [0, 2, 4].map((i) => parseInt(v.slice(i, i + 2), 16));
    return g > r + 12 && g > b + 12;
  }

  it.each(Object.entries(theme.colour))('%s is not green unless it is chrome', (name, hex) => {
    if (CHROME.has(name)) return;
    expect(isGreen(hex), `${name} (${hex}) is green and is not chrome`).toBe(false);
  });

  it('the colours that state something are never green, allowlist or not', () => {
    // The backstop for the paragraph above. These are the colours attached
    // to a claim about a mushroom rather than to the app's own furniture,
    // and no amount of brand evolution makes a green one of them correct.
    // `danger` and `caution` because a hazard in the colour of permission is
    // the single worst thing this palette could do; `confident` because it
    // sits beside a species name; the text colours because a sentence about
    // a mushroom is the most direct claim the app makes.
    for (const name of [
      'danger',
      'dangerSurface',
      'caution',
      'cautionSurface',
      'confident',
      'text',
      'textMuted',
      'textFaint',
    ] as const) {
      expect(
        GREEN_BY_DESIGN.has(name),
        `${name} states something; it must never be listed as green by design`,
      ).toBe(false);
      expect(isGreen(theme.colour[name]), `${name} is ${theme.colour[name]}`).toBe(false);
    }
  });

  it('confident is not green, because it is attached to an identification', () => {
    expect(CHROME.has('confident')).toBe(false);
    expect(isGreen(theme.colour.confident)).toBe(false);
    // Nor warm, which would make it read as a hazard. Luminance contrast is
    // the wrong instrument here -- a deep blue and a deep red can sit at
    // nearly the same luminance and still be unmistakable -- so this tests
    // the hue instead.
    const [r, , b] = [0, 2, 4].map((i) =>
      parseInt(theme.colour.confident.replace('#', '').slice(i, i + 2), 16),
    );
    expect(b).toBeGreaterThan(r + 20);
  });
});

describe('the ink panel is readable', () => {
  /**
   * The one block of solid colour in the app, carrying the paragraph that
   * is the product's entire argument. Two colours sit on it and both have
   * to work, because a panel nobody can read is worse than the cream card
   * it replaced -- that one was merely invisible as an object.
   */
  it('both weights of text clear AAA on the ink panel', () => {
    expect(contrast(theme.colour.onAccent, theme.colour.canopyInk)).toBeGreaterThanOrEqual(7);
    expect(contrast(theme.colour.onCanopyInk, theme.colour.canopyInk)).toBeGreaterThanOrEqual(7);
  });

  it('the panel is the heaviest thing on the page', () => {
    // Heavier than the accent control, which is the only other filled
    // element. If that ever inverts, the loudest thing on the home screen
    // becomes a button rather than the sentence about not eating things.
    const weight = (hex: string) => contrast(hex, theme.colour.background);
    expect(weight(theme.colour.canopyInk)).toBeGreaterThan(weight(theme.colour.accent));
  });

  it('body text on the panel is not usable on the page', () => {
    // So it cannot be reached for as a general muted colour; it is a role,
    // not a shade. Same mistake shape as `color: theme.colour.background`
    // for a label on a filled button.
    expect(contrast(theme.colour.onCanopyInk, theme.colour.background)).toBeLessThan(2.5);
  });
});

describe('hazard emphasis is ordered', () => {
  /**
   * The stripe on a candidate row must get *fainter* as the hazard gets
   * milder, and faintest of all where there is no hazard. On the light
   * palette the no-hazard case fell through to `textMuted` and drew a
   * darker bar than a TOXIC row's amber, so the species the app had
   * nothing to say about was the loudest thing in the list.
   */
  function weight(hex: string): number {
    // How far the colour is from the page it sits on.
    return contrast(hex, theme.colour.surface);
  }

  it('deadly is heavier than toxic, which is heavier than no hazard', () => {
    const deadly = weight(theme.colour.danger);
    const toxic = weight(theme.colour.caution);
    const none = weight(theme.colour.border);

    expect(deadly).toBeGreaterThan(toxic);
    expect(toxic).toBeGreaterThan(none);
  });

  it('a row with no hazard barely marks the page at all', () => {
    expect(weight(theme.colour.border)).toBeLessThan(1.6);
  });
});

describe('the palette is the only place colours live', () => {
  /**
   * The point of this one is that changing the colour scheme must be a
   * one-file job. It is the question Martin asked on 2026-10-20 — can the
   * palette still be changed later — and the honest answer depended on
   * this being true.
   *
   * It was not quite. `SporePrintScreen` set a label's background to a
   * hardcoded `rgba(0,0,0,0.6)` with `theme.colour.text` on top. That read
   * correctly while the palette was near-black and became near-black ink on
   * a near-black scrim the moment it went to paper — invisible, on the
   * labels that tell a user which box holds the spore deposit and which
   * holds the white card.
   *
   * The contrast tests above could not catch it, because the background was
   * not a token. This catches the shape of the mistake instead.
   */
  const SRC = join(__dirname, '..', 'src');

  function sources(dir: string): string[] {
    return readdirSync(dir).flatMap((entry) => {
      const path = join(dir, entry);
      if (statSync(path).isDirectory()) return sources(path);
      return /\.tsx?$/.test(path) && !path.endsWith('theme.ts') ? [path] : [];
    });
  }

  it.each(sources(SRC).map((f) => [f.slice(f.indexOf('src')), f]))(
    '%s names no colour of its own',
    (_label, path) => {
      const code = readFileSync(path, 'utf8')
        // Comments may discuss a hex value; code may not use one.
        .replace(/\/\*[\s\S]*?\*\//g, '')
        .replace(/^\s*\/\/.*$/gm, '');
      const literals = code.match(/#[0-9a-fA-F]{3,8}\b|\brgba?\([^)]*\)/g) ?? [];
      expect(literals, `define it in theme.ts instead: ${literals}`).toEqual([]);
    },
  );

  it('a scrim over a photograph takes light text, never body text', () => {
    // The photograph underneath is not themed, so the scrim stays dark in
    // every palette and `text` is the wrong colour on it in any of them.
    expect(contrast(theme.colour.onAccent, '#000000')).toBeGreaterThanOrEqual(7);
    expect(contrast(theme.colour.text, '#000000')).toBeLessThan(3);
  });
});
