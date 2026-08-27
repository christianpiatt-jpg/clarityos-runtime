/**
 * ★★ THE SECOND CONSUMER OF THE TIE-BREAK.
 *
 * The guard shipped in cdae4ba to PersonalElins and MISSED this view, which
 * kept rendering the raw backend value. CT-1's walk on 2026-08-27 measured
 * the result live:
 *
 *     S1 25 · S2 25 · S3 25 · S4 25      <- perfectly level
 *     attractor: S1 · aligned coherence  <- printed underneath it
 *
 * ★ THE FAILING CASE IS TESTED FIRST AND ASSERTED HARDEST. An indeterminate
 * state that swallows real signal would be worse than the defect it
 * replaces, so the non-flat distribution is pinned before the flat one.
 *
 * ★ The BACKEND still returns "S1" on a level field. This is a display guard
 * only; any non-UI consumer of /elins/v2/run still gets the wrong answer.
 * Named and held — separate backend item.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import ElinsV2View from "../ElinsV2View";

/** Envelope built to the real ElinsV2Envelope shape (lib/elinsV2.ts:104).
 *  ★ The first draft of this fixture was hand-guessed and blew up on
 *  `pipeline.L8_temporal.etf_agg` — the component reads more than the
 *  attractor block. Read the type, do not invent the fixture. */
function envelope(dist: Record<string, number>, attractor: string) {
  return {
    elins_version: "v2",
    region: null,
    input: { raw_text: "x" },
    pipeline: {
      L1_ingest: {},
      L2_normalize: { normalized: true, note: "" },
      L3_domain: {},
      L4_narrative: {},
      L5_pressure: { pressure: 0, drivers: [] },
      L6_drift: { drift: 0 },
      L7_basin: { region: null, available: false },
      L8_temporal: {
        forecast_5day: {},
        forecast_engine: {},
        etf_table: {},
        etf_agg: { survival_1y: 0, survival_10y: 0, survival_50y: 0 },
      },
      L9_alignment: {},
      L10_signature: {},
    },
    outputs: {
      collapse_state: "none",
      attractor,
      state_distribution: dist,
      P0_P8: {},
      geography_tier: null,
      timeline: { short_term_days: 1, mid_term_days: 2, long_term_days: 3 },
      multiplier: 1,
    },
    meta: { engine: "clarity_elins_v2", view_kind: "v2" },
  } as never;
}

const flat = { S1: 0.25, S2: 0.25, S3: 0.25, S4: 0.25 };
const real = { S1: 0.21, S2: 0.21, S3: 0.36, S4: 0.21 };

describe("ElinsV2View — attractor tie-break", () => {
  it("★ a REAL signal is still named — the guard must not swallow it", () => {
    render(<ElinsV2View envelope={envelope(real, "S3")} />);
    expect(screen.getByTestId("attractor-determinate")).toHaveTextContent("S3");
    expect(screen.queryByTestId("attractor-indeterminate")).toBeNull();
  });

  it("a decisive distribution is named from the numbers, not the label", () => {
    render(<ElinsV2View envelope={envelope({ S1: 0.1, S2: 0.1, S3: 0.1, S4: 0.7 }, "S1")} />);
    expect(screen.getByTestId("attractor-determinate")).toHaveTextContent("S4");
  });

  it("★ the measured flat read names NO attractor", () => {
    render(<ElinsV2View envelope={envelope(flat, "S1")} />);
    const el = screen.getByTestId("attractor-indeterminate");
    expect(el).toHaveTextContent("indeterminate — no attractor leads");
    expect(screen.queryByTestId("attractor-determinate")).toBeNull();
  });

  it("★ and never prints S1 on a tie — the exact string CT-1 saw", () => {
    render(<ElinsV2View envelope={envelope(flat, "S1")} />);
    expect(screen.queryByText(/attractor: S1/)).toBeNull();
    expect(screen.queryByText(/aligned coherence/)).toBeNull();
  });

  it("no column is crowned on a tie either", () => {
    const { container } = render(<ElinsV2View envelope={envelope(flat, "S1")} />);
    // aria-current marks "the" attractor column; on a level field there is none.
    expect(container.querySelectorAll('[aria-current="true"]').length).toBe(0);
  });

  it("the winning column IS crowned when there is a winner", () => {
    const { container } = render(<ElinsV2View envelope={envelope(real, "S3")} />);
    expect(container.querySelectorAll('[aria-current="true"]').length).toBe(1);
  });
});
