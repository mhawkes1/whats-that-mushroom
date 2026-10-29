/**
 * Reopening an observation from the history.
 *
 * The server keeps in-progress observations in a plain in-memory dict with
 * no persistence and no eviction, so `/answer` stops working on a restart
 * and on anything older than the process. The phone re-identifies from what
 * it already stored instead -- which also repairs the spore print flow,
 * since that asks a user to wait two to twelve hours and the server's half
 * of the observation never survived that either.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { IdentifyResponse } from '../src/lib/api';
import type { Observation } from '../src/lib/observationLog';
import {
  ObservationGone,
  PhotographsGone,
  answerPastObservation,
  reopen,
} from '../src/lib/reopen';

const identify = vi.fn();
const answerQuestion = vi.fn();
const readLog = vi.fn(async () => [] as Observation[]);

vi.mock('../src/lib/api', () => ({
  identify: (...args: unknown[]) => identify(...args),
  answerQuestion: (...args: unknown[]) => answerQuestion(...args),
}));

vi.mock('../src/lib/observationLog', async (orig) => ({
  ...(await orig<Record<string, unknown>>()),
  readLog: (...args: unknown[]) => readLog(...args),
}));

// Static import: `vi.mock` is hoisted above it by vitest, and a
// top-level await here type-checks only under newer module settings
// than this project uses.

const reply = (id: string): IdentifyResponse =>
  ({ observation_id: id, verdict: 'species', headline: '', detail: '',
     candidates: [], warnings: [], deadly_in_play: false, questions: [],
     how_to_tell_apart: [], model_version: '0.1.0', calibrated: true }) as IdentifyResponse;

const entry = (over: Partial<Observation> = {}): Observation =>
  ({
    version: 1,
    observationId: 'old-1',
    recordedAt: 1_000,
    photos: { top: 'file:///cap.jpg', underside: 'file:///gills.jpg' },
    place: null,
    fieldNotes: { habitat: 'Broadleaf woodland' },
    answers: { ring: 'No ring', volva: 'Clear cup or sac' },
    verdict: 'species',
    headline: '',
    detail: '',
    candidates: [],
    warnings: [],
    deadlyInPlay: false,
    modelVersion: '0.1.0',
    calibrated: true,
    ...over,
  }) as Observation;

beforeEach(() => {
  identify.mockReset();
  answerQuestion.mockReset();
  readLog.mockReset();
});

describe('reopen', () => {
  it('re-identifies from the stored photographs and field notes', () => {
    identify.mockResolvedValue(reply('new-1'));
    answerQuestion.mockImplementation(async () => reply('new-1'));
    return reopen(entry()).then(() => {
      const [views, context, notes] = identify.mock.calls[0];
      expect(views).toEqual({
        top: 'file:///cap.jpg',
        side: undefined,
        underside: 'file:///gills.jpg',
      });
      expect(notes).toEqual({ habitat: 'Broadleaf woodland' });
      expect(context).toEqual({});
    });
  });

  it('replays every answer through the real /answer route', async () => {
    // Not re-sent as a batch and not applied locally. Replaying them
    // through the engine is the only way the reopened ranking is the one
    // the user left; anything else makes the history lie about what the
    // app had said.
    identify.mockResolvedValue(reply('new-1'));
    answerQuestion.mockImplementation(async () => reply('new-1'));
    await reopen(entry());
    expect(answerQuestion.mock.calls.map((c) => [c[1], c[2]])).toEqual([
      ['ring', 'No ring'],
      ['volva', 'Clear cup or sac'],
    ]);
  });

  it('keeps going when one answer no longer applies', async () => {
    // A character may have left the catalogue, or the engine may no longer
    // ask it. The honest outcome is the ranking without that answer, not a
    // dead end on a record the user can still see.
    identify.mockResolvedValue(reply('new-1'));
    answerQuestion
      .mockRejectedValueOnce(new Error('unknown character'))
      .mockResolvedValue(reply('new-1'));
    const result = await reopen(entry());
    expect(result.observation_id).toBe('new-1');
    expect(answerQuestion).toHaveBeenCalledTimes(2);
  });

  it('says plainly when the photographs have been evicted', async () => {
    // The OS clears camera cache files; the history already copes with
    // that for thumbnails. Here it is fatal, and must not surface as a
    // server error from a form that was sent empty.
    await expect(reopen(entry({ photos: {} }))).rejects.toBeInstanceOf(
      PhotographsGone,
    );
    expect(identify).not.toHaveBeenCalled();
  });

  it('does not replay a blank answer', async () => {
    identify.mockResolvedValue(reply('new-1'));
    answerQuestion.mockResolvedValue(reply('new-1'));
    await reopen(entry({ answers: { ring: '', volva: 'Clear cup or sac' } }));
    expect(answerQuestion).toHaveBeenCalledTimes(1);
  });
});

describe('answering an observation the server has forgotten', () => {
  // What makes the spore print deliverable. It asks the user to wait two
  // to twelve hours, so it is almost never started and finished in one
  // session -- and the server's record is a dictionary entry in memory
  // that does not survive a restart, let alone an afternoon.
  const stored: Observation[] = [];

  beforeEach(() => {
    stored.length = 0;
    readLog.mockImplementation(async () => [...stored]);
  });

  it('rebuilds the observation, then applies the answer to it', async () => {
    stored.push(entry());
    identify.mockResolvedValue(reply('live-1'));
    answerQuestion.mockResolvedValue(reply('live-1'));

    const { result } = await answerPastObservation(
      'old-1',
      'spore_print_colour',
      'White or cream',
    );

    expect(identify).toHaveBeenCalledTimes(1);
    // Two replayed answers, then the new one.
    const last = answerQuestion.mock.calls.at(-1);
    expect(last?.[1]).toBe('spore_print_colour');
    expect(last?.[2]).toBe('White or cream');
    expect(result.observation_id).toBe('live-1');
  });

  it('returns the entry with the new answer folded in', async () => {
    stored.push(entry());
    identify.mockResolvedValue(reply('live-1'));
    answerQuestion.mockResolvedValue(reply('live-1'));

    const { entry: updated } = await answerPastObservation(
      'old-1',
      'spore_print_colour',
      'White or cream',
    );
    // Keeps its identity, so it replaces the record rather than becoming
    // a second find of the same mushroom.
    expect(updated.observationId).toBe('old-1');
    expect(updated.recordedAt).toBe(1_000);
    expect(updated.answers.spore_print_colour).toBe('White or cream');
    expect(updated.answers.ring).toBe('No ring');
  });

  it('says so by name when the record has been deleted meanwhile', async () => {
    // Twelve hours is long enough to clear the log.
    await expect(
      answerPastObservation('gone', 'spore_print_colour', 'White or cream'),
    ).rejects.toBeInstanceOf(ObservationGone);
    expect(identify).not.toHaveBeenCalled();
  });
});
