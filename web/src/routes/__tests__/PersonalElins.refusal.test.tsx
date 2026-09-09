/**
 * #238 · #237 (CT-1 2026-09-09) — A REFUSAL DOES NOT GET A FORECAST.
 *
 * Measured live on CT-1's own member session, 52 characters of seed text.
 * Section 1 refused correctly — every bearing "unclear", the prose "Cannot
 * assess internal pattern without concrete context." — and then, on the same
 * screen, section 3 printed "P0 risk 33% · P1 0% · P2 0% · P3 22%" and
 * section 4 printed "Soft pressure rising. Watch the edge for fragmentation."
 *
 * The fixture below IS that screen.
 */
import { afterEach, describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...actual, runEmotionalPhysics: vi.fn(), runElinsV2: vi.fn() };
});

import { runEmotionalPhysics, runElinsV2 } from "../../lib/api";
import PersonalElins from "../PersonalElins";
import {
  physicsRefusal, elinsRefusal, sectionRefusal,
  ELINS_NO_SIGNAL_REASON, PHYSICS_DECLINED_REASON,
} from "../../lib/refusal";

/** ★ THE FIXTURE BELOW IS LIFTED FROM THE LIVE CAPTURE, not written here:
 *  analysis/har/clarity.pro-mediations.com_v2_crhome_260902-1446.har, the
 *  /me/emotional_physics/analyze response whose bearings all read "unclear".
 *  A refuter found it after ET-1 had guessed the shape and put the reason in
 *  the wrong layer's notes. Every string below is that payload's. */
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
    // the live block: an instruction to the MEMBER in a field that means what
    // to say to ANOTHER PERSON, and the two keys with no word of CT-1's
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

afterEach(() => vi.clearAllMocks());

// ===========================================================================
// the reading itself
// ===========================================================================

describe("#238 — the one reading of 'a layer above declined'", () => {
  test("every bearing unclear IS the refusal, and its own prose is the reason", () => {
    const r = physicsRefusal(EP_REFUSED as never);
    expect(r.refused).toBe(true);
    // ★ the reason is quoted from the layer that EXPLAINS the decline
    // (field_curvature), not from the bearings that DETECT it -- measured.
    expect(r.reason).toBe(REFUSAL_PROSE);
    expect(r.reason).not.toBe(RP_PROSE);
    expect(r.source).toBe("physics");
  });

  test("a partial reading is NOT a refusal — some unclear bearings are a real answer", () => {
    const partial = {
      ...EP_REFUSED,
      relational_primitives: {
        trust: "low", alignment: "unclear", boundary: "unclear",
        agency: "unclear", distance: "unclear", notes: "n",
      },
    };
    expect(physicsRefusal(partial as never).refused).toBe(false);
  });

  test("no physics response at all is an ABSENCE, not a refusal", () => {
    expect(physicsRefusal(null).refused).toBe(false);
    expect(physicsRefusal(undefined).refused).toBe(false);
  });

  test("a declining reader that wrote no prose ANYWHERE still gets a reason", () => {
    const noProse = {
      ...EP_REFUSED,
      field_curvature: { intensity: "unclear" },
      edge_pressure: { coherence: "unclear" },
      relational_primitives: {
        trust: "unclear", alignment: "unclear", boundary: "unclear",
        agency: "unclear", distance: "unclear",
      },
    };
    expect(physicsRefusal(noProse as never).reason).toBe(PHYSICS_DECLINED_REASON);
  });

  test("★ THE HOLE A REFUTER FOUND: a dropped bearing key is not an escape", () => {
    // Four declining bearings plus ONE MISSING key used to read "not refused",
    // and the forecast spoke again -- CT-1's screen, one dropped key away.
    // The backend already scores missing and "unclear" identically.
    const oneMissing = {
      ...EP_REFUSED,
      relational_primitives: {
        trust: "unclear", alignment: "unclear", boundary: "unclear",
        agency: "unclear", notes: RP_PROSE,   // distance ABSENT
      },
    };
    expect(physicsRefusal(oneMissing as never).refused).toBe(true);
  });

  test("★ parse_error: empty layers are a decline, not a licence to speak", () => {
    const unparsed = {
      field_curvature: {}, edge_pressure: {}, relational_primitives: {},
      external_expression: {},
      _meta: { model_id: "m", ts_ms: 1, parse_error: "could not parse" },
    };
    expect(physicsRefusal(unparsed as never).refused).toBe(true);
  });

  test("#110(c) — no_signal survives the hop and is read where it lands", () => {
    const env = {
      ...ELINS_SPEAKING,
      pipeline: { L10_signature: { summary: { no_signal: true } } },
    };
    expect(elinsRefusal(env as never).refused).toBe(true);
    expect(elinsRefusal(env as never).reason).toBe(ELINS_NO_SIGNAL_REASON);
    expect(elinsRefusal(ELINS_SPEAKING as never).refused).toBe(false);
  });

  test("either layer silences what is below it", () => {
    expect(sectionRefusal(EP_REFUSED as never, ELINS_SPEAKING as never).source).toBe("physics");
    const noSig = { ...ELINS_SPEAKING, pipeline: { L10_signature: { summary: { no_signal: true } } } };
    expect(sectionRefusal(EP_READ as never, noSig as never).source).toBe("elins");
    expect(sectionRefusal(EP_READ as never, ELINS_SPEAKING as never).refused).toBe(false);
  });
});

