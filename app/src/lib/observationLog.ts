/**
 * The observation log.
 *
 * What the user photographed, where and when, and what the app was willing to
 * say about it. Local to the device; nothing here is uploaded.
 *
 * ## Why a history is a safety feature and not a trophy cabinet
 *
 * At the moment of identification the user sees the whole answer: the verdict,
 * the refusal if there was one, the warnings, the question that would settle
 * it. Three weeks later they see a thumbnail and whatever text sits beside it.
 * Everything that made the original answer honest has fallen away, and the
 * strongest thing left on the row is what they will remember.
 *
 * So the log stores the verdict, not the name. `summarise` leads with what the
 * app was willing to assert, and for every verdict except `species` it names
 * no species at all -- the same rule the API shape already enforces, where
 * there is no field carrying a bare answer and a caller has to read `verdict`
 * to know whether `candidates[0]` means anything. A list row is read at a
 * glance and out of context, which is exactly the condition under which a
 * species name becomes an answer.
 *
 * Refusals are logged like everything else. A history that quietly kept only
 * the confident identifications would misrepresent the app to its own user,
 * and the refusals are the product.
 *
 * ## Confidence does not keep
 *
 * A number recorded before calibration was fitted is not a probability, and
 * saying so once at the time is not enough -- the entry outlives the sentence.
 * Each entry carries the model version and the calibration state it was
 * recorded under, and `caveats` compares them against the app as it stands
 * now. This is rule 4 extended along the time axis.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';

import type { IdentifyResponse, Toxicity, Verdict } from './api';

const STORAGE_KEY = 'observation-log';

/** The shape stored on disk. Anything else is discarded on read. */
const ENTRY_VERSION = 1;

/**
 * Old entries fall off the end.
 *
 * The photographs are referenced, not copied, so what grows is the JSON --
 * but AsyncStorage is a single blob per key and rewriting an unbounded one on
 * every identification is how a fast app becomes a slow one.
 */
export const MAX_ENTRIES = 200;

export interface LoggedCandidate {
  scientificName: string;
  commonName: string | null;
  confidence: number;
  toxicity: Toxicity;
}

export interface Place {
  latitude: number;
  longitude: number;
}

export interface Observation {
  version: number;
  observationId: string;
  recordedAt: number;
  /** URIs, not copies. The OS may evict a camera cache file; see `photoUri`. */
  photos: { top?: string; side?: string; underside?: string };
  place: Place | null;
  /** What was answered on the field-notes form before identifying. */
  fieldNotes: Record<string, string>;
  /** What was answered afterwards, question by question. */
  answers: Record<string, string>;

  verdict: Verdict;
  headline: string;
  detail: string;
  candidates: LoggedCandidate[];
  warnings: string[];
  deadlyInPlay: boolean;
  modelVersion: string;
  calibrated: boolean;
}

// --- Building an entry -------------------------------------------------------

export function fromResult(
  result: IdentifyResponse,
  extras: {
    photos?: { top?: string; side?: string; underside?: string };
    place?: Place | null;
    fieldNotes?: Record<string, string>;
    answers?: Record<string, string>;
    now?: number;
  } = {},
): Observation {
  return {
    version: ENTRY_VERSION,
    observationId: result.observation_id,
    recordedAt: extras.now ?? Date.now(),
    photos: { ...(extras.photos ?? {}) },
    place: extras.place ?? null,
    fieldNotes: { ...(extras.fieldNotes ?? {}) },
    answers: { ...(extras.answers ?? {}) },

    verdict: result.verdict,
    headline: result.headline,
    detail: result.detail,
    candidates: result.candidates.map((candidate) => ({
      scientificName: candidate.scientific_name,
      commonName: candidate.common_names[0] ?? null,
      confidence: candidate.confidence,
      toxicity: candidate.toxicity,
    })),
    // Stored with the entry rather than recomputed. A warning is part of what
    // the user was told, and what they were told does not change later.
    warnings: [...result.warnings],
    deadlyInPlay: result.deadly_in_play,
    modelVersion: result.model_version,
    calibrated: result.calibrated,
  };
}

// --- Reading an entry back ---------------------------------------------------

export type Tone = 'danger' | 'caution' | 'confident';

export interface Summary {
  line: string;
  tone: Tone;
}

/**
 * The one line a history row shows.
 *
 * Only a `species` verdict names a species. Everything else describes what the
 * app declined to do, because a name on a glanceable row is read as the
 * answer whatever sits around it -- including a `dangerous_group`, where the
 * result screen does name both halves of the pair. Naming both is a warning
 * when the refusal is on the screen beside it; in a scrolling list, six weeks
 * on, it is two guesses to choose between.
 */
export function summarise(entry: Observation): Summary {
  const tone: Tone = entry.deadlyInPlay
    ? 'danger'
    : entry.verdict === 'species'
      ? 'confident'
      : 'caution';

  switch (entry.verdict) {
    case 'species': {
      const top = entry.candidates[0];
      return {
        line: top ? `Most likely ${top.scientificName}` : entry.headline,
        tone,
      };
    }
    case 'group':
      return { line: 'Narrowed to a group, not to a species', tone };
    case 'dangerous_group':
      return { line: 'Refused — a species that can kill was in play', tone };
    case 'out_of_scope':
      return { line: 'Not recognised as anything I know', tone };
    case 'uncertain':
    default: {
      const n = entry.candidates.length;
      return {
        line: n ? `Not identified — ${n} possibilit${n === 1 ? 'y' : 'ies'}` : 'Not identified',
        tone,
      };
    }
  }
}

