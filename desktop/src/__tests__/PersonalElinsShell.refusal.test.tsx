/**
 * #161a -- the refusal gate where the web has it (#238 / #237 (1)), on the
 * desktop Personal ELINS view. The fixture is the web test's (lifted from the
 * live capture): every bearing "unclear", the curvature note the reason.
 *
 * The shell wraps its body in the v1 DesktopShell chrome; stubbed to a
 * passthrough that renders only `center`, as OperatorConsoleShell.test does.
 */
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("../DesktopShell", () => ({
  default: ({ center }: { center: ReactNode }) => center,
}));
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, runEmotionalPhysics: vi.fn(), runElinsV2: vi.fn() };
});

import { runEmotionalPhysics, runElinsV2 } from "../lib/api";
import PersonalElinsShell from "../PersonalElinsShell";
import {
  physicsRefusal, elinsRefusal, sectionRefusal, ELINS_NO_SIGNAL_REASON, PHYSICS_DECLINED_REASON,
} from "../lib/refusal";

const REFUSAL_PROSE = "No specific situation provided. Cannot assess internal pattern without concrete context.";
const RP_PROSE = "No relational context provided. Cannot identify structural patterns without at least two parties or a specific interpersonal dynamic.";

const EP_REFUSED = {
  field_curvature: { intensity: "unclear", gradient_direction: "unclear", stability: "unclear", notes: REFUSAL_PROSE },
  edge_pressure: {
    signal_clarity: "unclear", signal_intensity: "unclear", coherence: "unclear",
    notes: "No external behavior or interaction described. Cannot assess how this lands on others.",
  },
  relational_primitives: {
    trust: "unclear", alignment: "unclear", boundary: "unclear",
    agency: "unclear", distance: "unclear", dominant_pattern: [], notes: RP_PROSE,
  },
  external_expression: {
    recommended_posture: [],
    message_guidance: [
      "Provide a specific situation, interaction, or relational dynamic to analyze",
      "Include context: who is involved, what triggered this, what outcome you want",
    ],
    friction_reduction_moves: ["Describe the concrete situation in plain language"],
    risk_if_unchanged: "Analysis cannot proceed without situational data.",
    next_step: "Share the specific interpersonal or internal situation you want analyzed.",
  },
  _meta: { model_id: "m", ts_ms: 1, parse_error: null },
};

/** A real reading: bearings that say something. */
const EP_READ = {
  ...EP_REFUSED,
  relational_primitives: {
    trust: "low", alignment: "misaligned", boundary: "contested",
    agency: "constrained", distance: "increasing", notes: "n",
  },
};

const ELINS_SPEAKING = {
  elins_version: "v2", region: null, input: {}, pipeline: {},
  outputs: {
    collapse_state: "soft", attractor: "S2",
    state_distribution: { S1: 0.7, S2: 0.1, S3: 0.1, S4: 0.1 },
    P0_P8: { P0: 0.33, P1: 0, P2: 0, P3: 0.22 },
    geography_tier: null,
    timeline: { short_term_days: 1, mid_term_days: 2, long_term_days: 3 },
    multiplier: 1,
  },
  meta: { engine: "clarity_elins_v2", view_kind: "v2" },
};

const ELINS_NO_SIGNAL = {
  ...ELINS_SPEAKING,
  pipeline: { L10_signature: { summary: { no_signal: true } } },
};

afterEach(() => vi.clearAllMocks());

function mount() {
  return render(<PersonalElinsShell onSignOut={vi.fn()} onNavigate={vi.fn()} />);
}