// ===========================================================================
// the screen
// ===========================================================================

describe("#238 — nothing speaks below a refusal", () => {
  async function mount(ep: unknown, elins: unknown) {
    vi.mocked(runEmotionalPhysics).mockResolvedValue(ep as never);
    vi.mocked(runElinsV2).mockResolvedValue(elins as never);
    render(<MemoryRouter><PersonalElins /></MemoryRouter>);
    await screen.findByTestId("section-emotional-physics");
  }

  test("★ CT-1's screen: §3 produces NO percentage and carries the reason", async () => {
    await mount(EP_REFUSED, ELINS_SPEAKING);
    expect(await screen.findByTestId("collapse-risk-refusal")).toHaveTextContent(REFUSAL_PROSE);
    // not 33%, not 0%, not "balanced" — the cells are not rendered at all
    for (const p of ["P0", "P1", "P2", "P3"]) {
      expect(screen.queryByTestId(`risk-${p}`)).toBeNull();
    }
    expect(screen.queryByText(/33%/)).toBeNull();
    expect(screen.queryByText(/\b0%/)).toBeNull();
  });

  test("★ CT-1's screen: §4 assembles NOTHING from an empty envelope", async () => {
    await mount(EP_REFUSED, ELINS_SPEAKING);
    expect(await screen.findByTestId("field-weather-refusal")).toHaveTextContent(REFUSAL_PROSE);
    expect(screen.queryByText(/Soft pressure rising/)).toBeNull();
    expect(screen.queryByText(/Watch the edge for fragmentation/)).toBeNull();
    expect(screen.queryByText(/Field is/)).toBeNull();
  });

  test("the panels do NOT disappear — a member sees they exist and why they are quiet", async () => {
    await mount(EP_REFUSED, ELINS_SPEAKING);
    expect(screen.getByTestId("section-collapse-risk")).toBeInTheDocument();
    expect(screen.getByTestId("section-field-weather")).toBeInTheDocument();
  });

  test("§2 (the level field) is UNTOUCHED — it was honest already", async () => {
    await mount(EP_REFUSED, ELINS_SPEAKING);
    expect(screen.getByTestId("section-attractor")).toBeInTheDocument();
    expect(screen.queryByTestId("attractor-refusal")).toBeNull();
  });

  test("a real reading still speaks — the gate closes only on a refusal", async () => {
    await mount(EP_READ, ELINS_SPEAKING);
    expect(await screen.findByTestId("risk-P0")).toHaveTextContent("33%");
    expect(screen.queryByTestId("collapse-risk-refusal")).toBeNull();
    expect(screen.queryByTestId("field-weather-refusal")).toBeNull();
    expect(screen.getByText(/Soft pressure rising/)).toBeInTheDocument();
  });
});

