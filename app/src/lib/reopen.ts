import { identify, answerQuestion, type IdentifyResponse } from './api';
import { photoUri, type Observation } from './observationLog';

/**
 * Open an observation from the history again, so more can be added to it.
 *
 * **Why this needs doing at all.** `/answer` works against a record the
 * server keeps in a plain in-memory dictionary:
 *
 *     observations: dict[str, dict] = {}
 *
 * Nothing persists it and nothing evicts from it. Restart the process and
 * every observation is gone; come back next week and `/answer` returns
 * "Unknown observation. Start again with /identify."
 *
 * That is not only a limit on this feature. The spore print flow asks a
 * user to wait **two to twelve hours** -- the client already assumes the
 * session will not survive that, which is why its timer is a stored
 * timestamp rather than a countdown -- and the server's half of the
 * observation does not survive it either. So the spore print can already
 * be started and then be impossible to submit. This is the repair for
 * that as much as a new feature.
 *
 * **Why the phone re-identifies instead of the server remembering.** The
 * log already holds the photographs, the field notes and every answer, so
 * the device can rebuild the whole observation by sending them again. The
 * alternative is a server that stores people's observations, and this
 * project has turned that down before on privacy grounds -- the incident
 * route deliberately holds no address for the same reason. A second
 * inference run costs a second or two of CPU and nobody's data.
 *
 * **Answers are replayed, not re-sent in a batch**, through the same
 * `/answer` route the live flow uses. Replaying them through the real
 * engine is the only way the reopened ranking is the one the user left;
 * a shortcut that applied them differently would make the history lie
 * about what the app had said.
 */

export class PhotographsGone extends Error {
  constructor() {
    super(
      'The photographs for this observation are no longer on this phone, ' +
        'so it cannot be identified again.',
    );
    this.name = 'PhotographsGone';
  }
}

/** Answers that no longer mean anything and must not be replayed. */
function replayable(entry: Observation): Array<[string, string]> {
  return Object.entries(entry.answers ?? {}).filter(
    ([, answer]) => typeof answer === 'string' && answer.length > 0,
  );
}

export async function reopen(entry: Observation): Promise<IdentifyResponse> {
  // `photoUri` already knows that the OS evicts camera cache files, which
  // is why the history screen can show a record whose picture has gone.
  // Here that is fatal rather than cosmetic, and must say so plainly
  // instead of sending an empty form and reporting a server error.
  const top = photoUri(entry);
  if (!top) throw new PhotographsGone();

  let result = await identify(
    { top, side: entry.photos.side, underside: entry.photos.underside },
    {},
    entry.fieldNotes ?? {},
  );

  for (const [character, answer] of replayable(entry)) {
    try {
      result = await answerQuestion(result.observation_id, character, answer);
    } catch {
      // One answer failing must not lose the rest. The character may have
      // left the catalogue since, or the engine may no longer ask it --
      // in which case the honest outcome is the ranking without it, not a
      // dead end on a record the user can still see.
      continue;
    }
  }

  return result;
}
