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
  it('is NOT on the front page, and that is deliberate', () => {
    // Martin's call, 2026-10-29, after two rounds of me arguing for it:
    // "I don't want the app to seem alarming from the off. And it looks
    // as if something is wrong."
    //
    // That is a product judgement about the first three seconds of the
    // app, and it is his to make. Recorded in docs/SAFETY.md rather than
    // deleted quietly, because that file had listed the front-page route
    // as a requirement and a dropped requirement must say so.
    //
    // This test exists so the removal stays a decision rather than
    // becoming an accident: if a future change puts it back on the
    // capture screen, somebody should have to come here and read why it
    // left.
    const capture = read('screens/CaptureScreen.tsx');
    expect(capture).not.toMatch(/navigate\('Emergency'\)/);
  });

  it('is still reachable, by more than one route', () => {
    // Removing it from the front page is not the same as removing it.
    // The screen is hardcoded, offline and sits above the consent gate,
    // and none of that matters if nothing navigates to it.
    const routes = ['screens/ConsentScreen.tsx', 'screens/ReportScreen.tsx']
      .filter((f) => /navigate\('Emergency'\)/.test(read(f)));
    expect(routes.length).toBeGreaterThanOrEqual(2);
  });

  it('is reached without the network, and before consent', () => {
    // The two properties that make this screen different from every
    // other one. Everything else a user reads is served so that one copy
    // of it exists; this is hardcoded because a wood is exactly where the
    // network is not, and it sits above the gate because a safety gate
    // standing between a frightened person and "call 999" is not a
    // safety gate.
    const screen = read('screens/EmergencyScreen.tsx');
    expect(screen).toMatch(/999/);
    expect(screen).toMatch(/111/);
    // No fetch, no api import: it must render with the radio off.
    expect(screen).not.toMatch(/from '\.\.\/lib\/api'/);
    expect(screen).not.toMatch(/fetch\(/);
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
