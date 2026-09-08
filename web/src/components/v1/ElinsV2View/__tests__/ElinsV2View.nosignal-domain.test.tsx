/**
 * #184 -- no_signal with an L3_domain hit: the one line says the domain the
 * run did find ("no reading — but domain: <name> (<score>)"); without a hit
 * the line reads as before; the actions stay either way.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import ElinsV2View from "../ElinsV2View";

function envelope(domain: Record<string, unknown>) {
  const layer = (p: string) => ({ primitive: p, intensity: 0, edge_count: 0 });
  return {
    elins_version: "v2", region: null, input: { raw_text: "x" },
    pipeline: {
      L1_ingest: {}, L2_normalize: { normalized: true, note: "" }, L3_domain: domain, L4_narrative: {},
      L5_pressure: layer("pressure"), L6_drift: layer("drift"),
      L7_basin: { region: null, available: false },
      L8_temporal: { forecast_5day: {}, forecast_engine: {}, etf_table: {}, etf_agg: { n_365: 0, n_3650: 0, n_18250: 0 } },
      L9_alignment: layer("alignment"), L10_signature: { summary: { no_signal: true } },
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

describe("ElinsV2View -- no signal, but a domain (#184)", () => {
  it("★ a domain hit names the domain and its score on the one line", () => {
    render(<ElinsV2View envelope={envelope({ top: "housing", effective_top: "housing", scores: { housing: 0.61, work: 0.2 } })} onRun={() => {}} />);
    expect(screen.getByTestId("elins-no-signal")).toHaveTextContent("no reading — but domain: housing (0.61)");
    expect(screen.queryByTestId("domain-row")).toBeNull();   // no other reading renders
  });
  it("a hit without a score reads a dash for the score", () => {
    render(<ElinsV2View envelope={envelope({ top: "housing", scores: {} })} />);
    expect(screen.getByTestId("elins-no-signal")).toHaveTextContent("no reading — but domain: housing (—)");
  });
  it("no domain -> the line as before, the instrument named", () => {
    render(<ElinsV2View envelope={envelope({})} />);
    expect(screen.getByTestId("elins-no-signal")).toHaveTextContent(/^no signal — /);
  });
});
