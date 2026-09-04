/**
 * #162 (d) -- the personal view's rail: click a relationship, the row speaks
 * trust_signal's status (no_prior_yet -> the sentence; n = 1 -> the value,
 * no direction).
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";

vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, listThreads: vi.fn(), getRelationshipTurns: vi.fn(), runEmotionalPhysics: vi.fn(), runElinsV2: vi.fn() };
});

import * as api from "../../../lib/api";
import PersonalElinsInsightsPanel from "../PersonalElinsInsightsPanel";
import { cockpit } from "../../../state/cockpitStore";

afterEach(() => vi.clearAllMocks());

describe("PersonalElinsInsightsPanel -- the awaiting rail", () => {
  it("no_prior_yet -> the sentence", async () => {
    vi.mocked(api.getRelationshipTurns).mockResolvedValue({
      thread_id: "r1", turn_count: 0, turns: [],
      trust_signal: { status: "no_prior_yet", scored_turns: 0, theta_floor: 7, theta_ready: false },
    } as never);
    render(<PersonalElinsInsightsPanel />);
    await act(async () => { await cockpit.relationships.actions.open("r1"); });
    expect(screen.getByTestId("math-rail-basin-hop")).toHaveTextContent("basin_hop -- awaiting a second read");
  });
  it("n = 1 -> the value and no direction", async () => {
    vi.mocked(api.getRelationshipTurns).mockResolvedValue({
      thread_id: "r2", turn_count: 2, turns: [],
      trust_signal: { status: "value", value: 0.8333, scored_turns: 1, per_turn: [0.8333], theta_floor: 7, theta_ready: false },
    } as never);
    render(<PersonalElinsInsightsPanel />);
    await act(async () => { await cockpit.relationships.actions.open("r2"); });
    const row = screen.getByTestId("math-rail-basin-hop");
    expect(row).toHaveTextContent("basin_hop -- trust 0.8333");
    expect(row).not.toHaveTextContent(/rising|falling|flat/);
    expect(row).toHaveTextContent("awaiting a second read");   // theta not ready: the sentence stays
  });
});
