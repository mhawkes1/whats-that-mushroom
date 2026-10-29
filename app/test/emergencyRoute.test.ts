import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

/**
 * The emergency route, guarded at the source level.
 *
 * `EmergencyScreen` is the one screen that must never fail: it is hardcoded,
 * offline, ungated, and it sits above the consent gate because somebody whose
 * child has eaten something is not going to complete an onboarding flow.
 *
 * None of that helps if the front page stops offering a way to reach it. The
 * route used to hang off the book cover's top corner; the cover was removed
 * on 2026-09-29 and the button had to move with it. That is precisely the
 * kind of change that silently costs an app its panic button, and vitest
 * cannot drive the React Native renderer to catch it, so these read the
 * source instead. Cruder than a render test and considerably better than
 * nothing.
 */
const SRC = resolve(__dirname, '..', 'src');
const read = (p: string) => readFileSync(resolve(SRC, p), 'utf8');

describe('the emergency route', () => {
  it('is offered by the front page', () => {
    const capture = read('screens/CaptureScreen.tsx');
    expect(capture).toMatch(/onEmergency=\{\(\) =>\s*navigation\.navigate\('Emergency'\)/);
  });

  it('is a labelled button in the header, not a bare glyph', () => {
    const header = read('components/AppHeader.tsx');
    expect(header).toContain('onPress={onEmergency}');
    expect(header).toContain("accessibilityRole=\"button\"");
    // A screen reader user in an emergency needs words, not a plus sign.
    expect(header).toMatch(/accessibilityLabel="[^"]*eaten[^"]*"/i);
  });

  it('does not render as a plus sign', () => {
    // It was drawn as a heavy greek cross, which is a plus, in the top
    // right corner, which is where every app puts "add a new one". Martin
    // read it as exactly that in ordinary use on 2026-10-29 and reached
    // for it to add a second mushroom.
    //
    // The compounding failure is what makes this a safety bug rather than
    // a papercut: tap it, get the emergency screen, learn the button is
    // wrong, and you have been trained away from the one control that has
    // to work when it matters. Invisible to the accessibility test,
    // because the label was always right; it was only wrong to look at.
    const header = read('components/AppHeader.tsx');
    for (const glyph of ['✚', '✛', '➕', '+']) {
      expect(header.includes(`>${glyph}<`)).toBe(false);
    }
    // Words, which need no learning at the one moment nobody is learning.
    expect(header).toMatch(/EATEN/);
  });

  it('is positioned without needing a scroll', () => {
    const header = read('components/AppHeader.tsx');
    // The header is the first thing the capture screen renders, so the
    // control is above the fold by construction. Assert it stays there.
    const capture = read('screens/CaptureScreen.tsx');
    const firstChild = capture.indexOf('<AppHeader');
    const anythingElse = capture.indexOf('<View style={styles.header}>');
    expect(firstChild).toBeGreaterThan(-1);
    expect(firstChild).toBeLessThan(anythingElse);
    // And that it is a real target rather than a few pixels of text.
    // Asserted as the platform minimum in each dimension rather than as a
    // literal `width: 44`: the control went from a 44x44 circle to a
    // 64x44 rounded rectangle when the plus-sign glyph was replaced with
    // words, which is larger, and the old literal would have failed a
    // change that made the target better.
    const w = header.match(/min(?:Width|Height): (\d+)/g) ?? [];
    expect(w.length).toBeGreaterThanOrEqual(2);
    for (const dim of w) {
      expect(Number(dim.split(': ')[1])).toBeGreaterThanOrEqual(44);
    }
    expect(header).toMatch(/hitSlop/);
  });

  it('leaves no reference to the removed cover', () => {
    for (const file of [
      'screens/CaptureScreen.tsx',
      'components/AppHeader.tsx',
      'lib/theme.ts',
    ]) {
      expect(read(file)).not.toContain('CoverHeader');
    }
  });
});
