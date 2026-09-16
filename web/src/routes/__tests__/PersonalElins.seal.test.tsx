/**
 * #303 · #305 · #307 (CT-1 2026-09-16) -- seal what reads, count what counts,
 * on the personal surface.
 *
 * A1  the render is a MAP (three readings) and a PROJECTION (one field,
 *     risk_if_unchanged), stamped "sealed at turn <_meta.window_last_message>";
 *     the model line names the ring.
 * A2  counsel never lands on the glass.
 * A4  the run carries whose field it reads; the door's refusal renders in the
 *     #238 shape (the panel exists, says why, nothing below speaks, no banner).
 * E2  the four percentages render only at n >= 2; at a single read the card
 *     says S1/S2 need a prior read.
 * C3  P0-P3 are captioned "derived from stress only" while edges == 0.
 * C4  the weather sentence drops its verb until n >= 2.
 */
import { afterEach, describe, expect, test, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...actual, runEmotionalPhysics: vi.fn(), runElinsV2: vi.fn() };
});

import { ApiError, runEmotionalPhysics, runElinsV2 } from "../../lib/api";
import PersonalElins from "../PersonalElins";
import { NEEDS_PRIOR_READ, DERIVED_FROM_STRESS_ONLY } from "../../lib/counts";

const EP = {
  field_curvature: { intensity: "medium", gradient_direction: "mixed", stability: "unstable", dominant_forces: ["time_pressure"], notes: "split" },
  edge_pressure: { signal_clarity: "mixed", signal_intensity: "medium", coherence: "fragmented", perceived_posture: ["ambivalent"], risk_of_misread: "high", notes: "distant" },
  relational_primitives: { trust: "low", alignment: "misaligned", boundary: "contested", agency: "constrained", distance: "increasing", notes: "n" },
  external_expression: {
    recommended_posture: ["clarify_intent"],
    risk_if_unchanged: "drift continues",
    counsel: { message_guidance: ["say it plainly"], friction_reduction_moves: ["one checkpoint"], next_step: "send three lines" },
  },
  _meta: { model_id: "anthropic:m", ts_ms: 1, parse_error: null, ring: "meaning", window_last_message: 7 },
};

function elins(nPoints: number, edges: number) {
  return {
    elins_version: "v2", region: null, input: {},
    pipeline: { L4_narrative: { edge_count: edges, threshold: 0.05 } },
    outputs: {
      collapse_state: "soft", attractor: "S2",
      state_distribution: { S1: 0.7, S2: 0.1, S3: 0.1, S4: 0.1 },
      P0_P8: { P0: 0.33, P1: 0, P2: 0, P3: 0.22 },
      geography_tier: null, timeline: { short_term_days: 1, mid_term_days: 2, long_term_days: 3 }, multiplier: 1,
    },
    meta: { engine: "clarity_elins_v2", view_kind: "v2" },
    _meta: { ring: "event", n_points: nPoints },
  };
}

/** Mount, then choose a field: the first choice runs the default seed. */
async function mount(ep: unknown, env: unknown) {
  vi.mocked(runEmotionalPhysics).mockResolvedValue(ep as never);
  vi.mocked(runElinsV2).mockResolvedValue(env as never);
  render(<MemoryRouter><PersonalElins /></MemoryRouter>);
  await screen.findByTestId("section-emotional-physics");
  expect(vi.mocked(runEmotionalPhysics)).not.toHaveBeenCalled();   // #303 A4 -- nothing knocks before a choice
  fireEvent.change(screen.getByTestId("whose-field"), { target: { value: "author" } });
  await waitFor(() => expect(vi.mocked(runEmotionalPhysics)).toHaveBeenCalled());
}

afterEach(() => vi.clearAllMocks());

describe("#303 A1/A2 — a map, a projection, a seal", () => {
  test("the projection renders ONE field under CT-1's word; counsel is never on the glass", async () => {
    await mount(EP, elins(2, 3));
    expect(await screen.findByTestId("layer-risk_if_unchanged")).toHaveTextContent("drift continues");
    expect(screen.getByTitle("risk_if_unchanged")).toHaveTextContent("if nothing changes");
    for (const s of ["say it plainly", "one checkpoint", "send three lines", "clarify_intent"]) {
      expect(screen.queryByText(new RegExp(s))).toBeNull();
    }
    // the three map cards are still there
    expect(screen.getByTestId("bearings-card")).toBeInTheDocument();
    expect(screen.getByTitle("signal_clarity")).toBeInTheDocument();
  });

  test("the model line names the ring and the turn the window sealed at", async () => {
    await mount(EP, elins(2, 3));
    expect(await screen.findByTestId("physics-model-line"))
      .toHaveTextContent("model anthropic:m · ring meaning · sealed at turn 7");
  });

  test("no window on the wire: the seal reads a dash, never a date", async () => {
    await mount({ ...EP, _meta: { model_id: "m", ts_ms: 1, parse_error: null } }, elins(2, 3));
    expect(await screen.findByTestId("physics-model-line")).toHaveTextContent("sealed at turn —");
  });
});

