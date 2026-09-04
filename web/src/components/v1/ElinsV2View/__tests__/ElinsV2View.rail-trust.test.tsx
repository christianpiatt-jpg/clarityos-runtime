/**
 * #162 (d) -- the basin_hop row of the math rail is bound to a relationship's
 * trust signal when the caller has one; unchanged otherwise.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import ElinsV2View from "../ElinsV2View";

function envelope() {
  const layer = (p: string) => ({ primitive: p, intensity: 0, edge_count: 0 });
  return {
    elins_version: "v2", region: null, input: { raw_text: "x" },
    pipeline: {
      L1_ingest: {}, L2_normalize: { normalized: true, note: "" }, L3_domain: {}, L4_narrative: {},
      L5_pressure: layer("pressure"), L6_drift: layer("drift"),
      L7_basin: { region: null, available: false },
      L8_temporal: { forecast_5day: {}, forecast_engine: {}, etf_table: {},
        etf_agg: { survival_1y: 0, survival_10y: 0, survival_50y: 0 } },
      L9_alignment: layer("alignment"), L10_signature: {},
    },
    outputs: {
      collapse_state: "none", attractor: "S1",
      state_distribution: { S1: 0.25, S2: 0.25, S3: 0.25, S4: 0.25 },
      P0_P8: {}, geography_tier: null,
      timeline: { short_term_days: 1, mid_term_days: 2, long_term_days: 3 }, multiplier: 1,
    },
    meta: { engine: "clarity_elins_v2", view_kind: "v2" },
  } as never;
}

describe("ElinsV2View -- the basin_hop row speaks the trust signal", () => {
  it("no trust -> the sentence, as it always read", () => {
    render(<ElinsV2View envelope={envelope()} />);
    expect(screen.getByTestId("math-rail-basin-hop")).toHaveTextContent("basin_hop -- awaiting a second read");
  });
  it("no_prior_yet -> the sentence; n = 1 -> value, no direction", () => {
    const { unmount } = render(
      <ElinsV2View envelope={envelope()} trust={{ status: "no_prior_yet", scored_turns: 0, theta_floor: 7, theta_ready: false }} />,
    );
    expect(screen.getByTestId("math-rail-basin-hop")).toHaveTextContent("awaiting a second read");
    unmount();
    render(
      <ElinsV2View envelope={envelope()} trust={{ status: "value", value: 1, scored_turns: 1, per_turn: [1], theta_floor: 7, theta_ready: false }} />,
    );
    const row = screen.getByTestId("math-rail-basin-hop");
    expect(row).toHaveTextContent("trust 1");
    expect(row).not.toHaveTextContent(/rising|falling|flat/);
    expect(row).toHaveTextContent("awaiting a second read");   // theta not ready: the sentence stays
  });
  it("the labels: the words from the dictionary, the keys in title attributes", () => {
    render(<ElinsV2View envelope={envelope()} />);
    expect(screen.getByTitle("attractor")).toHaveTextContent("what's pulling");
    expect(screen.getByTitle("collapse_state")).toHaveTextContent("holding / giving");
    expect(screen.getByTitle("L6_drift")).toHaveTextContent("drift");
  });
});
