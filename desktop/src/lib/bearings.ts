/**
 * #167b -- the five bearings as rows (the web's lib/bearings.ts). ONE
 * definition of the reading logic. MEASURED at intelligence_kernel.py: a
 * bearing is a flat enum string with an "unclear" member; ABSENT is a MISSING
 * KEY in the layer dict (never null / 0.0). So: missing -> "\u2014" (an em
 * dash, a different kind from a reading), "unclear" -> the word itself, and
 * a boolean -> its word (a false is never blank).
 */
import { labelFor } from "./labels";

export const BEARING_KEYS = ["trust", "alignment", "boundary", "agency", "distance"] as const;
export type BearingKey = (typeof BEARING_KEYS)[number];

export interface BearingRow {
  key: BearingKey;
  /** CT-1's word (labels.ts); the key rides in a title attribute. */
  label: string;
  value: string;
  missing: boolean;
}

export function bearingRows(rp: Record<string, unknown> | null | undefined): BearingRow[] {
  const src = (rp ?? {}) as Record<string, unknown>;
  return BEARING_KEYS.map((key) => {
    const raw = src[key];
    const text = typeof raw === "string" ? raw.trim()
      : typeof raw === "boolean" ? (raw ? "true" : "false")
      : "";
    const missing = text.length === 0;
    return { key, label: labelFor(key).word, value: missing ? "\u2014" : text, missing };
  });
}

/** #167b -- the stop mark. A provider stop signal other than end_turn means
 *  the model was cut off (max_tokens, a refusal, ...). null / absent is a
 *  mock or an unknown stop, not a cut -- no mark. */
export function stopMark(stopReason: unknown): string | null {
  if (typeof stopReason !== "string" || !stopReason.trim()) return null;
  return stopReason === "end_turn" ? null : stopReason;
}
