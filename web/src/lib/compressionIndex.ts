// compressionIndex — CI = 1 − H/H_max over an attractor distribution.
//
// ★ WHY THIS EXISTS. The attractor row renders 25/25/25/25 as "indeterminate
// — no attractor leads" and the panel treats that as a non-result. It is
// the opposite: CI = 0 is MAXIMUM entropy and MINIMUM curvature — the most
// resilient reading the instrument returns. A flat distribution is a
// measurement, not a failure to measure. Ruled 2026-08-27 (ORDER_math_rail).
//
// The closed form is source_docs/floating_geometry_2026-08-04/
// "### Hydronic compression index (CI).txt":
//     p_i = w_i / Σw · H = −Σ p_i ln p_i · H_max = ln n · CI = 1 − H / H_max
//
// ★ n IS THE NUMBER OF ATTRACTORS PRESENT IN THE PAYLOAD — not a hard-coded
// 4, and not the number of NON-ZERO entries. A zero-weight attractor is
// present and zero: it contributes nothing to H but still widens H_max. A
// denominator that shrank when an attractor happened to be empty would make
// two reads different measurements. (Same ruling as the backend CI over the
// eight-category primitive taxonomy.)
//
// ★ D5 — the no-basis cases return a DIFFERENT KIND, never NaN and never a
// number that reads as a real CI: n ≤ 1 (one attractor cannot be "spread")
// and Σw ≤ 0 (p_i undefined). The brief names the first; the second would
// also produce NaN and is guarded for the same reason.

export type CompressionIndex =
  | { kind: "ci"; ci: number; h: number; hMax: number; n: number }
  | { kind: "none"; n: number; reason: "single_attractor" | "no_weight" };

export function compressionIndex(dist: number[]): CompressionIndex {
  const w = (dist ?? []).map((x) => (Number.isFinite(x) && x > 0 ? x : 0));
  const n = w.length;
  if (n <= 1) return { kind: "none", n, reason: "single_attractor" };
  const sum = w.reduce((a, b) => a + b, 0);
  if (sum <= 0) return { kind: "none", n, reason: "no_weight" };

  let h = 0;
  for (const x of w) {
    const p = x / sum;             // normalise by the sum FIRST
    if (p > 0) h -= p * Math.log(p);   // skip p ≤ 0: ln(0) is −∞, and 0·ln0 is a convention, not arithmetic
  }
  const hMax = Math.log(n);
  return { kind: "ci", ci: 1 - h / hMax, h, hMax, n };
}

/** The word beside the number. Boundaries as ruled: < 0.1 resilient,
 *  0.1–0.5 leaning, > 0.5 brittle. */
export function compressionWord(ci: number): "resilient" | "leaning" | "brittle" {
  if (ci < 0.1) return "resilient";
  if (ci <= 0.5) return "leaning";
  return "brittle";
}
