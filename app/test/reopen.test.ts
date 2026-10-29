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
import { PhotographsGone, reopen } from '../src/lib/reopen';

const identify = vi.fn();
const answerQuestion = vi.fn();

vi.mock('../src/lib/api', () => ({
  identify: (...args: unknown[]) => identify(...args),
  answerQuestion: (...args: unknown[]) => answerQuestion(...args),
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
