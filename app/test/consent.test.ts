/**
 * Onboarding consent, and the emergency text that sits outside it.
 *
 * The interesting cases are the two directions of failure: letting someone
 * through who has not been told what the app does not do, and locking
 * someone out of their own app over a dropped connection.
 */

import { beforeEach, describe, expect, it } from 'vitest';

import {
  consentState,
  gate,
  isComplete,
  outstanding,
  readConsent,
  recordConsent,
  withdrawConsent,
} from '../src/lib/consent';
import { EMERGENCY_HEADLINE, EMERGENCY_STEPS } from '../src/lib/emergency';
import { control } from './asyncStorageDouble';

beforeEach(() => control.reset());

const ACKS = [{ key: 'a' }, { key: 'b' }, { key: 'c' }];

describe('the gate', () => {
  it('asks on a device that has never consented', () => {
    expect(gate(null, 'v1')).toBe('consent');
  });

  it('asks again when the text has changed', async () => {
    // The version is derived from the text, so this is a changed statement,
    // not a bumped constant. Agreeing to an older statement is not agreeing
    // to a newer one.
    await recordConsent('v1', ['a']);
    expect(gate(await readConsent(), 'v2')).toBe('consent');
    expect(consentState(await readConsent(), 'v2')).toBe('stale');
  });

  it('lets a consented user in when it cannot reach the service', async () => {
    // Everything else needs the network, but locking someone out of their own
    // observation log over a blip is not a safety measure.
    await recordConsent('v1', ['a']);
    expect(gate(await readConsent(), null)).toBe('allow');
  });

  it('still asks an unconsented user when it cannot reach the service', () => {
    // The failure here is an app that cannot be used offline on first launch,
    // which it could not be anyway. The opposite failure is someone using it
    // having never been shown the disclaimer.
    expect(gate(null, null)).toBe('consent');
  });

  it('lets a consented user in when nothing has changed', async () => {
    await recordConsent('v1', ['a', 'b', 'c']);
    expect(gate(await readConsent(), 'v1')).toBe('allow');
  });
});

describe('the form', () => {
  it('requires every statement separately', () => {
    // There is no "accept all". A user who ticked three of four has not
    // agreed to the fourth.
    expect(isComplete({ a: true, b: true }, ACKS)).toBe(false);
    expect(isComplete({ a: true, b: true, c: true }, ACKS)).toBe(true);
    expect(outstanding({ a: true }, ACKS)).toBe(2);
  });

  it('cannot be satisfied by an empty list of statements', () => {
    // A disclaimer that failed to load must not read as one with nothing to
    // agree to.
    expect(isComplete({}, [])).toBe(false);
  });

  it('does not count an untick as agreement', () => {
    expect(isComplete({ a: true, b: true, c: false }, ACKS)).toBe(false);
  });
});

describe('the stored record', () => {
  it('round-trips the version and the statements seen', async () => {
    await recordConsent('v1', ['a', 'b'], 1_700_000_000_000);
    const stored = await readConsent();
    expect(stored).toEqual({
      version: 'v1',
      acknowledgedAt: 1_700_000_000_000,
      keys: ['a', 'b'],
    });
  });

  it('treats a damaged record as no consent rather than as agreement', async () => {
    // One extra onboarding screen is the cost of being wrong this way.
    // Reading a damaged record as agreement costs someone the disclaimer.
    for (const raw of ['not json', '{}', '{"version":""}', '{"version":"v1"}', 'null']) {
      control.seed('onboarding-consent', raw);
      expect(await readConsent(), raw).toBeNull();
      expect(gate(await readConsent(), 'v1')).toBe('consent');
    }
  });

  it('treats unreadable storage as no consent', async () => {
    await recordConsent('v1', ['a']);
    control.failReads = true;
    expect(await readConsent()).toBeNull();
  });

  it('reports a failed write, so the caller does not proceed on nothing', async () => {
    // `docs/SAFETY.md` asks for consent to be *recorded*. Proceeding on a
    // write that failed leaves no record that the disclaimer was shown.
    control.failWrites = true;
    expect(await recordConsent('v1', ['a'])).toBe(false);
  });

  it('can be withdrawn, which puts the gate back', async () => {
    await recordConsent('v1', ['a']);
    await withdrawConsent();
    expect(gate(await readConsent(), 'v1')).toBe('consent');
  });
});

describe('the emergency text', () => {
  it('is a constant, so it cannot fail to load', () => {
    // The one screen that must never need a network, because a wood is
    // exactly where there is not one.
    expect(EMERGENCY_STEPS.length).toBeGreaterThan(0);
    expect(EMERGENCY_HEADLINE).toBeTruthy();
  });

  it('leads with the call, not with an explanation', () => {
    expect(EMERGENCY_STEPS[0].body).toContain('999');
    expect(EMERGENCY_STEPS[0].body).toContain('111');
    expect(EMERGENCY_STEPS[0].heading.toLowerCase()).toContain('call');
  });

  it('says not to wait for symptoms', () => {
    // The amatoxin latent period is the reason people present too late.
    const all = EMERGENCY_STEPS.map((s) => `${s.heading} ${s.body}`).join(' ').toLowerCase();
    expect(all).toMatch(/do not wait for symptoms/);
    expect(all).toMatch(/latent period/);
  });

  it('tells them to bring the specimen', () => {
    const all = EMERGENCY_STEPS.flatMap((s) => [s.heading, s.body])
      .join(' ')
      .toLowerCase();
    expect(all).toMatch(/take the mushroom/);
    expect(all).toMatch(/poor substitute for the specimen/);
  });

  it('asserts no edibility, the same as every other user-facing string', () => {
    const all = [EMERGENCY_HEADLINE, ...EMERGENCY_STEPS.flatMap((s) => [s.heading, s.body])]
      .join(' ')
      .toLowerCase();
    for (const claim of ['is edible', 'are edible', 'safe to eat', 'good to eat']) {
      // Allowed only inside a negation, as on the server.
      const at = all.indexOf(claim);
      if (at === -1) continue;
      const sentence = all.slice(all.lastIndexOf('.', at) + 1, all.indexOf('.', at) + 1);
      expect(sentence, claim).toMatch(/never|not|cannot|can't|does not|whether/);
    }
  });
});
