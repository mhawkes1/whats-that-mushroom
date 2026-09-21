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

export type Toxicity = 'DEADLY' | 'SERIOUS' | 'TOXIC' | 'INEDIBLE' | 'UNKNOWN';

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

export interface Health {
  status: string;
  model_loaded: boolean;
  calibrated: boolean;
  n_classes: number;
  model_version: string;
  taxonomy_reviewed: boolean;
  character_states_described: number;
}

/**
 * What the service currently is.
 *
 * The observation log needs this to know whether a confidence it stored
 * months ago is still the same quantity as one stored today, and asking that
 * should not require running an identification.
 */
export async function getHealth(): Promise<Health> {
  const response = await fetch(`${BASE_URL}/health`, {
    headers: { Accept: 'application/json' },
  });
  return handle<Health>(response);
}

export interface Acknowledgement {
  key: string;
  statement: string;
  /** Why this one is here, shown beneath it. Never a reassurance. */
  because: string;
}

export interface Disclaimer {
  /**
   * A hash of the text, derived by the server. Stored with the consent: when
   * the statements change this changes with them and the consent is stale,
   * because agreeing to an older statement is not agreeing to a newer one.
   */
  version: string;
  heading: string;
  body: string;
  acknowledgements: Acknowledgement[];
}

/**
 * What a user acknowledges before first use.
 *
 * Served rather than written into the client, for the reason `/field-form` is
 * served, and because the statements depend on what the service currently is:
 * while there is no trained model, no fitted calibration and no reviewed
 * taxonomy, each of those is something the user is told up front.
 */
export async function getDisclaimer(): Promise<Disclaimer> {
  const response = await fetch(`${BASE_URL}/disclaimer`, {
    headers: { Accept: 'application/json' },
  });
  return handle<Disclaimer>(response);
}

export interface SpeciesListEntry {
  species_key: string;
  scientific_name: string;
  common_names: string[];
}

export async function getSpeciesList(): Promise<SpeciesListEntry[]> {
  const response = await fetch(`${BASE_URL}/species`, {
    headers: { Accept: 'application/json' },
  });
  return (await handle<{ species: SpeciesListEntry[] }>(response)).species;
}

export interface IncidentReport {
  observation_id?: string | null;
  verdict?: string | null;
  reported_candidates?: string[];
  model_version?: string | null;
  calibrated?: boolean | null;
  believed_species_key?: string | null;
  account?: string;
  anyone_ate_it?: boolean;
  anyone_unwell?: boolean;
  contact?: string | null;
}

export interface IncidentReceipt {
  incident_id: string;
  severity: string;
  acknowledgement: string;
  /** True when the report says someone ate it or is unwell. */
  medical_emergency: boolean;
  emergency_guidance: string | null;
}

/**
 * Report a suspected misidentification.
 *
 * Everything about what the app said is sent from the observation log rather
 * than looked up server-side, so a report stays actionable after the server
 * has forgotten the observation, and records the model that actually produced
 * the answer.
 *
 * A receipt with `medical_emergency` is not a confirmation. The client shows
 * the emergency guidance instead -- and checks for itself before submitting,
 * because the network is exactly what fails in a wood.
 */
export async function reportIncident(report: IncidentReport): Promise<IncidentReceipt> {
  const response = await fetch(`${BASE_URL}/incident`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(report),
  });
  return handle<IncidentReceipt>(response);
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
 * There is no "edible" label, and INEDIBLE deliberately reads as an absence
 * of assessment rather than as reassurance. Users read the best-case label as
 * permission, so the best case must not sound like permission.
 */
export const TOXICITY_LABEL: Record<Toxicity, string> = {
  DEADLY: 'Can kill',
  SERIOUS: 'Causes serious illness',
  TOXIC: 'Causes illness',
  INEDIBLE: 'Not assessed as safe',
  UNKNOWN: 'Unassessed',
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

/** A rectangle on the photograph, in fractions of its width and height. */
export interface Region {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface ColourMatch {
  option: string;
  distance: number;
}

export interface SporePrintReading {
  confident: boolean;
  /** Null whenever no match may be asserted. Never guess past this. */
  option: string | null;
  reason: string;
  ranked: ColourMatch[];
  corrected_rgb: number[] | null;
}

/**
 * Match a photographed spore print against the reference chart.
 *
 * The two patches are marked rather than sampled here: reading pixels is
 * awkward on the device, and the server already owns the colour judgement and
 * the answer strings it has to produce.
 *
 * The result is a suggestion. A reading with `confident: false` has no option
 * and must not be submitted; the ranking it carries is for ordering the manual
 * picker, nothing more.
 */
export async function matchSporePrint(
  imageUri: string,
  sample: Region,
  white: Region,
): Promise<SporePrintReading> {
  const form = new FormData();
  appendPhoto(form, 'image', imageUri);
  const asField = (r: Region) => `${r.x},${r.y},${r.width},${r.height}`;
  form.append('sample_region', asField(sample));
  form.append('white_region', asField(white));

  const response = await fetch(`${BASE_URL}/spore-print/match`, {
    method: 'POST',
    body: form,
    headers: { Accept: 'application/json' },
  });
  return handle<SporePrintReading>(response);
}