/**
 * What this entry can no longer be read as, given the app as it stands now.
 *
 * Returned as a list rather than a single worst case: "recorded before
 * calibration" and "a different model produced this" are separate facts and
 * neither substitutes for the other.
 *
 * `current` is null when the app could not reach the service. The calibration
 * caveat still applies -- it is a fact about the entry and needs nothing to
 * compare against -- while the drift caveat cannot be asserted or ruled out,
 * so it is left unsaid rather than guessed either way.
 */
export function caveats(
  entry: Observation,
  current: { modelVersion: string; calibrated: boolean } | null,
): string[] {
  const out: string[] = [];
  if (!entry.calibrated) {
    out.push(
      'The confidences here were never calibrated. Read them as an ordering, not as probabilities.',
    );
  }
  if (current && entry.modelVersion !== current.modelVersion) {
    out.push(
      `Recorded by model ${entry.modelVersion}; this app now runs ${current.modelVersion}. ` +
        'The same photograph may not give the same answer.',
    );
  }
  return out;
}

export function recencyLabel(recordedAt: number, now: number = Date.now()): string {
  const days = Math.floor((now - recordedAt) / (24 * 60 * 60 * 1000));
  if (days < 0) return 'Just now';
  if (days === 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 30) return `${days} days ago`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months} month${months === 1 ? '' : 's'} ago`;
  const years = Math.floor(days / 365);
  return `${years} year${years === 1 ? '' : 's'} ago`;
}

/** The first photograph there is, or null. Slots may be empty or evicted. */
export function photoUri(entry: Observation): string | null {
  return entry.photos.top ?? entry.photos.side ?? entry.photos.underside ?? null;
}

// --- The list ----------------------------------------------------------------

/**
 * Fold one entry into the log. Pure, so the ordering and capping rules can be
 * reasoned about without touching storage.
 *
 * Keyed on `observation_id`, and the newer copy wins. Answering a question
 * changes the verdict -- often from a refusal to an identification, or the
 * reverse -- and the log holds where the user got to, not where they started.
 */
export function merge(existing: Observation[], entry: Observation): Observation[] {
  const kept = existing.filter((e) => e.observationId !== entry.observationId);
  return [entry, ...kept]
    .sort((a, b) => b.recordedAt - a.recordedAt)
    .slice(0, MAX_ENTRIES);
}

function isEntry(value: unknown): value is Observation {
  const e = value as Partial<Observation> | null;
  return (
    !!e &&
    typeof e === 'object' &&
    e.version === ENTRY_VERSION &&
    typeof e.observationId === 'string' &&
    e.observationId.length > 0 &&
    typeof e.recordedAt === 'number' &&
    Number.isFinite(e.recordedAt) &&
    typeof e.verdict === 'string' &&
    Array.isArray(e.candidates) &&
    Array.isArray(e.warnings)
  );
}

/**
 * Entries that do not parse are dropped, not repaired.
 *
 * A half-understood record would render as a mushroom the user photographed
 * with some of the qualification missing, which is worse than a record that
 * is not there.
 */
export function parseLog(raw: string | null): Observation[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isEntry).sort((a, b) => b.recordedAt - a.recordedAt);
  } catch {
    return [];
  }
}

// --- Storage -----------------------------------------------------------------
//
// Every accessor swallows its own failure, as the spore print timer's do. A
// log that cannot be written is a lost record; a log that throws on the way
// back from an identification loses the identification too.

export async function readLog(): Promise<Observation[]> {
  try {
    return parseLog(await AsyncStorage.getItem(STORAGE_KEY));
  } catch {
    return [];
  }
}

async function write(entries: Observation[]): Promise<boolean> {
  try {
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
    return true;
  } catch {
    return false;
  }
}

/**
 * Every write is read-modify-write over a single blob, so they are queued.
 *
 * The result screen saves on arrival and again after each answer, and an
 * answer arriving while the previous save is still in flight would have the
 * second read miss the first write. The entries involved carry the same
 * observation id, so the loss would usually be invisible -- which is exactly
 * why it is worth ruling out rather than reasoning about.
 */
let queue: Promise<unknown> = Promise.resolve();

function serialised<T>(work: () => Promise<T>): Promise<T> {
  const next = queue.then(work, work);
  // A rejection must not poison the queue for everything behind it.
  queue = next.catch(() => undefined);
  return next;
}

/** Save an entry, replacing any earlier copy of the same observation. */
export async function record(entry: Observation): Promise<boolean> {
  return serialised(async () => write(merge(await readLog(), entry)));
}

export async function forget(observationId: string): Promise<boolean> {
  return serialised(async () => {
    const entries = await readLog();
    return write(entries.filter((e) => e.observationId !== observationId));
  });
}

export async function forgetAll(): Promise<boolean> {
  return serialised(async () => {
    try {
      await AsyncStorage.removeItem(STORAGE_KEY);
      return true;
    } catch {
      return false;
    }
  });
}

/**
 * Strip the locations, keeping the observations.
 *
 * Where someone forages is the most sensitive thing in this file and the part
 * they are most likely to want gone without losing the rest. It is a separate
 * control because "delete my history" and "stop recording where I was" are
 * different requests.
 *
 * Any future sync must coarsen coordinates rather than send these: a patch is
 * findable from one accurate fix.
 */
export async function forgetPlaces(): Promise<boolean> {
  return serialised(async () => {
    const entries = await readLog();
    return write(entries.map((e) => (e.place ? { ...e, place: null } : e)));
  });
}