// ===========================================================================
// #237 — the external expression block
// ===========================================================================

describe("#237 — the block carries the refusal, and no internal key", () => {
  async function mount(ep: unknown) {
    vi.mocked(runEmotionalPhysics).mockResolvedValue(ep as never);
    vi.mocked(runElinsV2).mockResolvedValue(ELINS_SPEAKING as never);
    render(<MemoryRouter><PersonalElins /></MemoryRouter>);
    await screen.findByTestId("section-emotional-physics");
  }

  test("★ (1) an instruction to the MEMBER never lands in 'what to say'", async () => {
    await mount(EP_REFUSED);
    expect(await screen.findByTestId("layer-refusal")).toHaveTextContent(REFUSAL_PROSE);
    expect(screen.queryByText(/Provide a specific situation/)).toBeNull();
    expect(screen.queryByText(/Include context/)).toBeNull();
    expect(screen.queryByTestId("layer-message_guidance")).toBeNull();
  });

  test("★ (2) no internal key reaches glass, and the holding back is DECLARED", async () => {
    await mount(EP_READ);
    expect(screen.queryByText(/risk_if_unchanged/)).toBeNull();
    expect(screen.queryByText(/next_step/)).toBeNull();
    expect(screen.queryByText(/ext_step/)).toBeNull();
    expect(screen.queryByTestId("layer-risk_if_unchanged")).toBeNull();
    // declared, with a count — never silently dropped
    const held = screen.getByTestId("layer-unnamed-external-expression");
    expect(held).toHaveTextContent("2 readings not yet named");
    // the keys live in the title, for CT-1, not in the prose
    expect(held).toHaveAttribute("title", "risk_if_unchanged · next_step");
  });

  test("(2) the rule is key-agnostic — a key the prompt never asked for is held too", async () => {
    const odd = {
      ...EP_READ,
      external_expression: { ...EP_READ.external_expression, ext_step: "x", reads_as_distant: false },
    };
    await mount(odd);
    expect(screen.queryByText(/ext_step/)).toBeNull();
    expect(screen.getByTestId("layer-unnamed-external-expression")).toHaveTextContent("4 readings not yet named");
  });

  test("★ (3) prose is not cut mid-word at 40 characters", async () => {
    const long = {
      ...EP_READ,
      external_expression: {
        recommended_posture: "Resubmit with a specific interpersonal or relational situation to analyze",
        notes: "n",
      },
    };
    await mount(long);
    const v = await screen.findByTestId("layer-recommended_posture");
    expect(v).toHaveTextContent("situation to analyze");
    expect(v.textContent).not.toBe("Resubmit with a specific interpersonal o");
  });

  test("(3) a value that DOES exceed the ceiling declares its cut", async () => {
    const huge = {
      ...EP_READ,
      external_expression: { recommended_posture: "x".repeat(500), notes: "n" },
    };
    await mount(huge);
    expect((await screen.findByTestId("layer-recommended_posture")).textContent).toMatch(/…$/);
  });

  test("★ (4) a list renders as a list, and nothing is dropped from it", async () => {
    const four = {
      ...EP_READ,
      external_expression: {
        message_guidance: ["one", "two", "three", "four"],
        notes: "n",
      },
    };
    await mount(four);
    const v = await screen.findByTestId("layer-message_guidance");
    // a real list element, one item per line -- not a joined sentence
    expect(v.tagName).toBe("UL");
    expect(v.querySelectorAll("li")).toHaveLength(4);
    // all four survive (the old renderer kept THREE and joined them with ", ")
    for (const w of ["one", "two", "three", "four"]) {
      expect(v).toHaveTextContent(w);
    }
    expect(v.textContent).not.toMatch(/one, two/);
  });
});
