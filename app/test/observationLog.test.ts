/**
 * The observation log.
 *
 * What is worth pinning here is not that a record round-trips. It is that a
 * record read weeks later still carries the things that made it honest when
 * it was written: the verdict rather than a name, the warnings, and the
 * calibration state the confidences were produced under.
 */

import { beforeEach, describe, expect, it } from 'vitest';

import type { IdentifyResponse, Verdict } from '../src/lib/api';
import {
  MAX_ENTRIES,
  caveats,
  forget,
  forgetAll,
  forgetPlaces,
  fromResult,
  merge,
  parseLog,
  photoUri,
  readLog,
  recencyLabel,
  record,
  summarise,
  type Observation,
} from '../src/lib/observationLog';
import { control } from './asyncStorageDouble';

beforeEach(() => control.reset());

const DAY = 24 * 60 * 60 * 1000;

function response(over: Partial<IdentifyResponse> = {}): IdentifyResponse {
  return {
    observation_id: 'obs-1',
    verdict: 'species',
    headline: 'Most likely Amanita rubescens',
    detail: 'Flesh reddens where damaged.',
    candidates: [
      {
        species_key: 'amanita-rubescens',
        scientific_name: 'Amanita rubescens',
        common_names: ['The Blusher'],
        confidence: 0.82,
        toxicity: 'TOXIC',
        genus: 'Amanita',
      },
    ],
    warnings: ['Never eat a wild mushroom identified only by an app.'],
    deadly_in_play: false,
    questions: [],
    model_version: 'stub-0',
    calibrated: true,
    ...over,
  };
}

function entry(over: Partial<Observation> = {}): Observation {
  return { ...fromResult(response(), { now: 1_000_000 }), ...over };
}

// --- What a row is allowed to say --------------------------------------------

describe('what a history row says', () => {
  it('names a species only when the app named one', () => {
    // The row is read at a glance, weeks later, with none of the screen that
    // originally surrounded it. A name there is read as the answer.
    const verdicts: Verdict[] = ['group', 'uncertain', 'dangerous_group', 'out_of_scope'];
    for (const verdict of verdicts) {
      const summary = summarise(entry({ verdict }));
      expect(summary.line, verdict).not.toContain('Amanita');
      expect(summary.line, verdict).not.toContain('rubescens');
      expect(summary.line, verdict).not.toContain('Blusher');
    }
    expect(summarise(entry({ verdict: 'species' })).line).toBe(
      'Most likely Amanita rubescens',
    );
  });

  it('names neither half of a lethal pair, though the result screen names both', () => {
    // Naming both is a warning while the refusal is on the screen beside it.
    // In a scrolling list it is two guesses to choose between.
    const pair = fromResult(
      response({
        verdict: 'dangerous_group',
        deadly_in_play: true,
        candidates: [
          {
            species_key: 'amanita-phalloides',
            scientific_name: 'Amanita phalloides',
            common_names: ['Death Cap'],
            confidence: 0.44,
            toxicity: 'DEADLY',
            genus: 'Amanita',
          },
          {
            species_key: 'agaricus-campestris',
            scientific_name: 'Agaricus campestris',
            common_names: ['Field Mushroom'],
            confidence: 0.41,
            toxicity: 'NO_RECORDED_TOXICITY',
            genus: 'Agaricus',
          },
        ],
      }),
    );
    const summary = summarise(pair);
    expect(summary.line).not.toMatch(/Amanita|Agaricus|Death Cap|Field Mushroom/);
    expect(summary.tone).toBe('danger');
    // The names are still in the record, for the expanded view.
    expect(pair.candidates.map((c) => c.scientificName)).toEqual([
      'Amanita phalloides',
      'Agaricus campestris',
    ]);
  });

  it('marks a deadly candidate as danger even under a confident verdict', () => {
    // Rule 2 of the safety layer, carried into the log: the warning is shown
    // regardless of how confident the model is about something else.
    expect(summarise(entry({ verdict: 'species', deadlyInPlay: true })).tone).toBe('danger');
  });

  it('stores the taxonomy key beside the name', () => {
    // An incident report is graded by looking these up server-side, and a
    // scientific name is not a key. With names in place of keys, a report
    // disputing a warning grades as a warning that never happened -- the
    // opposite classification.
    const stored = fromResult(response());
    expect(stored.candidates[0].speciesKey).toBe('amanita-rubescens');
    expect(stored.candidates[0].scientificName).toBe('Amanita rubescens');
  });

  it('never reduces to a bare name field', () => {
    // The API shape has no field carrying an answer without its verdict, and
    // neither does a stored entry. Anything reading one must go through
    // `summarise`, which cannot be called without the verdict.
    const stored = entry();
    expect(Object.keys(stored)).not.toContain('identifiedAs');
    expect(Object.keys(stored)).not.toContain('species');
    expect(stored.verdict).toBeDefined();
  });
});

