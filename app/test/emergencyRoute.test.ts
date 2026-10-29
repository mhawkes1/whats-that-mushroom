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
    expect(capture).toMatch(/navigation\.navigate\('Emergency'\)/);
  });

  it('is a labelled button, not a bare glyph', () => {
    const capture = read('screens/CaptureScreen.tsx');
    expect(capture).toMatch(/accessibilityLabel="[^"]*eaten[^"]*"/i);
    // A screen reader user in an emergency needs words, not a symbol.
    expect(capture).toMatch(/Someone has eaten a wild mushroom/);
  });

  it('is PINNED, so it cannot be scrolled off', () => {
    // This is the whole guarantee, and the mechanism carrying it changed
    // on 2026-10-29.
    //
    // It used to be the compact control in the header -- above the fold by
    // construction, because the header is the first thing rendered. Martin
    // dropped that to free the corner for starting another mushroom, which
    // is what users were already trying to use it for.
    //
    // What was left was the full-width button at the END OF THE SCROLL.
    // That is below the fold on any phone shorter than the content, so
    // dropping the header control without pinning this one would have
    // quietly removed the guarantee while leaving a button that looks like
    // it provides it. The button now sits outside the ScrollView.
    const capture = read('screens/CaptureScreen.tsx');
    const closeScroll = capture.indexOf('</ScrollView>');
    const emergency = capture.indexOf('onPress={() => navigation.navigate(\'Emergency\')}');
    expect(closeScroll).toBeGreaterThan(-1);
    expect(emergency).toBeGreaterThan(-1);
    expect(emergency).toBeGreaterThan(closeScroll);
  });

  it('does not share the corner with anything that means "add"', () => {
    // The route was drawn as a heavy greek cross -- a plus -- in the top
    // right corner, which is where every app puts "add a new one". Martin
    // read it as exactly that in ordinary use and reached for it to add a
    // second mushroom.
    //
    // The compounding failure is what made it a safety bug: tap it, get
    // the emergency screen, learn the button is wrong, and you have been
    // trained away from the one control that has to work. Invisible to
    // the accessibility test, because the label was always right.
    //
    // The corner now does mean "add", and the emergency route is not in
    // it. What must never return is both at once.
    const header = read('components/AppHeader.tsx');
    for (const glyph of ['\u271a', '\u271b', '\u2795', '+']) {
      expect(header.includes(`>${glyph}<`)).toBe(false);
    }
    expect(header).not.toMatch(/Emergency/);
    expect(header).not.toMatch(/onEmergency/);
  });

  it('is never the same colour as the control beside it', () => {
    // Red is the emergency route's colour throughout. A red button in the
    // corner that used to hold the emergency route would be the original
    // confusion with the arguments reversed.
    const header = read('components/AppHeader.tsx');
    expect(header).not.toMatch(/backgroundColor: theme\.colour\.danger\b/);
    const capture = read('screens/CaptureScreen.tsx');
    expect(capture).toMatch(/dangerSurface/);
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
