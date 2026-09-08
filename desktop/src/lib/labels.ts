/**
 * #167b -- CT-1's words for the five bearings (the web's lib/labels.ts, the
 * physics rows only). The key rides in a title attribute; the word is what
 * the reader sees.
 */
export interface Label {
  word: string;
  instrument: string;
}
const PHYSICS = "physics \u00b7 model-read";

export const LABELS: Readonly<Record<string, Label>> = {
  relational_primitives: { word: "relational primitives", instrument: PHYSICS },
  trust:                 { word: "trust",     instrument: PHYSICS },
  alignment:             { word: "alignment", instrument: PHYSICS },
  boundary:              { word: "boundary",  instrument: PHYSICS },
  agency:                { word: "agency",    instrument: PHYSICS },
  distance:              { word: "distance",  instrument: PHYSICS },
  // the relational pattern that rides beside the five (the web's word)
  dominant_pattern:      { word: "pattern",   instrument: PHYSICS },
};

/** Unknown keys come back as themselves, never blank. */
export function labelFor(key: string): Label {
  const hit = LABELS[key];
  if (hit) return hit;
  const word = typeof key === "string" && key.trim() ? key : "\u2014";
  return { word, instrument: "" };
}
