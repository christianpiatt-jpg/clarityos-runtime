/**
 * #185 -- the personal physics surface: a layer's sub-keys read as CT-1's
 * words with the raw key in the title; a false reads its WORD; a missing
 * risk reads "—", never a manufactured 0%; the collapse section carries the
 * dictionary's word with the instrument key in its title.
 */
import { afterEach, describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...actual, runEmotionalPhysics: vi.fn(), runElinsV2: vi.fn() };
});

import { runEmotionalPhysics, runElinsV2 } from "../../lib/api";
import { labelFor } from "../../lib/labels";
import PersonalElins from "../PersonalElins";

const EP = {
  field_curvature: { intensity: "medium", gradient_direction: "mixed", stability: "unstable", stable: false, dominant_forces: ["time_pressure"], notes: "n" },
  edge_pressure: { signal_clarity: "mixed", signal_intensity: "medium", coherence: "fragmented", perceived_posture: ["ambivalent"], risk_of_misread: "high", notes: "n" },
  relational_primitives: { trust: "low", alignment: "misaligned", boundary: "contested", agency: "constrained", distance: "increasing", dominant_pattern: [], notes: "n" },
  external_expression: { recommended_posture: ["clarify_intent"], message_guidance: ["say it plainly"], friction_reduction_moves: [], reads_as_distant: false, notes: "n" },
  _meta: { model_id: "m", ts_ms: 1, parse_error: null },
};
const ELINS = {
  elins_version: "v2", region: null, input: {}, pipeline: {},
  outputs: {
    collapse_state: "none", attractor: "S1",
    state_distribution: { S1: 0.7, S2: 0.1, S3: 0.1, S4: 0.1 },
    P0_P8: { P0: 0.33 },   // P1..P3 missing on purpose
    geography_tier: null, timeline: { short_term_days: 1, mid_term_days: 2, long_term_days: 3 }, multiplier: 1,
  },
  meta: { engine: "clarity_elins_v2", view_kind: "v2" },
};

afterEach(() => vi.clearAllMocks());

describe("PersonalElins -- words, no zero fallbacks (#185)", () => {
  test("★ a layer's sub-keys read as words with the raw key in the title; a false reads its word", async () => {
    vi.mocked(runEmotionalPhysics).mockResolvedValue(EP as never);
    vi.mocked(runElinsV2).mockResolvedValue(ELINS as never);
    render(<MemoryRouter><PersonalElins /></MemoryRouter>);
    const stable = await screen.findByTestId("layer-stable");
    expect(stable).toHaveTextContent("false");
    expect(screen.getByTestId("layer-reads_as_distant")).toHaveTextContent("false");
    // the dictionary word, the raw key in the title -- the WORDS, never the raw key
    expect(screen.getByTitle("signal_clarity")).toHaveTextContent("how clear");
    expect(screen.getByTitle("recommended_posture")).toHaveTextContent("posture to take");
    expect(screen.getByTitle("message_guidance")).toHaveTextContent("what to say");
    expect(labelFor("friction_reduction_moves").word).not.toBe("friction_reduction_moves");
    expect(screen.queryByText(/recommended_posture:/)).toBeNull();
  });

  test("★ a missing risk reads a dash, never 0%; a present one reads its percent", async () => {
    vi.mocked(runEmotionalPhysics).mockResolvedValue(EP as never);
    vi.mocked(runElinsV2).mockResolvedValue(ELINS as never);
    render(<MemoryRouter><PersonalElins /></MemoryRouter>);
    expect(await screen.findByTestId("risk-P0")).toHaveTextContent("33%");
    expect(screen.getByTestId("risk-P1")).toHaveTextContent("—");
    expect(screen.getByTestId("risk-P3")).toHaveTextContent("—");
    expect(screen.getByTestId("risk-P1")).not.toHaveTextContent("0%");
    // the collapse section carries the dictionary's word, the key in its title
    expect(screen.getByTitle("collapse_state")).toHaveTextContent(labelFor("collapse_state").word);
  });
});
