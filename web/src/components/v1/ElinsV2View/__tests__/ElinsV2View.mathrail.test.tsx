/**
 * The Math rail — the strip below the attractor row that says which numbers
 * are measured, which are waiting, and what a flat reading means.
 *
 * ★ WHAT THESE PIN. Before this rail, 25/25/25/25 rendered only as
 * "indeterminate — no attractor leads", and the panel treated the most
 * resilient reading the instrument returns as a non-result. And intensities
 * printed 0.000 where edge_count was 0 — a confident number with no
 * measurement behind it. These pin the rail's four promises: the flat read
 * says "resilient"; an unmeasured primitive says "no edges" and never
 * "0.000"; every waiting quantity is in the DOM with its named blocker; and
 * the timeline's middle sits beside the P-grid's mid band.
 *
 * The existing attractor tests are untouched and must keep passing: the
 * rail is ADDITIVE, and the attractor caption still says what it said.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import ElinsV2View from "../ElinsV2View";

type Layer = { primitive: string; intensity: number; edge_count: number };

function envelope(
  dist: Record<string, number>,
  layers: { pressure?: Layer; drift?: Layer; alignment?: Layer } = {},
  midDays = 2,
) {
  return {
    elins_version: "v2",
    region: null,
    input: { raw_text: "x" },
    pipeline: {
      L1_ingest: {},
      L2_normalize: { normalized: true, note: "" },
      L3_domain: {},
      L4_narrative: {},
      // Real backend shape (elins_v2_view.py:450-461): {primitive, intensity, edge_count}
      L5_pressure:  layers.pressure  ?? { primitive: "pressure",  intensity: 0, edge_count: 0 },
      L6_drift:     layers.drift     ?? { primitive: "drift",     intensity: 0, edge_count: 0 },
      L7_basin: { region: null, available: false },
      L8_temporal: {
        forecast_5day: {},
        forecast_engine: {},
        etf_table: {},
        etf_agg: { survival_1y: 0, survival_10y: 0, survival_50y: 0 },
      },
      L9_alignment: layers.alignment ?? { primitive: "alignment", intensity: 0, edge_count: 0 },
      L10_signature: {},
    },
    outputs: {
      collapse_state: "none",
      attractor: "S1",
      state_distribution: dist,
      P0_P8: {},
      geography_tier: null,
      timeline: { short_term_days: 1, mid_term_days: midDays, long_term_days: 3 },
      multiplier: 1,
    },
    meta: { engine: "clarity_elins_v2", view_kind: "v2" },
  } as never;
}

const flat = { S1: 0.25, S2: 0.25, S3: 0.25, S4: 0.25 };

describe("Math rail — a flat reading is a measurement", () => {
  it("★ 25/25/25/25 renders CI 0.0000 and the word 'resilient' — not an error state", () => {
    render(<ElinsV2View envelope={envelope(flat)} />);
    const row = screen.getByTestId("math-rail-ci");
    expect(row).toHaveAttribute("data-word", "resilient");
    expect(row).toHaveTextContent("0.0000");
    expect(row).toHaveTextContent("resilient");
    expect(row).toHaveTextContent("a measurement, not a non-result");
    // and the rail is not in any error/defect state
    expect(row).not.toHaveAttribute("data-word", "none");
  });

  it("the attractor caption above still says what it said (rail is additive)", () => {
    render(<ElinsV2View envelope={envelope(flat)} />);
    expect(screen.getByTestId("attractor-indeterminate")).toBeInTheDocument();
    expect(screen.getByTestId("math-rail")).toBeInTheDocument();
  });

  it("H is shown against ln n", () => {
    render(<ElinsV2View envelope={envelope(flat)} />);
    const h = screen.getByTestId("math-rail-entropy");
    expect(h).toHaveTextContent("H_max = ln 4");
    expect(h).toHaveTextContent("1.3863");   // ln 4, both H and H_max on a flat read
  });

  it("a concentrated distribution reads 'brittle'", () => {
    render(<ElinsV2View envelope={envelope({ S1: 0.97, S2: 0.01, S3: 0.01, S4: 0.01 })} />);
    expect(screen.getByTestId("math-rail-ci")).toHaveAttribute("data-word", "brittle");
  });
});

describe("Math rail — edge_count beside every intensity", () => {
  it("★ edge_count 0 renders 'no edges' and the row never reads '0.000'", () => {
    render(<ElinsV2View envelope={envelope(flat)} />);
    for (const p of ["pressure", "drift", "alignment"]) {
      const row = screen.getByTestId(`math-rail-${p}`);
      expect(row).toHaveAttribute("data-edges", "0");
      expect(row).toHaveTextContent("no edges");
      expect(row.textContent).not.toContain("0.000");
    }
  });

  it("a measured primitive shows its intensity to 3 dp with its edge count", () => {
    render(<ElinsV2View envelope={envelope(flat, {
      pressure: { primitive: "pressure", intensity: 0.4123, edge_count: 3 },
      drift:    { primitive: "drift",    intensity: 0.05,   edge_count: 1 },
    })} />);
    const pr = screen.getByTestId("math-rail-pressure");
    expect(pr).toHaveTextContent("0.412");
    expect(pr).toHaveTextContent("3 edges");
    const dr = screen.getByTestId("math-rail-drift");
    expect(dr).toHaveTextContent("0.050");
    expect(dr).toHaveTextContent("1 edge");
    // alignment left unmeasured in this fixture
    expect(screen.getByTestId("math-rail-alignment")).toHaveTextContent("no edges");
  });

  it("edges present but intensity unmeasured says so -- never 'no edges', never '0.000'", () => {
    render(<ElinsV2View envelope={envelope(flat, {
      pressure: { primitive: "pressure", intensity: Number.NaN, edge_count: 2 },
    })} />);
    const pr = screen.getByTestId("math-rail-pressure");
    expect(pr).toHaveTextContent("2 edges");
    expect(pr).toHaveTextContent("intensity unavailable");
    expect(pr.textContent).not.toContain("no edges");
    expect(pr.textContent).not.toContain("0.000");
  });

  it("a layer missing intensity/edge_count entirely still renders 'no edges' (never crashes)", () => {
    const env = envelope(flat) as unknown as { pipeline: Record<string, unknown> };
    env.pipeline.L5_pressure = { pressure: 0, drivers: [] };   // the old stub shape
    render(<ElinsV2View envelope={env as never} />);
    expect(screen.getByTestId("math-rail-pressure")).toHaveTextContent("no edges");
  });
});

describe("Math rail — waiting rows are ALWAYS rendered, with their blocker", () => {
  it("★ every waiting quantity is in the DOM with a named blocker", () => {
    render(<ElinsV2View envelope={envelope(flat)} />);
    const w = screen.getByTestId("math-rail-waiting");
    // Full lines, as pairs: fog_of_war and cohesion share a blocker phrase,
    // so asserting the phrase alone could not tell one row from the other.
    expect(w).toHaveTextContent("basin_hop -- awaiting a second read");
    expect(w).toHaveTextContent("fog_of_war -- awaiting PRO-tier ingest");
    expect(w).toHaveTextContent("cohesion -- awaiting PRO-tier ingest");
    expect(w).toHaveTextContent("E/r curvature -- awaiting a region graph");
    expect(w.querySelectorAll("div")).toHaveLength(4);
  });
});

describe("Math rail — the timeline middle beside the P-grid mid band", () => {
  it("mid_term_days renders next to the 'mid' header, not conflated with P1/P4/P7", () => {
    render(<ElinsV2View envelope={envelope(flat, {}, 14)} />);
    const days = screen.getByTestId("pgrid-mid-days");
    expect(days).toHaveTextContent("14d");
    // POSITION, not just presence: its parent is the "mid" header cell.
    expect(days.parentElement).toHaveTextContent("mid · 14d");
  });
});

describe("Math rail — D5: no basis is a different kind", () => {
  it("a single-attractor payload renders the sentinel, never NaN", () => {
    render(<ElinsV2View envelope={envelope({ S1: 1 })} />);
    const row = screen.getByTestId("math-rail-ci");
    expect(row).toHaveAttribute("data-word", "none");
    expect(row.textContent).not.toContain("NaN");
    expect(row).toHaveTextContent("one attractor cannot be spread");
  });
});
