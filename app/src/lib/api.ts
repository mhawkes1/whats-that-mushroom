/**
 * API client.
 *
 * Note the response shape: there is no field carrying a bare answer. A caller
 * must read `verdict` to know whether `candidates[0]` means anything at all.
 * That is deliberate -- it makes the unsafe rendering the awkward one to write.
 */

const BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';

export type Verdict =
  | 'species'
  | 'group'
  | 'uncertain'
  | 'dangerous_group'
  | 'out_of_scope';

export type Toxicity =
  | 'DEADLY'
  | 'SERIOUS'
  | 'TOXIC'
  | 'NONE_RECORDED'
  | 'UNASSESSED';

export interface Candidate {
  species_key: string;
  scientific_name: string;
  common_names: string[];
  confidence: number;
  toxicity: Toxicity;
  genus: string;
}

export interface Question {
  key: string;
  label: string;
  prompt: string;
  how: string;
  effort: 'instant' | 'minutes' | 'hours';
  options: string[];
  requires_photo: boolean;
  safety_note: string;
  rationale: string;
  expected_information_gain: number;
}

export interface IdentifyResponse {
  observation_id: string;
  verdict: Verdict;
  headline: string;
  detail: string;
  candidates: Candidate[];
  warnings: string[];
  deadly_in_play: boolean;
  questions: Question[];
  model_version: string;
  calibrated: boolean;
}

export interface FieldContext {
  month?: number;
  latitude?: number;
  longitude?: number;
}

/** The three views asked for at capture. Only `top` is required. */
export interface Views {
  top: string;
  side?: string;
  underside?: string;
}

/** Character key -> chosen option. Every entry is optional. */
export type FieldNotes = Record<string, string>;

export interface FieldFormField {
  key: string;
  label: string;
  prompt: string;
  how: string;
  options: string[];
  effort: 'instant' | 'minutes' | 'hours';
}

export interface FieldForm {
  fields: FieldFormField[];
  note: string;
}

/**
 * Fetch the capture form.
 *
 * The fields and their options come from the server rather than being written
 * out here. The answer strings are validated against the character catalogue
 * on submission, so a hardcoded copy that drifted would start producing
 * rejected requests -- or, worse, answers the user believes were recorded.
 */
export async function getFieldForm(): Promise<FieldForm> {
  const response = await fetch(`${BASE_URL}/field-form`, {
    headers: { Accept: 'application/json' },
  });
  return handle<FieldForm>(response);
}

async function handle<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(
      `Request failed (${response.status}). ${detail.slice(0, 200)}`.trim(),
    );
  }
  return (await response.json()) as T;
}

function appendPhoto(form: FormData, field: string, uri: string): void {
  form.append(field, {
    uri,
    name: `${field}.jpg`,
    type: 'image/jpeg',
  } as unknown as Blob);
}

export async function identify(
  views: Views,
  context: FieldContext = {},
  notes: FieldNotes = {},
): Promise<IdentifyResponse> {
  const form = new FormData();

  // `image` is the top view. The name is historical -- it was the only
  // photograph the API took -- and is kept so a single-photo client still works.
  appendPhoto(form, 'image', views.top);
  if (views.side) appendPhoto(form, 'side', views.side);
  if (views.underside) appendPhoto(form, 'underside', views.underside);

  if (context.month) form.append('month', String(context.month));
  if (context.latitude !== undefined) {
    form.append('latitude', String(context.latitude));
  }
  if (context.longitude !== undefined) {
    form.append('longitude', String(context.longitude));
  }

  const answered = Object.fromEntries(
    Object.entries(notes).filter(([, value]) => value),
  );
  if (Object.keys(answered).length > 0) {
    form.append('field_notes', JSON.stringify(answered));
  }

  const response = await fetch(`${BASE_URL}/identify`, {
    method: 'POST',
    body: form,
    headers: { Accept: 'application/json' },
  });
  return handle<IdentifyResponse>(response);
}

export async function answerQuestion(
  observationId: string,
  characterKey: string,
  answer: string,
): Promise<IdentifyResponse> {
  const response = await fetch(`${BASE_URL}/answer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({
      observation_id: observationId,
      character_key: characterKey,
      answer,
    }),
  });
  return handle<IdentifyResponse>(response);
}

/**
 * Toxicity labels shown to users.
 *
 * These describe recorded harm and nothing else. There is no "edible" label
 * -- and deliberately no "inedible" one either. Telling a user that a Penny
 * Bun is inedible is a false statement, and a label that is plainly wrong to
 * anyone with field experience destroys their trust in the warnings that
 * matter. The bottom of the scale makes no edibility claim in either
 * direction.
 */
export const TOXICITY_LABEL: Record<Toxicity, string> = {
  DEADLY: 'Can kill',
  SERIOUS: 'Causes serious illness',
  TOXIC: 'Causes illness',
  NONE_RECORDED: 'No toxicity recorded',
  UNASSESSED: 'Not yet assessed',
};

export function verdictColour(
  verdict: Verdict,
  deadlyInPlay: boolean,
  colours: { danger: string; confident: string; caution: string },
): string {
  if (verdict === 'dangerous_group' || deadlyInPlay) return colours.danger;
  if (verdict === 'species') return colours.confident;
  return colours.caution;
}