// --- Confidence does not keep ------------------------------------------------

describe('caveats', () => {
  const current = { modelVersion: 'v2', calibrated: true };

  it('says so forever when the confidences were never calibrated', () => {
    // Rule 4 along the time axis. Saying it once at the time is not enough:
    // the entry outlives the sentence.
    const said = caveats(entry({ calibrated: false, modelVersion: 'v2' }), current);
    expect(said).toHaveLength(1);
    expect(said[0]).toMatch(/never calibrated/);
  });

  it('says so when a different model produced the numbers', () => {
    const said = caveats(entry({ calibrated: true, modelVersion: 'v1' }), current);
    expect(said).toHaveLength(1);
    expect(said[0]).toMatch(/v1.*v2/);
  });

  it('reports both rather than picking a worst case', () => {
    expect(caveats(entry({ calibrated: false, modelVersion: 'v1' }), current)).toHaveLength(2);
  });

  it('is silent when the entry still stands', () => {
    expect(caveats(entry({ calibrated: true, modelVersion: 'v2' }), current)).toEqual([]);
  });

  it('still says what it knows when the service cannot be reached', () => {
    // Whether the entry was calibrated is a fact about the entry. Whether the
    // model has moved on is a comparison, and an unreachable service is not
    // evidence either way -- so that one is left unsaid rather than guessed.
    expect(caveats(entry({ calibrated: false, modelVersion: 'v1' }), null)).toEqual([
      expect.stringMatching(/never calibrated/),
    ]);
    expect(caveats(entry({ calibrated: true, modelVersion: 'v1' }), null)).toEqual([]);
  });
});

// --- What is kept ------------------------------------------------------------

describe('what an entry keeps', () => {
  it('keeps the warnings it was shown with', () => {
    // A warning is part of what the user was told, and what they were told
    // does not change later. Recomputing it from today's rules would rewrite
    // history; storing it cannot.
    const stored = fromResult(
      response({ warnings: ['One or more candidates can kill.', 'Never eat.'] }),
    );
    expect(stored.warnings).toEqual(['One or more candidates can kill.', 'Never eat.']);
  });

  it('keeps refusals, not only identifications', () => {
    // A log holding only the confident answers would misrepresent the app to
    // its own user, and the refusals are the product.
    for (const verdict of ['dangerous_group', 'out_of_scope', 'uncertain'] as Verdict[]) {
      expect(fromResult(response({ verdict })).verdict).toBe(verdict);
    }
  });

  it('copies the photographs and notes rather than aliasing the caller', () => {
    const photos = { top: 'file://a.jpg' };
    const notes = { volva: 'Neither' };
    const stored = fromResult(response(), { photos, fieldNotes: notes });
    photos.top = 'file://mutated.jpg';
    notes.volva = 'Clear cup or sac';
    expect(stored.photos.top).toBe('file://a.jpg');
    expect(stored.fieldNotes.volva).toBe('Neither');
  });

  it('records no place unless one was given', () => {
    expect(fromResult(response()).place).toBeNull();
  });
});

// --- The list ----------------------------------------------------------------

describe('merge', () => {
  it('replaces an observation in place rather than appending a second copy', async () => {
    // Answering a question changes the verdict, often from a refusal to an
    // identification. The log holds where the user got to.
    await record(entry({ verdict: 'dangerous_group', recordedAt: 1 }));
    await record(entry({ verdict: 'species', recordedAt: 2 }));

    const log = await readLog();
    expect(log).toHaveLength(1);
    expect(log[0].verdict).toBe('species');
  });

  it('keeps the newest and drops the oldest past the cap', () => {
    let log: Observation[] = [];
    for (let i = 0; i < MAX_ENTRIES + 25; i += 1) {
      log = merge(log, entry({ observationId: `obs-${i}`, recordedAt: i }));
    }
    expect(log).toHaveLength(MAX_ENTRIES);
    expect(log[0].observationId).toBe(`obs-${MAX_ENTRIES + 24}`);
    expect(log.some((e) => e.observationId === 'obs-0')).toBe(false);
  });

  it('orders newest first whatever order entries arrive in', () => {
    const log = [
      entry({ observationId: 'a', recordedAt: 100 }),
      entry({ observationId: 'b', recordedAt: 300 }),
    ].reduce(merge, [] as Observation[]);
    expect(merge(log, entry({ observationId: 'c', recordedAt: 200 })).map((e) => e.recordedAt))
      .toEqual([300, 200, 100]);
  });
});

// --- Reading back what is on disk --------------------------------------------

