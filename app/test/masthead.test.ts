import { readFileSync, statSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

/**
 * The masthead, guarded at the source level.
 *
 * A photograph returned to the front page on 2026-10-31, eighteen months of
 * project-time after the book cover was taken off it. Three of the four
 * things that make it safe to have there are invisible to any renderer
 * vitest can drive, and the fourth fails only at build time on a real
 * device, so these read the source and the asset instead.
 *
 * The one that is not here is the emergency route, because removing the
 * cover is what nearly cost the app its panic button last time.
 * `emergencyRoute.test.ts` has held that line since and still does.
 */
const APP = resolve(__dirname, '..');
const read = (p: string) => readFileSync(resolve(APP, p), 'utf8');
const header = () => read('src/components/AppHeader.tsx');

describe('the masthead', () => {
  it('ships both assets, because a missing one stops an Expo build', () => {
    // Same reason icons.test.ts exists. `require` of a missing asset is a
    // bundler error, which surfaces long after anybody has stopped looking
    // at this component.
    for (const asset of ['assets/masthead.jpg', 'assets/mark-cream.png']) {
      const size = statSync(resolve(APP, asset)).size;
      expect(size, `${asset} is missing or empty`).toBeGreaterThan(1024);
    }
  });

  it('puts its text on the scrim token, never a literal', () => {
    // What is underneath is a photograph. It is not themed and cannot be
    // reasoned about from the palette, which is why `theme.ts` names a
    // scrim for exactly this and why `theme.test.ts` bans colour literals
    // outside that file. A hardcoded rgba() here is how SporePrintScreen
    // ended up with near-black ink on a near-black scrim.
    expect(header()).toMatch(/theme\.colour\.photoScrim/);
    expect(header()).not.toMatch(/rgba\(/);
    expect(header()).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });

  it('uses onAccent for every word over the photograph', () => {
    // The rule `theme.ts` states in both directions: text on photoScrim is
    // onAccent and never `text`. On paper `text` is near-black ink, which
    // over a dark scrim is invisible -- and invisible is what the title,
    // the rule and the tagline would all be.
    const src = header();
    const colours = [...src.matchAll(/color:\s*theme\.colour\.(\w+)/g)].map((m) => m[1]);
    expect(colours.length).toBeGreaterThan(0);
    for (const c of colours) expect(c).toBe('onAccent');
    // And the rule under the title, which is a background rather than a
    // colour and so would slip past the check above.
    expect(src).toMatch(/backgroundColor:\s*theme\.colour\.onAccent/);
  });

  it('does not reintroduce the cover', () => {
    // Not a naming quibble. `CoverHeader` was a full reproduction of the
    // book jacket -- a cep filling the frame, lit as a portrait. That
    // composition is the thing this photograph was chosen to avoid, so a
    // file reappearing under that name is the regression, not the string.
    expect(header()).not.toContain('CoverHeader');
    expect(header()).not.toContain('cover.jpg');
  });

  it('keeps the tagline, which is what the name cannot say', () => {
    // "Funga" tells a beginner nothing about mushrooms. That was the
    // accepted cost of the name, and this sentence is what pays it.
    expect(header()).toMatch(/I'll tell you when I can't tell/);
  });

  it('hides the decorative images from screen readers', () => {
    // Two images, neither carrying information the title does not. A
    // reader announcing them before the app's own name is noise, and
    // noise at the top of the first screen is where people stop
    // listening.
    const src = header();
    expect(src.match(/accessibilityElementsHidden/g) ?? []).toHaveLength(2);
    expect(src.match(/importantForAccessibility="no"/g) ?? []).toHaveLength(2);
  });
});