describe("#238 -- the reading itself (the web's, ported)", () => {
  it("every bearing unclear IS the refusal, and the curvature note is the reason", () => {
    const r = physicsRefusal(EP_REFUSED as never);
    expect(r.refused).toBe(true);
    expect(r.reason).toBe(REFUSAL_PROSE);
    expect(r.reason).not.toBe(RP_PROSE);
    expect(r.source).toBe("physics");
  });
  it("a partial reading is NOT a refusal; no response is an absence", () => {
    const partial = { ...EP_REFUSED, relational_primitives: { trust: "low", alignment: "unclear", boundary: "unclear", agency: "unclear", distance: "unclear", notes: "n" } };
    expect(physicsRefusal(partial as never).refused).toBe(false);
    expect(physicsRefusal(null).refused).toBe(false);
  });
  it("a declining reader that wrote no prose still gets a reason; a missing key is the same kind as unclear", () => {
    const noProse = { ...EP_REFUSED, field_curvature: {}, edge_pressure: {}, relational_primitives: { trust: "unclear" } };
    const r = physicsRefusal(noProse as never);
    expect(r.refused).toBe(true);
    expect(r.reason).toBe(PHYSICS_DECLINED_REASON);
  });
  it("ELINS no_signal is the second decline; physics is read first", () => {
    expect(elinsRefusal(ELINS_SPEAKING as never).refused).toBe(false);
    const e = elinsRefusal(ELINS_NO_SIGNAL as never);
    expect(e.refused && e.reason === ELINS_NO_SIGNAL_REASON && e.source === "elins").toBe(true);
    expect(sectionRefusal(EP_REFUSED as never, ELINS_NO_SIGNAL as never).source).toBe("physics");
    expect(sectionRefusal(EP_READ as never, ELINS_NO_SIGNAL as never).source).toBe("elins");
    expect(sectionRefusal(EP_READ as never, ELINS_SPEAKING as never).refused).toBe(false);
  });
});

describe("#161a -- desktop Personal ELINS: a refusal does not get a forecast", () => {
  it("★ the refused screen: sections 1, 3 and 4 carry the reason and no number, no guidance", async () => {
    vi.mocked(runEmotionalPhysics).mockResolvedValue(EP_REFUSED as never);
    vi.mocked(runElinsV2).mockResolvedValue(ELINS_SPEAKING as never);
    mount();
    expect((await screen.findByTestId("layer-refusal")).textContent).toBe(REFUSAL_PROSE);
    expect(screen.getByTestId("collapse-risk-refusal").textContent).toBe(REFUSAL_PROSE);
    expect(screen.getByTestId("field-weather-refusal").textContent).toBe(REFUSAL_PROSE);
    expect(screen.getByTestId("layer-refusal").getAttribute("title")).toBe("refused by: physics");
    expect(screen.queryByText("33%")).toBeNull();
    expect(screen.queryByText("22%")).toBeNull();
    expect(screen.queryByText(/Soft pressure rising/)).toBeNull();
    expect(screen.queryByText(/Provide a specific situation/)).toBeNull();
    expect(screen.queryByText(/do not sum to 100%/)).toBeNull();
  });

  it("★ a real reading: no refusal line; the numbers and the weather render", async () => {
    vi.mocked(runEmotionalPhysics).mockResolvedValue(EP_READ as never);
    vi.mocked(runElinsV2).mockResolvedValue(ELINS_SPEAKING as never);
    mount();
    expect(await screen.findByText("33%")).toBeTruthy();
    expect(screen.getByText("22%")).toBeTruthy();
    expect(screen.queryByTestId("layer-refusal")).toBeNull();
    expect(screen.queryByTestId("collapse-risk-refusal")).toBeNull();
    expect(screen.queryByTestId("field-weather-refusal")).toBeNull();
    expect(screen.getByText(/Soft pressure rising/)).toBeTruthy();
  });

  it("ELINS no_signal alone: section 1 speaks, sections 3 and 4 carry the rail's sentence", async () => {
    vi.mocked(runEmotionalPhysics).mockResolvedValue(EP_READ as never);
    vi.mocked(runElinsV2).mockResolvedValue(ELINS_NO_SIGNAL as never);
    mount();
    expect((await screen.findByTestId("collapse-risk-refusal")).textContent).toBe(ELINS_NO_SIGNAL_REASON);
    expect(screen.getByTestId("field-weather-refusal").textContent).toBe(ELINS_NO_SIGNAL_REASON);
    expect(screen.getByTestId("collapse-risk-refusal").getAttribute("title")).toBe("refused by: elins");
    expect(screen.queryByTestId("layer-refusal")).toBeNull();
    expect(screen.queryByText("33%")).toBeNull();
  });
});
