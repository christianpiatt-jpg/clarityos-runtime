/**
 * #330 leg 1 — the one row this leg adds to the S-card.
 *
 * The record already sealed an expectation and observed the previous one;
 * what it never sealed was what the INSTRUMENT concluded. Now it does, and
 * the card says whether this run met the state the previous turn sealed.
 *
 * ★ THE ABSENT CASE IS TESTED FIRST. "No prior seal" is a different KIND of
 * answer from "missed" (D5): a first turn has nothing to be right or wrong
 * about, and rendering that as a 0, a blank, or a miss is the failure this
 * row exists to avoid.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import ElinsV2View from "../ElinsV2View";

/** The real ElinsV2Envelope shape (lib/elinsV2.ts:104) — read, not invented. */
function envelope(meta: Record<string, unknown>) {
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
        etf_agg: { n_365: 0, n_3650: 0, n_18250: 0 },
      },
      L9_alignment: {},
      L10_signature: {},
    },
    outputs: {
      collapse_state: "none",
      attractor: "S3",
      state_distribution: { S1: 0.21, S2: 0.21, S3: 0.36, S4: 0.21 },
      P0_P8: {},
      geography_tier: null,
      timeline: { short_term_days: 1, mid_term_days: 2, long_term_days: 3 },
      multiplier: 1,
    },
    meta: { engine: "clarity_elins_v2", view_kind: "v2" },
    _meta: { n_points: 2, ...meta },
  } as never;
}

const row = () => screen.getByTestId("attractor-prior-seal");

describe("ElinsV2View — #330 the prior seal row", () => {
  it("★ no prior seal says so in words — never a 0, never a blank", () => {
    render(<ElinsV2View envelope={envelope({})} />);
    expect(row()).toHaveTextContent("no prior seal");
    expect(row()).toHaveTextContent("—");
    expect(row().textContent).not.toMatch(/\b0\b/);
    expect(row().textContent?.trim()).not.toBe("");
  });

  it("a met seal names the state and says matched", () => {
    render(<ElinsV2View envelope={envelope({ prior_s_state: "S3", s_state_match: true })} />);
    expect(row()).toHaveTextContent("prior seal: S3");
    expect(row()).toHaveTextContent("matched");
  });

  it("★ a missed seal is NOT swallowed — the whole point of sealing first", () => {
    render(<ElinsV2View envelope={envelope({ prior_s_state: "S1", s_state_match: false })} />);
    expect(row()).toHaveTextContent("prior seal: S1");
    expect(row()).toHaveTextContent("missed");
  });

  it("a prior seal with no comparison reads undefined, not missed", () => {
    render(<ElinsV2View envelope={envelope({ prior_s_state: "S3" })} />);
    expect(row()).toHaveTextContent("prior seal: S3");
    expect(row()).toHaveTextContent("undefined");
    expect(row().textContent).not.toMatch(/missed/);
  });

  it("an older backend that sends neither key renders the absent case", () => {
    render(<ElinsV2View envelope={envelope({ prior_s_state: null, s_state_match: null })} />);
    expect(row()).toHaveTextContent("no prior seal");
  });

  it("★ a prior turn that named NO state is not the same as no prior turn", () => {
    // Since the seal follows the surface's own tie rule, a level field seals
    // nothing — and that is the COMMON case, so the row must not call it
    // "no prior seal", which would be false.
    render(<ElinsV2View envelope={envelope({ observed_prior: true })} />);
    expect(row()).toHaveTextContent("prior turn named no state");
    expect(row().textContent).not.toMatch(/no prior seal/);
  });

  it("and with no prior turn at all it still says no prior seal", () => {
    render(<ElinsV2View envelope={envelope({ observed_prior: false })} />);
    expect(row()).toHaveTextContent("no prior seal");
    expect(row().textContent).not.toMatch(/named no state/);
  });

  it("the row is present at n < 2, where the four percentages are not", () => {
    render(<ElinsV2View envelope={envelope({ n_points: 1, prior_s_state: "S3", s_state_match: true })} />);
    expect(screen.getByTestId("attractor-needs-prior")).toBeTruthy();
    expect(row()).toHaveTextContent("matched");
  });
});
