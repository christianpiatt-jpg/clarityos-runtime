/**
 * #374 -- #184's line, after #355's domain floor.
 *
 * ★ THE FLOOR KILLED IT FOR EXACTLY THE RUNS IT WAS BUILT FOR.
 * #184 exists so a signal-less run can still report the one thing it found:
 * a domain hit. #355 3c then made `_domain_top` return None whenever the top
 * score is below DOMAIN_MIN_SIGNAL (2.0) -- and a signal-less text that
 * happened to hit ONE domain token scores exactly 1.0. Measured on the
 * backend: generate_ELINS("The court adjourned.") returns no_signal with
 * scores {legal: 1.0}, top null, effective_top null.
 *
 * The no-signal branch returns before DomainBlock renders, so this line is
 * the ONLY route that hit has to a reader. Reading `effective_top ?? top` it
 * rendered "no signal" instead, and the scores -- which the floor
 * deliberately still returns -- reached nobody.
 *
 * ★★ AND THE FIX DOES NOT RE-MAKE THE CLAIM THE FLOOR REFUSED. The floor's
 * own rule is that it withholds the NAME, not the reading. So a domain that
 * cleared the floor is still stated as a finding; one that did not is shown
 * as a signal with its magnitude and said to be too weak to name.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import ElinsV2View from "../ElinsV2View";

function envelope(domain: Record<string, unknown>) {
  const layer = (p: string) => ({ primitive: p, intensity: 0, edge_count: 0 });
  return {
    elins_version: "v2", region: null, input: { raw_text: "x" },
    pipeline: {
      L1_ingest: {}, L2_normalize: { normalized: true, note: "" },
      L3_domain: domain, L4_narrative: {},
      L5_pressure: layer("pressure"), L6_drift: layer("drift"),
      L7_basin: { region: null, available: false },
      L8_temporal: {
        forecast_5day: {}, forecast_engine: {}, etf_table: {},
        etf_agg: { n_365: 0, n_3650: 0, n_18250: 0 },
      },
      L9_alignment: layer("alignment"),
      L10_signature: { summary: { no_signal: true } },
    },
    outputs: {
      collapse_state: "none", attractor: "S1",
      state_distribution: { S1: 0.25, S2: 0.25, S3: 0.25, S4: 0.25 },
      P0_P8: {}, geography_tier: null,
      timeline: { short_term_days: 1, mid_term_days: 2, long_term_days: 3 },
      multiplier: 1,
    },
    meta: { engine: "clarity_elins_v2", view_kind: "v2" },
  } as never;
}

describe("ElinsV2View -- a domain below the floor (#374 / #184 / #355 3c)", () => {
  it("★ the shape the floor actually produces still reaches the reader", () => {
    // MUTATION: read only `effective_top ?? top` as before. This is the exact
    // wire shape measured from generate_ELINS("The court adjourned.").
    render(
      <ElinsV2View
        envelope={envelope({ top: null, effective_top: null, scores: { legal: 1.0 } })}
        onRun={() => {}}
      />,
    );
    const line = screen.getByTestId("elins-no-signal");
    expect(line).toHaveTextContent("legal");
    expect(line).toHaveTextContent("1");
    // and it does NOT silently fall back to the bare no-signal sentence
    expect(line.textContent ?? "").not.toMatch(/^no signal —/);
  });

  it("★ it reports a SIGNAL, not a domain -- the floor withheld the name", () => {
    // MUTATION: render the below-floor case with the same wording as a named
    // one. The floor refused to make the categorical claim; this line must
    // not make it on the floor's behalf.
    render(
      <ElinsV2View
        envelope={envelope({ top: null, effective_top: null, scores: { legal: 1.0 } })}
      />,
    );
    const text = screen.getByTestId("elins-no-signal").textContent ?? "";
    expect(text).toMatch(/too weak to name/);
    expect(text).not.toMatch(/but domain:/);
  });

  it("a domain that DID clear the floor is still stated as a finding", () => {
    // MUTATION: route every case through the below-floor wording. #184's
    // original line must survive #374 intact.
    render(
      <ElinsV2View
        envelope={envelope({ top: "housing", effective_top: "housing", scores: { housing: 4.0 } })}
      />,
    );
    expect(screen.getByTestId("elins-no-signal"))
      .toHaveTextContent("no reading — but domain: housing (4)");
  });

  it("★ the highest-scoring domain wins, with an alphabetical tiebreak", () => {
    // MUTATION: take Object.keys()[0], i.e. insertion order. Determinism is
    // the whole reason _domain_top sorts; this line must not disagree with it.
    render(
      <ElinsV2View
        envelope={envelope({ top: null, effective_top: null, scores: { work: 0.2, legal: 1.0 } })}
      />,
    );
    expect(screen.getByTestId("elins-no-signal")).toHaveTextContent("legal");

    render(
      <ElinsV2View
        envelope={envelope({ top: null, effective_top: null, scores: { work: 1.0, legal: 1.0 } })}
      />,
    );
    // ties break alphabetically, as _domain_top does
    expect(screen.getAllByTestId("elins-no-signal").at(-1)).toHaveTextContent("legal");
  });

  it("no scores at all -> the bare no-signal line, unchanged", () => {
    // MUTATION: return a fabricated entry for an empty scores dict. Absence
    // of a hit is still absence; #374 must not manufacture one.
    render(<ElinsV2View envelope={envelope({ top: null, effective_top: null, scores: {} })} />);
    expect(screen.getByTestId("elins-no-signal").textContent ?? "").toMatch(/^no signal —/);
  });
});
