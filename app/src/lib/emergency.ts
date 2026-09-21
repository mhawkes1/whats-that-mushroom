/**
 * What to do if someone has eaten one.
 *
 * Hardcoded here, alone among the app's user-facing text, and deliberately.
 * Everything else that a user reads is served -- the field form, the
 * disclaimer -- because one copy cannot drift from another. This is the
 * exception, because the one screen that must never fail is this one, and a
 * wood is exactly where the network is not.
 *
 * It is also reachable before consent. Someone opening the app in a panic is
 * not going to work through an onboarding flow first, and a safety gate that
 * stands between a frightened person and the words "call 999" is not a safety
 * gate.
 */

export interface EmergencyStep {
  heading: string;
  body: string;
}

export const EMERGENCY_HEADLINE = 'If someone has eaten a wild mushroom';

export const EMERGENCY_STEPS: EmergencyStep[] = [
  {
    heading: 'Call now — do not wait for symptoms',
    body:
      'In the UK: 999 if someone is seriously unwell, NHS 111 otherwise. ' +
      'Amatoxin poisoning has a latent period of six to twenty-four hours, and ' +
      'someone who feels fine may already need treatment. Early treatment ' +
      'substantially improves the outcome.',
  },
  {
    heading: 'Take the mushroom with you',
    body:
      'Whatever is left of it, including scraps, peelings and anything in the ' +
      'bin. Keep it dry and in paper rather than plastic. A photograph is a ' +
      'poor substitute for the specimen, and identification by a mycologist ' +
      'changes the treatment.',
  },
  {
    heading: 'Say what was eaten, when, and how much',
    body:
      'The time of the meal matters as much as the species, because the gap ' +
      'between eating and the first symptom is itself diagnostic. Take a note ' +
      'of it before you leave.',
  },
  {
    heading: 'Do not rely on anything this app told you',
    body:
      'Including a reassuring answer. This app cannot assess whether a ' +
      'mushroom is safe to eat and has never claimed to.',
  },
];

/** True of every step: none of this requires a network or an account. */
export const WORKS_OFFLINE = true;
