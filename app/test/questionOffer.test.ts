/**
 * Whether the follow-up questions are asked, or merely offered.
 *
 * Martin's observation: a wall of questions between the name and the
 * percentages gets skipped, because the user wants the answer and the
 * questions are in the way. True -- but only where skipping them is a
 * reasonable thing to do, and there are cases where it is not.
 *
 * Source-level, because vitest cannot drive the RN renderer.
 */

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const SRC = resolve(__dirname, '..', 'src');
const read = (p: string) => readFileSync(resolve(SRC, p), 'utf8');

describe('the question offer', () => {
  it('never collapses while a deadly species holds mass', () => {
    // There the questions are not an optional extra: they are the only
    // mechanism that can resolve the ambiguity, and the instinct to skip
    // to the answer is exactly what you do not want when there is no safe
    // answer yet. Same shape as rule 5, which gates the taste question on
    // whether a deadly candidate holds mass.
    const screen = read('screens/ResultScreen.tsx');
    expect(screen).toMatch(/const mustAsk =[^;]*deadly_in_play/s);
  });

  it('never collapses when the app declined to name a species', () => {
    // A refusal is the case where more evidence matters most. Offering
    // the questions as an extra, beside "I'm not sure what this is", gets
    // them skipped by the people they exist for.
    const screen = read('screens/ResultScreen.tsx');
    expect(screen).toMatch(/const mustAsk =[^;]*verdict !== 'species'/s);
  });

  it('does not promise the percentage will go up', () => {
    // A consistent answer never boosts in this engine. Evidence
    // eliminates; the leading species' share moves as a side effect of
    // its rivals being contradicted, and it can FALL -- answering the
    // follow-up on a dangerous pair once moved the destroying angel up
    // from 24% to 26%, because its partner was ruled out and the mass had
    // to go somewhere.
    //
    // A label promising the number will rise would make a fall read as a
    // malfunction, when it is the app learning something.
    const screen = read('screens/ResultScreen.tsx');
    const offer = screen.split('styles.offer}')[1].split('</Pressable>')[0];
    for (const phrase of [
      'increase', 'improve', 'boost', 'raise', 'more confident',
      'better answer', 'higher',
    ]) {
      expect(offer.toLowerCase()).not.toContain(phrase);
    }
  });

  it('says the answer can change, rather than that it will get better', () => {
    const screen = read('screens/ResultScreen.tsx');
    expect(screen).toMatch(/this can change the/i);
    expect(screen).toMatch(/rule things out/i);
  });

  it('still reaches the spore print guide once opened', () => {
    // The one character the app can walk someone through obtaining, the
    // one that takes hours, and the one that most often settles a lethal
    // ambiguity. Collapsing the questions must not strand it.
    const screen = read('screens/ResultScreen.tsx');
    expect(screen).toMatch(/spore_print_colour[\s\S]{0,400}navigate\('SporePrint'/);
  });
});

describe('the spore print, which takes hours', () => {
  it('carries the log id, not a live session id', () => {
    // The server's `observation_id` is an entry in an in-memory dict that
    // does not survive a restart. This screen asks the user to come back
    // in two to twelve hours, so that id was worthless at exactly the
    // moment it was needed -- a print could be started and never finished.
    const result = read('screens/ResultScreen.tsx');
    expect(result).toMatch(
      /navigate\('SporePrint'[\s\S]{0,300}identity\?\.observationId \?\? result\.observation_id/,
    );
    const history = read('screens/HistoryScreen.tsx');
    expect(history).toMatch(
      /navigate\('SporePrint'[\s\S]{0,200}entry\.observationId/,
    );
  });

  it('can be started from a record weeks old', () => {
    const history = read('screens/HistoryScreen.tsx');
    expect(history).toMatch(/Take a spore print/);
  });

  it('clears the timer only after the answer has landed', () => {
    // Clearing first loses a twelve-hour wait to a dropped connection.
    const screen = read('screens/SporePrintScreen.tsx');
    // A fixed window rather than a brace split: the first `  );` in this
    // block closes the answerPastObservation call, not the callback.
    const accept = screen
      .split('const accept = useCallback(')[1]
      .slice(0, 1200);
    expect(accept.indexOf('answerPastObservation')).toBeLessThan(
      accept.indexOf('clearTimer'),
    );
  });

  it('has one path for applying the answer, not a live fast path', () => {
    // Two arrangements for applying an answer would be kept in step by
    // hand, and the one that matters here is the one almost never
    // exercised during development.
    const screen = read('screens/SporePrintScreen.tsx');
    expect(screen).not.toMatch(/onMatched/);
  });
});
