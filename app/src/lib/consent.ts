/**
 * Onboarding consent.
 *
 * A blocking item in `docs/SAFETY.md`: the disclaimer must be shown and
 * acknowledged before first use.
 *
 * ## Consent is to a version, not to the idea of a disclaimer
 *
 * The stored record carries the version of the text that was acknowledged.
 * The server derives that version from the text itself, so a change to a
 * single word produces a different one and the stored consent is stale. This
 * matters here more than in most apps, because the statements genuinely
 * change: while there is no trained model, no fitted calibration and no
 * reviewed taxonomy, the user is asked to acknowledge each of those, and when
 * one becomes true the thing they agreed to is no longer what the app does.
 *
 * ## Every claim is ticked separately
 *
 * `isComplete` requires each acknowledgement individually. One blanket "I
 * agree" is a formality, and a formality is what people learn to tap past.
 * The stored record keeps the keys, so a later version can tell which
 * statements a user has actually seen.
 *
 * ## Offline
 *
 * First use needs the network, which costs nothing that is not already lost:
 * identifying anything is a network call. But a user who has consented and
 * then goes offline is not asked again -- `gate` returns `allow` on a
 * consented device it cannot re-check. Locking someone out of their own
 * observation log over a dropped connection is not a safety measure.
 *
 * The emergency screen is outside all of this. See `emergency.ts`.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';

const STORAGE_KEY = 'onboarding-consent';

export interface Consent {
  /** The disclaimer version acknowledged, as the server derived it. */
  version: string;
  acknowledgedAt: number;
  /** Which statements were ticked, so a later version can tell what is new. */
  keys: string[];
}

export type ConsentState = 'none' | 'stale' | 'current';

export function consentState(
  stored: Consent | null,
  currentVersion: string | null,
): ConsentState {
  if (!stored) return 'none';
  // Nothing to compare against. The stored consent is the best fact available
  // and is not invalidated by a failed request.
  if (!currentVersion) return 'current';
  return stored.version === currentVersion ? 'current' : 'stale';
}

/** Where to send someone on launch. */
export type Gate = 'allow' | 'consent';

export function gate(stored: Consent | null, currentVersion: string | null): Gate {
  return consentState(stored, currentVersion) === 'current' ? 'allow' : 'consent';
}

/**
 * Whether the form may be submitted.
 *
 * Every statement, individually. There is no "accept all" and there is no
 * partial consent: a user who ticks three of four has not agreed to the
 * fourth, and proceeding anyway would make the whole exercise decorative.
 */
export function isComplete(
  ticked: Record<string, boolean>,
  acknowledgements: { key: string }[],
): boolean {
  return (
    acknowledgements.length > 0 &&
    acknowledgements.every((ack) => ticked[ack.key] === true)
  );
}

/** What is still unticked, so the form can say so rather than just refusing. */
export function outstanding(
  ticked: Record<string, boolean>,
  acknowledgements: { key: string }[],
): number {
  return acknowledgements.filter((ack) => ticked[ack.key] !== true).length;
}

// --- Storage -----------------------------------------------------------------

function isConsent(value: unknown): value is Consent {
  const c = value as Partial<Consent> | null;
  return (
    !!c &&
    typeof c === 'object' &&
    typeof c.version === 'string' &&
    c.version.length > 0 &&
    typeof c.acknowledgedAt === 'number' &&
    Number.isFinite(c.acknowledgedAt) &&
    Array.isArray(c.keys)
  );
}

/**
 * A record that does not parse is treated as no consent.
 *
 * The failure is one extra onboarding screen. The opposite failure -- reading
 * a damaged record as agreement -- is someone using the app without having
 * been told what it does not do.
 */
export async function readConsent(): Promise<Consent | null> {
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    return isConsent(parsed)
      ? { version: parsed.version, acknowledgedAt: parsed.acknowledgedAt, keys: [...parsed.keys] }
      : null;
  } catch {
    return null;
  }
}

/**
 * Returns false if it could not be saved, and the caller must not proceed.
 *
 * Letting someone through on a consent that was never written means the next
 * launch asks again, which is merely annoying -- but it also means the app
 * has no record that the disclaimer was ever shown, which is the thing
 * `docs/SAFETY.md` requires.
 */
export async function recordConsent(
  version: string,
  keys: string[],
  now: number = Date.now(),
): Promise<boolean> {
  const consent: Consent = { version, acknowledgedAt: now, keys: [...keys] };
  try {
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(consent));
    return true;
  } catch {
    return false;
  }
}

/** For "show me that again" -- and for testing that the gate actually gates. */
export async function withdrawConsent(): Promise<void> {
  try {
    await AsyncStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing to do. The next launch reads whatever is still there.
  }
}
