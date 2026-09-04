/**
 * #162 (a) -- the five bearings as rows. ONE definition of the reading
 * logic; two render sites (the v1 physics view and the personal section)
 * style it their own way.
 *
 * MEASURED at intelligence_kernel.py:1753-1766 / :2029-2039: a bearing is a
 * flat enum string with an "unclear" member; ABSENT is a MISSING KEY in the
 * layer dict (never null / 0.0), and a parse failure leaves the layer {}
 * with _meta.parse_error set. So: missing -> "\u2014" (an em dash, a
 * different kind from a reading), "unclear" -> the word itself.
 */
import { BEARING_KEYS, type BearingKey, type RelationalPrimitives } from "./api";
import { labelFor } from "./labels";

export interface BearingRow {
  key: BearingKey;
  /** CT-1's word (labels.ts); the key rides in a title attribute. */
  label: string;
  value: string;
  missing: boolean;
}

export function bearingRows(rp: RelationalPrimitives | null | undefined): BearingRow[] {
  const src = (rp ?? {}) as Record<string, unknown>;
  return BEARING_KEYS.map((key) => {
    const raw = src[key];
    const text = typeof raw === "string" ? raw.trim() : "";
    const missing = text.length === 0;
    return { key, label: labelFor(key).word, value: missing ? "\u2014" : text, missing };
  });
}

/** #162 (b) -- the stop mark. A provider stop signal other than end_turn
 *  means the model was cut off (max_tokens, a refusal, ...). null / absent
 *  is a mock or an unknown stop, not a cut -- no mark. */
export function stopMark(stopReason: unknown): string | null {
  if (typeof stopReason !== "string" || !stopReason.trim()) return null;
  return stopReason === "end_turn" ? null : stopReason;
}
