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
 * with an ELINS reading must ask for L9_alignment. The same holds for the
 * bare "intensity" (#180a: a physics sub-key, "how strong"); the ELINS
 * intensities ride under L5_pressure / L6_drift / L9_alignment.
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
// #180a -- the ELINS rail's instruments. The two versioned ones are the
// DICTIONARY'S fallback: the panel reads the version off the wire
// (pipeline.L10_signature.version, forecast_engine.version) when it is
// there, so a backend bump shows before this file is touched.
const ELINS_LEXICON  = "elins-lexicon";
const ELINS_V341     = "elins v34.1";
const ELINS_FORECAST = "elins forecast v34.1";
const ELINS_OUTPUTS  = "elins v2 \u00b7 outputs";
const ELINS_SNAPSHOT = "elins v38 snapshot";

export const LABELS: Readonly<Record<string, Label>> = {
  // ---- ELINS v2 (deterministic pipeline) ----
  attractor:             { word: "what's pulling",   instrument: ELINS },
  collapse_state:        { word: "holding / giving", instrument: ELINS },
  L5_pressure:           { word: "pressure",         instrument: ELINS },
  L6_drift:              { word: "drift",            instrument: ELINS },
  L9_alignment:          { word: "alignment",        instrument: ELINS },
  // ---- ELINS v2, the rail's captions (#180a) ----
  L3_domain:             { word: "domain",    instrument: ELINS_LEXICON },
  L10_signature:         { word: "signature", instrument: ELINS_V341 },
  etf_table:             { word: "survival",  instrument: ELINS_FORECAST },
  forecast_5day:         { word: "forecast",  instrument: ELINS_FORECAST },
  forecast_engine:       { word: "envelopes", instrument: ELINS_FORECAST },
  P0_P8:                 { word: "P0\u2013P8 \u00b7 resolution \u00d7 timescale", instrument: ELINS_OUTPUTS },
  geography_tier:        { word: "geography tier", instrument: ELINS_OUTPUTS },
  multiplier:            { word: "multiplier",     instrument: ELINS_OUTPUTS },
  provenance:            { word: "provenance",     instrument: "elins v2" },
  // ---- ELINS v38 dashboard snapshot (#180a i) ----
  ep_mean:               { word: "EP mean",          instrument: ELINS_SNAPSHOT },
  top_primitive:         { word: "Top primitive",    instrument: ELINS_SNAPSHOT },
  forecast_horizon:      { word: "Forecast horizon", instrument: ELINS_SNAPSHOT },
  // ---- Emotional Physics, layer 3: the five bearings (a model's reading) ----
  relational_primitives: { word: "relational primitives", instrument: PHYSICS },
  trust:                 { word: "trust",     instrument: PHYSICS },
  alignment:             { word: "alignment", instrument: PHYSICS },
  boundary:              { word: "boundary",  instrument: PHYSICS },
  agency:                { word: "agency",    instrument: PHYSICS },
  distance:              { word: "distance",  instrument: PHYSICS },
  // ---- Emotional Physics, the four layer captions (#180a j) ----
  field_curvature:       { word: "Field curvature",     instrument: PHYSICS },
  edge_pressure:         { word: "Edge pressure",       instrument: PHYSICS },
  external_expression:   { word: "External expression", instrument: PHYSICS },
  // ---- Emotional Physics, the layer sub-keys (#180a j): CT-1's words ----
  signal_clarity:        { word: "how clear",         instrument: PHYSICS },
  signal_intensity:      { word: "how loud",          instrument: PHYSICS },
  coherence:             { word: "holding together",  instrument: PHYSICS },
  perceived_posture:     { word: "leaning",           instrument: PHYSICS },
  risk_of_misread:       { word: "chance of misread", instrument: PHYSICS },
  intensity:             { word: "how strong",        instrument: PHYSICS },
  gradient_direction:    { word: "which way",         instrument: PHYSICS },
  stability:             { word: "steady",            instrument: PHYSICS },
  dominant_forces:       { word: "what's pushing",    instrument: PHYSICS },
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