describe("#303 A4 — whose field", () => {
  const MSG = "a personal run names whose field it reads: author, addressee or observer";

  test("★ the door refused: the #238 shape in section 1, nothing below speaks, no banner", async () => {
    vi.mocked(runEmotionalPhysics).mockRejectedValue(new ApiError("whose_field_required", MSG, 400));
    vi.mocked(runElinsV2).mockResolvedValue(elins(2, 3) as never);
    render(<MemoryRouter><PersonalElins /></MemoryRouter>);
    fireEvent.change(screen.getByTestId("whose-field"), { target: { value: "author" } });
    const line = await screen.findByTestId("physics-refusal");
    expect(line).toHaveTextContent(MSG);
    expect(line).toHaveAttribute("title", "refused by: whose_field");
    expect(vi.mocked(runElinsV2)).not.toHaveBeenCalled();
    expect(screen.queryByTestId("risk-P0")).toBeNull();
    expect(screen.queryByTestId("physics-model-line")).toBeNull();
    // the sentence appears ONCE: in the section, never as a red banner too
    expect(screen.getAllByText(MSG)).toHaveLength(1);
    // the title never claims a field the door refused
    expect(screen.getByTestId("physics-title").textContent).not.toMatch(/field:/);
  });

  test("the member chooses; the first choice runs the seed, the run carries the word, the title names the ACCEPTED field", async () => {
    vi.mocked(runEmotionalPhysics).mockResolvedValue(EP as never);
    vi.mocked(runElinsV2).mockResolvedValue(elins(2, 3) as never);
    render(<MemoryRouter><PersonalElins /></MemoryRouter>);
    const select = screen.getByTestId("whose-field") as HTMLSelectElement;
    expect(select.value).toBe("");
    expect(Array.from(select.options).map((o) => o.value)).toEqual(["", "author", "addressee", "observer", "instrument"]);
    expect(screen.getByTestId("physics-title").textContent).not.toMatch(/field:/);
    fireEvent.change(select, { target: { value: "observer" } });
    await waitFor(() => expect(vi.mocked(runEmotionalPhysics)).toHaveBeenCalledWith(
      expect.any(String), null, "personal", "observer",
    ));
    expect(await screen.findByTestId("physics-title")).toHaveTextContent("field: observer");
    // a second choice does not re-run by itself; Re-run carries the new word
    fireEvent.change(select, { target: { value: "author" } });
    expect(vi.mocked(runEmotionalPhysics)).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByTestId("personal-elins-rerun"));
    await waitFor(() => expect(vi.mocked(runEmotionalPhysics)).toHaveBeenLastCalledWith(
      expect.any(String), null, "personal", "author",
    ));
  });
});

describe("#307 E2 / #305 C3 C4 — count what counts", () => {
  test("★ a single read: S1/S2 need a prior read, no percentages; P0-P3 say 'derived from stress only'; the weather has no verb", async () => {
    await mount(EP, elins(1, 0));
    expect(await screen.findByTestId("attractor-needs-prior")).toHaveTextContent(NEEDS_PRIOR_READ);
    expect(screen.queryByTestId("attractor-shares")).toBeNull();
    expect(screen.getByTestId("section-attractor").textContent).not.toMatch(/\d+%/);
    expect(screen.getByTestId("collapse-risk-stress-only")).toHaveTextContent(DERIVED_FROM_STRESS_ONLY);
    expect(screen.getByTestId("risk-P0")).toHaveTextContent("33%");   // the cells still render
    expect(screen.getByTestId("section-field-weather")).toHaveTextContent("Soft pressure.");
    expect(screen.queryByText(/rising/)).toBeNull();
  });

  test("a prior read: the four percentages, no stress-only caption, the verb is back", async () => {
    await mount(EP, elins(2, 3));
    expect(await screen.findByTestId("attractor-shares")).toHaveTextContent("S1: 70%");
    expect(screen.queryByTestId("attractor-needs-prior")).toBeNull();
    expect(screen.queryByTestId("collapse-risk-stress-only")).toBeNull();
    expect(screen.getByText(/Soft pressure rising/)).toBeInTheDocument();
  });

  test("no n on the wire is NOT a prior read", async () => {
    await mount(EP, { ...elins(2, 3), _meta: { ring: "event" } });
    expect(await screen.findByTestId("attractor-needs-prior")).toBeInTheDocument();
  });
});
