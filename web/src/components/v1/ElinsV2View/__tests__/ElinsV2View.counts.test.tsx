/**
 * #303 A3 · #305 · #306 · #307 E2 -- count what counts, on the ELINS rail.
 *
 * ring     "engine: … · ring: event" when the wire carries it.
 * hits     a stress intensity reads "k of 5 hits" (k = round(i / 0.075)) on
 *          the signature and the stress rows; the relief row keeps its number.
 * forecast renders only at n_points >= 2; below it "one point — no trend".
 * stress   envelopes / P0-P8 / multiplier captioned "derived from stress only"
 *          while edges == 0, and not otherwise.
 * S-card   the four columns render only at n >= 2; below it the sentence.
 * lists    an envelope that is not a list of numbers reads a dash, never "[n]".
 */
import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import ElinsV2View from "../ElinsV2View";
import { NEEDS_PRIOR_READ, ONE_POINT_NO_TREND, DERIVED_FROM_STRESS_ONLY } from "../../../../lib/counts";

function envelope(nPoints: number | null, edges: number, ring: string | null = "event") {
  const meta: Record<string, unknown> = {};
  if (nPoints !== null) meta.n_points = nPoints;
  if (ring) meta.ring = ring;
  return {
    elins_version: "v2", region: null, input: { raw_text: "x" },
    pipeline: {
      L1_ingest: {}, L2_normalize: {}, L3_domain: {},
      L4_narrative: { edge_count: edges, threshold: 0.05 },
      L5_pressure: { primitive: "pressure", intensity: 0.15, edge_count: 2 },
      L6_drift: { primitive: "drift", intensity: 0, edge_count: 0 },
      L7_basin: { region: null, available: false },
      L8_temporal: {
        forecast_5day: {
          days: [{ day: 1, phase: "balanced", projected_net: 0.1 }, { day: 5, phase: "easing", projected_net: 0.2 }],
          starting_net: 0.1, ending_net: 0.2, trend: "rising",
        },
        forecast_engine: { days: 5, chain: ["a", "b"] },
        etf_table: {}, etf_agg: {},
      },
      L9_alignment: { primitive: "alignment", intensity: 0.3, edge_count: 1 },
      L10_signature: { summary: { stress_score: 0.15, relief_score: 0.3, no_signal: false }, version: "elins.v34.1" },
    },
    outputs: {
      collapse_state: "none", attractor: "S3",
      state_distribution: { S1: 0.21, S2: 0.21, S3: 0.36, S4: 0.22 },
      P0_P8: { P0: 0.1 }, geography_tier: null,
      timeline: { short_term_days: 365, mid_term_days: 3650, long_term_days: 18250 }, multiplier: 1.2,
    },
    meta: { engine: "clarity_elins_v2", view_kind: "v2" },
    _meta: meta,
  } as never;
}

describe("#303 A3 -- the ring", () => {
  it("rides beside the engine line when the wire carries it, and not otherwise", () => {
    render(<ElinsV2View envelope={envelope(2, 3)} />);
    expect(screen.getByText("engine: clarity_elins_v2 · ring: event")).toBeInTheDocument();
  });
  it("absent: the engine line alone", () => {
    render(<ElinsV2View envelope={envelope(2, 3, null)} />);
    expect(screen.getByText("engine: clarity_elins_v2")).toBeInTheDocument();
  });
});

describe("#305 -- hits, not percents, not bare numbers", () => {
  it("the stress rows read 'k of 5 hits'; the signature's four-primitive sum and the relief row keep their numbers", () => {
    render(<ElinsV2View envelope={envelope(2, 3)} />);
    expect(screen.getByTestId("sig-stress_score")).toHaveTextContent("stress 0.150");
    expect(screen.getByTestId("math-rail-pressure")).toHaveTextContent("2 of 5 hits");
    expect(screen.getByTestId("math-rail-pressure")).toHaveTextContent("2 edges");
    expect(screen.getByTestId("math-rail-alignment")).toHaveTextContent("0.300");
    expect(screen.getByTestId("math-rail-alignment").textContent).not.toMatch(/hits/);
  });
});

describe("#305 -- the forecast needs two points", () => {
  it("★ n = 1: 'one point — no trend', nothing of the curve drawn; the envelopes fold stays", () => {
    render(<ElinsV2View envelope={envelope(1, 3)} />);
    expect(screen.getByTestId("forecast-one-point")).toHaveTextContent(ONE_POINT_NO_TREND);
    expect(screen.queryByTestId("forecast-spark")).toBeNull();
    expect(screen.queryByTestId("forecast-nets")).toBeNull();
    expect(screen.queryByTestId("forecast-phases")).toBeNull();
    expect(screen.getByTestId("forecast-envelopes")).toBeInTheDocument();
  });
  it("n = 2: the curve, start → end · trend", () => {
    render(<ElinsV2View envelope={envelope(2, 3)} />);
    expect(screen.queryByTestId("forecast-one-point")).toBeNull();
    expect(screen.getByTestId("forecast-spark")).toBeInTheDocument();
    expect(screen.getByTestId("forecast-nets")).toHaveTextContent("trend rising");
  });
  it("no n on the wire is one point", () => {
    render(<ElinsV2View envelope={envelope(null, 3)} />);
    expect(screen.getByTestId("forecast-one-point")).toBeInTheDocument();
  });
});

describe("#305 -- derived from stress only while edges == 0", () => {
  it("★ edges 0: the envelopes, the P-grid and the multiplier say so", () => {
    render(<ElinsV2View envelope={envelope(2, 0)} />);
    expect(screen.getByTestId("env-stress-only")).toHaveTextContent(DERIVED_FROM_STRESS_ONLY);
    expect(screen.getByTestId("pgrid-stress-only")).toHaveTextContent(DERIVED_FROM_STRESS_ONLY);
    expect(screen.getByTestId("multiplier-stress-only")).toHaveTextContent(DERIVED_FROM_STRESS_ONLY);
  });
  it("edges 3: no caption", () => {
    render(<ElinsV2View envelope={envelope(2, 3)} />);
    expect(screen.queryByTestId("env-stress-only")).toBeNull();
    expect(screen.queryByTestId("pgrid-stress-only")).toBeNull();
    expect(screen.queryByTestId("multiplier-stress-only")).toBeNull();
  });
});

describe("#307 E2 -- the S-card", () => {
  it("★ n = 1: the sentence, no columns; the verdict caption stays", () => {
    render(<ElinsV2View envelope={envelope(1, 3)} />);
    expect(screen.getByTestId("attractor-needs-prior")).toHaveTextContent(NEEDS_PRIOR_READ);
    expect(screen.queryByTestId("state-share-S1")).toBeNull();
    expect(screen.getByTestId("attractor-determinate")).toHaveTextContent("S3");
  });
  it("n = 2: the four columns", () => {
    render(<ElinsV2View envelope={envelope(2, 3)} />);
    expect(screen.queryByTestId("attractor-needs-prior")).toBeNull();
    expect(screen.getByTestId("state-share-S3")).toHaveTextContent("36");
  });
});

describe("#306 -- a list that is not numbers is a dash", () => {
  it("chain: ['a','b'] reads '—', never '[2]'", () => {
    render(<ElinsV2View envelope={envelope(2, 3)} />);
    const fold = screen.getByTestId("forecast-envelopes");
    expect(within(fold).getByTestId("env-chain")).toHaveTextContent("—");
    expect(within(fold).getByTestId("env-chain").textContent).not.toMatch(/\[2\]/);
  });
});
