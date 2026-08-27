// lib/attractor.ts — the attractor tie-break, in ONE place.
//
// ★★★ A FLAT FIELD IS NOT "STABLE COHERENCE".
//
// The backend picks the attractor by argmax over the four state weights, and
// argmax on a tie silently returns the FIRST bucket — S1. So a perfectly
// balanced field reports as S1: the one state the system exists to produce,
// named precisely when nothing has settled.
//
// Measured live:
//   25/25/25/25 FLAT  -> "S1", while Emotional Physics reported
//                        stability: unstable, gradient: inward
//   21/21/36/21       -> "S3", agreeing with EP's intensity: high
// The engine discriminates correctly whenever there IS a winner. The LABEL
// was the defect.
//
// ★★ EXTRACTED, NOT REIMPLEMENTED. This shipped in cdae4ba to PersonalElins
// and missed ElinsV2View, which kept rendering the raw backend value — so
// CT-1's 2026-08-27 walk saw "attractor: S1 · aligned coherence" printed
// directly beneath 25/25/25/25. Both consumers now import this; writing a
// second copy is how the two would drift apart again.
//
// ★ THE BACKEND STILL RETURNS "S1" ON A LEVEL FIELD. This is a display
// guard only. Any non-UI consumer of /elins/v2/run still gets the wrong
// answer. Named and held — separate backend item.

/** Epsilon in weight units. The real discriminating read had a 15pp gap, so
 *  5pp sits comfortably below a genuine signal while catching exact and
 *  near ties. Chosen from the measurement, not from taste. */
export const ATTRACTOR_TIE_EPSILON = 0.05;

export type AttractorState = "S1" | "S2" | "S3" | "S4";

export type AttractorVerdict =
  | { determinate: true; state: AttractorState; gap: number }
  | { determinate: false; gap: number; leaders: string[] };

/** Decide whether a distribution actually names an attractor.
 *  `fallback` is used only when the distribution is unusable. */
export function attractorVerdict(
  dist: Record<string, number> | null | undefined,
  fallback: AttractorState,
): AttractorVerdict {
  const states: AttractorState[] = ["S1", "S2", "S3", "S4"];
  const pairs = states
    .map((s) => ({ s, w: Number(dist?.[s]) }))
    .filter((p) => Number.isFinite(p.w));
  if (pairs.length < 2) return { determinate: true, state: fallback, gap: 1 };
  pairs.sort((a, b) => b.w - a.w);
  const gap = pairs[0].w - pairs[1].w;
  if (gap < ATTRACTOR_TIE_EPSILON) {
    const leaders = pairs
      .filter((p) => pairs[0].w - p.w < ATTRACTOR_TIE_EPSILON)
      .map((p) => p.s);
    return { determinate: false, gap, leaders };
  }
  return { determinate: true, state: pairs[0].s, gap };
}

/** The copy both surfaces show when no attractor leads. Shared so the two
 *  cannot say different things about the same state. */
export const INDETERMINATE_LABEL = "indeterminate — no attractor leads";

export function indeterminateDetail(leaders: string[]): string {
  return `${leaders.join(" / ")} are within ${Math.round(
    ATTRACTOR_TIE_EPSILON * 100,
  )} points. A level field does not name a state.`;
}
