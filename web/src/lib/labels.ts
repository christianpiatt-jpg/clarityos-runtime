/**
 * #162 (e) -- ONE dictionary: internal key -> CT-1's word + the instrument
 * that produced it. Display only. The internal key never changes and rides
 * in a title attribute wherever the word is shown, so a member can always
 * see what the backend calls the thing.
 *
 * An unknown key returns ITSELF as the word, never blank: a panel that
 * meets a key this table has not heard of shows the internal name rather
 * than nothing. The one exception is the empty key, which has no name to
 * show and gets an em dash.
 *
 * Two keys share a word on purpose: the bare "alignment" is the PHYSICS
 * bearing (a model's reading); "L9_alignment" is the ELINS layer. A caller
 * with an ELINS reading must ask for L9_alignment.
 */
export interface Label {
  /** CT-1's word for the member. */
  word: string;
  /** Which instrument produced the reading. "" when unknown. */
  instrument: string;
}

const ELINS = "elins";
const PHYSICS = "physics \u00b7 model-read";   // R5.3: a model read the text; the bearings are its reading
const AZIMUTH = "azimuth";

export const LABELS: Readonly<Record<string, Label>> = {
  // ---- ELINS v2 (deterministic pipeline) ----
  attractor:             { word: "what's pulling",   instrument: ELINS },
  collapse_state:        { word: "holding / giving", instrument: ELINS },
  L5_pressure:           { word: "pressure",         instrument: ELINS },
  L6_drift:              { word: "drift",            instrument: ELINS },
  L9_alignment:          { word: "alignment",        instrument: ELINS },
  // ---- Emotional Physics, layer 3: the five bearings (a model's reading) ----
  relational_primitives: { word: "relational primitives", instrument: PHYSICS },
  trust:                 { word: "trust",     instrument: PHYSICS },
  alignment:             { word: "alignment", instrument: PHYSICS },
  boundary:              { word: "boundary",  instrument: PHYSICS },
  agency:                { word: "agency",    instrument: PHYSICS },
  distance:              { word: "distance",  instrument: PHYSICS },
  // ---- azimuth ----
  pressure_level:        { word: "pressure",  instrument: AZIMUTH },
};

/** The label for an internal key. Unknown keys come back as themselves. */
export function labelFor(key: string): Label {
  const hit = LABELS[key];
  if (hit) return hit;
  const word = typeof key === "string" && key.trim() ? key : "\u2014";
  return { word, instrument: "" };
}

/** Just the word. Never blank. */
export function labelText(key: string): string {
  return labelFor(key).word;
}
