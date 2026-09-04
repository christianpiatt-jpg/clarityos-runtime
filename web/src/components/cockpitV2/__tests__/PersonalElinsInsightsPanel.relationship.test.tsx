/**
 * #23 W2 -- the RELATIONSHIP header: name, turn count, the trust signal as
 * a STRING at n=0 (never 0.0), the last sealed stamp, seal/observe per turn,
 * and "no run yet" when the selected relationship has not been run.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";

vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return {
    ...actual,
    listThreads: vi.fn(),
    getRelationshipTurns: vi.fn(),
    runEmotionalPhysics: vi.fn(),
    runElinsV2: vi.fn(),
  };
});

import * as api from "../../../lib/api";
import PersonalElinsInsightsPanel, { trustLabel } from "../PersonalElinsInsightsPanel";
import { cockpit } from "../../../state/cockpitStore";

const REL = { thread_id: "r1", title: "Copilot-me-system_install", created_at: 1, updated_at: 2,
  message_count: 0, archived: false, summary: null, summary_ts_ms: null, project_id: "relationships" };
const NS = Date.UTC(2026, 8, 3, 18, 41, 0) * 1e6;   // 2026-09-03T18:41:00Z in ns

afterEach(() => vi.clearAllMocks());

describe("PersonalElinsInsightsPanel — the relationship header", () => {
  it("n = 0: name, 0 turns, the no_prior_yet STRING, no run yet", async () => {
    vi.mocked(api.listThreads).mockResolvedValue([REL] as never);
    vi.mocked(api.getRelationshipTurns).mockResolvedValue({
      thread_id: "r1", turn_count: 0, turns: [],
      trust_signal: { status: "no_prior_yet", scored_turns: 0, theta_floor: 7, theta_ready: false },
    } as never);
    render(<PersonalElinsInsightsPanel />);
    await act(async () => { await cockpit.relationships.actions.load(); });
    await act(async () => { await cockpit.relationships.actions.open("r1"); });

    expect(screen.getByTestId("rel-name")).toHaveTextContent("Copilot-me-system_install");
    expect(screen.getByTestId("rel-turn-count")).toHaveTextContent("0");
    expect(screen.getByTestId("rel-trust")).toHaveTextContent("no_prior_yet");
    expect(screen.getByTestId("rel-trust")).not.toHaveTextContent("0.0");
    expect(screen.getByTestId("rel-last-sealed")).toHaveTextContent("—");
    expect(screen.getByTestId("no-run-yet")).toBeInTheDocument();
  });

  it("n = 2: the count, a value with no direction, the last sealed stamp, seal/observe per turn", async () => {
    vi.mocked(api.getRelationshipTurns).mockResolvedValue({
      thread_id: "r1", turn_count: 2,
      turns: [
        { turn_index: 0, class: "geometry", ts_sealed: NS, ts_observed: NS + 60_000_000_000,
          expectation: { boundary: "clear" }, observation: { boundary: "clear" } },
        { turn_index: 1, class: "geometry", ts_sealed: NS + 60_000_000_000, ts_observed: null,
          expectation: { boundary: "clear" }, observation: null },
      ],
      trust_signal: { status: "value", value: 1, scored_turns: 1, per_turn: [1], theta_floor: 7, theta_ready: false },
    } as never);
    render(<PersonalElinsInsightsPanel />);
    await act(async () => { await cockpit.relationships.actions.open("r1"); });

    expect(screen.getByTestId("rel-turn-count")).toHaveTextContent("2");
    expect(screen.getByTestId("rel-trust")).toHaveTextContent("1 (1 scored)");
    expect(screen.getByTestId("rel-trust")).not.toHaveTextContent(/rising|falling|flat/);
    expect(screen.getByTestId("rel-last-sealed")).toHaveTextContent("2026-09-03 18:42");
    const rows = screen.getByTestId("rel-turns");
    expect(rows).toHaveTextContent("#0 · sealed 2026-09-03 18:41 · observed 2026-09-03 18:42");
    expect(rows).toHaveTextContent("#1 · sealed 2026-09-03 18:42 · awaiting return");
  });

  it("trustLabel: the strings at n=0 and undefined; the value carries a direction only when sent", () => {
    expect(trustLabel({ status: "no_prior_yet", scored_turns: 0, theta_floor: 7, theta_ready: false })).toBe("no_prior_yet");
    expect(trustLabel({ status: "undefined", scored_turns: 1, theta_floor: 7, theta_ready: false })).toBe("undefined");
    expect(trustLabel({ status: "value", value: 0.6667, scored_turns: 3, theta_floor: 7, theta_ready: false }))
      .toBe("0.6667 (3 scored)");
    expect(trustLabel({ status: "value", value: 0.5, direction: "falling", delta: -0.5, scored_turns: 2, theta_floor: 7, theta_ready: false }))
      .toBe("0.5 · falling (2 scored)");
    expect(trustLabel(null)).toBe("—");
  });
});