describe('reading the stored log', () => {
  it('drops an entry it cannot fully understand rather than repairing it', async () => {
    // A half-understood record renders as a mushroom the user photographed
    // with some of the qualification missing, which is worse than no record.
    control.seed(
      'observation-log',
      JSON.stringify([
        entry({ observationId: 'good' }),
        { observationId: 'no-version', recordedAt: 5, verdict: 'species' },
        { version: 99, observationId: 'from-the-future', recordedAt: 6 },
        null,
        'not an entry at all',
      ]),
    );
    const log = await readLog();
    expect(log.map((e) => e.observationId)).toEqual(['good']);
  });

  it('comes back empty rather than throwing on rubbish', () => {
    for (const raw of [null, '', 'not json', '{"not":"an array"}', '[']) {
      expect(parseLog(raw)).toEqual([]);
    }
  });

  it('comes back empty rather than throwing when storage is unavailable', async () => {
    // Losing the history is a nuisance. Throwing on the way back from an
    // identification would lose the identification too.
    control.failReads = true;
    await expect(readLog()).resolves.toEqual([]);
  });

  it('reports a failed write instead of pretending it saved', async () => {
    control.failWrites = true;
    await expect(record(entry())).resolves.toBe(false);
  });
});

// --- Forgetting --------------------------------------------------------------

describe('forgetting', () => {
  it('removes one observation and leaves the rest', async () => {
    await record(entry({ observationId: 'a', recordedAt: 1 }));
    await record(entry({ observationId: 'b', recordedAt: 2 }));
    await forget('a');
    expect((await readLog()).map((e) => e.observationId)).toEqual(['b']);
  });

  it('removes everything', async () => {
    await record(entry());
    await forgetAll();
    expect(await readLog()).toEqual([]);
  });

  it('strips locations without losing the observations', async () => {
    // Where someone forages is the most sensitive thing stored here and the
    // part they are most likely to want gone without losing the rest.
    await record(entry({ observationId: 'a', place: { latitude: 51.5, longitude: -0.1 } }));
    await record(entry({ observationId: 'b', place: { latitude: 53.4, longitude: -2.2 } }));
    await forgetPlaces();

    const log = await readLog();
    expect(log).toHaveLength(2);
    expect(log.every((e) => e.place === null)).toBe(true);
    expect(control.raw('observation-log')).not.toContain('51.5');
    expect(control.raw('observation-log')).not.toContain('-2.2');
  });
});

// --- Presentation ------------------------------------------------------------

describe('recencyLabel', () => {
  const now = 1_700_000_000_000;

  it('reads the way someone would say it', () => {
    expect(recencyLabel(now, now)).toBe('Today');
    expect(recencyLabel(now - DAY, now)).toBe('Yesterday');
    expect(recencyLabel(now - 5 * DAY, now)).toBe('5 days ago');
    expect(recencyLabel(now - 40 * DAY, now)).toBe('1 month ago');
    expect(recencyLabel(now - 200 * DAY, now)).toBe('6 months ago');
    expect(recencyLabel(now - 400 * DAY, now)).toBe('1 year ago');
  });

  it('does not report a negative age when the device clock moves', () => {
    expect(recencyLabel(now + DAY, now)).toBe('Just now');
  });
});

describe('photoUri', () => {
  it('falls back through the slots and admits when there is nothing', () => {
    expect(photoUri(entry({ photos: { top: 'a', side: 'b' } }))).toBe('a');
    expect(photoUri(entry({ photos: { underside: 'c' } }))).toBe('c');
    // The OS evicts camera cache files; a row must survive its photo going.
    expect(photoUri(entry({ photos: {} }))).toBeNull();
  });
});

describe('concurrent writes', () => {
  it('does not lose an entry when saves overlap', async () => {
    // Every write is read-modify-write over a single blob. The result screen
    // saves on arrival and again after each answer, so overlapping saves are
    // ordinary rather than exotic.
    await Promise.all(
      Array.from({ length: 20 }, (_, i) =>
        record(entry({ observationId: `obs-${i}`, recordedAt: i })),
      ),
    );
    expect(await readLog()).toHaveLength(20);
  });

  it('keeps the last write when the same observation is saved twice at once', async () => {
    await Promise.all([
      record(entry({ verdict: 'dangerous_group', recordedAt: 1 })),
      record(entry({ verdict: 'species', recordedAt: 2 })),
    ]);
    const log = await readLog();
    expect(log).toHaveLength(1);
    expect(log[0].verdict).toBe('species');
  });

  it('carries on after a write that failed', async () => {
    control.failWrites = true;
    await expect(record(entry({ observationId: 'lost' }))).resolves.toBe(false);
    control.failWrites = false;
    await expect(record(entry({ observationId: 'kept' }))).resolves.toBe(true);
    expect((await readLog()).map((e) => e.observationId)).toEqual(['kept']);
  });
});
