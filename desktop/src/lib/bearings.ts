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

/** #196 (CT-1 2026-09-09) -- the stop mark, read from the ONE backend
 *  vocabulary (stop_vocabulary.py) and never from the raw token. The
 *  class is "normal" | "cut" | "unknown"; ONLY "cut" earns a mark.
 *  "unknown" renders NOTHING -- it is not a cut and not a completion,
 *  and the backend has already logged the word once. Absent class (a
 *  mock, a provider that sends no signal, an older wire) renders
 *  nothing too. The RAW vendor token is what the mark NAMES (R5.3),
 *  so "stopped early: max_tokens" still says which instrument spoke. */
export type StopClass = "normal" | "cut" | "unknown";

export function stopMark(stopReason: unknown, stopClass: unknown): string | null {
  if (stopClass !== "cut") return null;
  if (typeof stopReason !== "string" || !stopReason.trim()) return null;
  return stopReason.trim();
}
