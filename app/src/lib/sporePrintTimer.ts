/**
 * The wait.
 *
 * A spore print takes between two and twelve hours, which is far longer than
 * an app session. The timer therefore lives in storage rather than in state:
 * the user starts it, closes the app, and comes back the next morning to a
 * screen that knows how long it has been.
 *
 * The time arithmetic is kept pure and separate from the storage so it can be
 * reasoned about directly. Everything is derived from a single stored
 * timestamp rather than from a running countdown, because a countdown does not
 * survive the process being killed and a timestamp does.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';

const STORAGE_KEY = 'spore-print-timer';

/** Below this the deposit is usually too thin to judge a colour from. */
export const MINIMUM_WAIT_MS = 2 * 60 * 60 * 1000;

/** Past this there is nothing further to gain by waiting. */
export const IDEAL_WAIT_MS = 12 * 60 * 60 * 1000;

/**
 * A print left far longer than a day has usually dried out, and the paper
 * may have absorbed moisture and discoloured. We do not refuse it -- the
 * user can see their own print -- but we stop implying it is fine.
 */
export const STALE_WAIT_MS = 36 * 60 * 60 * 1000;

export interface SporePrintTimer {
  /** Milliseconds since the epoch, as `Date.now()` recorded it. */
  startedAt: number;
  /** The observation this print belongs to, so a stale timer is recognisable. */
  observationId: string;
}

export type Readiness = 'too-soon' | 'usable' | 'ready' | 'stale';

export interface WaitStatus {
  elapsedMs: number;
  readiness: Readiness;
  /** What to tell the user about where they are in the wait. */
  summary: string;
}

function plural(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? '' : 's'}`;
}

export function formatElapsed(elapsedMs: number): string {
  if (elapsedMs < 60 * 1000) return 'less than a minute';
  const minutes = Math.floor(elapsedMs / (60 * 1000));
  if (minutes < 60) return plural(minutes, 'minute');
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  if (hours < 24) {
    return remainder === 0
      ? plural(hours, 'hour')
      : `${plural(hours, 'hour')} ${plural(remainder, 'minute')}`;
  }
  const days = Math.floor(hours / 24);
  const leftoverHours = hours % 24;
  // Days alone are too coarse here: 24 hours and 40 hours both read as
  // "1 day", and the app says different things about them -- one print is at
  // its best and the other has probably dried out.
  return leftoverHours === 0
    ? plural(days, 'day')
    : `${plural(days, 'day')} ${plural(leftoverHours, 'hour')}`;
}

/**
 * Where the wait has got to.
 *
 * `usable` rather than `ready` between two and twelve hours is deliberate:
 * the print can be read, but a longer wait gives a denser deposit and a more
 * reliable colour, and the user should be told that rather than nudged to
 * hurry. Nothing here blocks them from looking early.
 */
export function waitStatus(elapsedMs: number): WaitStatus {
  const elapsed = Math.max(0, elapsedMs);
  const human = formatElapsed(elapsed);

  if (elapsed < MINIMUM_WAIT_MS) {
    const remaining = formatElapsed(MINIMUM_WAIT_MS - elapsed);
    return {
      elapsedMs: elapsed,
      readiness: 'too-soon',
      summary: `${human} so far. Give it about ${remaining} more before looking — a thin deposit reads as the wrong colour.`,
    };
  }
  if (elapsed < IDEAL_WAIT_MS) {
    return {
      elapsedMs: elapsed,
      readiness: 'usable',
      summary: `${human} so far. You can read it now, but leaving it until the full twelve hours gives a denser deposit and a truer colour.`,
    };
  }
  if (elapsed < STALE_WAIT_MS) {
    return {
      elapsedMs: elapsed,
      readiness: 'ready',
      summary: `${human}. The print should be at its best now.`,
    };
  }
  return {
    elapsedMs: elapsed,
    readiness: 'stale',
    summary: `${human}. That is long enough for the print to dry out or the paper to discolour. Judge the colour by eye as well, or start a fresh print.`,
  };
}

// --- Storage -----------------------------------------------------------------
//
// Every accessor swallows its own failure. Storage can be unavailable, and a
// timer that cannot be read is a reason to offer starting a new one, never a
// reason to crash the screen the user opened to read their print.

export async function startTimer(observationId: string): Promise<SporePrintTimer> {
  const timer: SporePrintTimer = { startedAt: Date.now(), observationId };
  try {
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(timer));
  } catch {
    // Not fatal: the screen falls back to an un-timed flow.
  }
  return timer;
}

export async function readTimer(): Promise<SporePrintTimer | null> {
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<SporePrintTimer>;
    if (typeof parsed?.startedAt !== 'number' || !Number.isFinite(parsed.startedAt)) {
      return null;
    }
    // A timestamp in the future means the device clock moved. Treat it as
    // unusable rather than reporting a negative wait.
    if (parsed.startedAt > Date.now()) return null;
    return {
      startedAt: parsed.startedAt,
      observationId: String(parsed.observationId ?? ''),
    };
  } catch {
    return null;
  }
}

export async function clearTimer(): Promise<void> {
  try {
    await AsyncStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing to do: a stale timer is a nuisance, not a hazard.
  }
}
