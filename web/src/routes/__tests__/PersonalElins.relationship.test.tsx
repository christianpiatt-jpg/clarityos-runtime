/**
 * #162 (c) -- ONE KEY, TWO DOORS. The staging route now sends the selected
 * relationship on Re-run; the mount run (the default seed, boilerplate) stays
 * anonymous so it never writes a turn under anyone.
 */
import { afterEach, describe, expect, test, vi } from "vitest";
import { fireEvent, render, screen, waitFor, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    runEmotionalPhysics: vi.fn(),
    runElinsV2: vi.fn(),
    getRelationshipTurns: vi.fn(),
    listThreads: vi.fn(),
  };
});

import * as api from "../../lib/api";
import PersonalElins from "../PersonalElins";
import { cockpit } from "../../state/cockpitStore";

const EP = { field_curvature: {}, edge_pressure: {}, relational_primitives: {}, external_expression: {},
  _meta: { model_id: null, ts_ms: 1, parse_error: null } };

afterEach(() => vi.clearAllMocks());

describe("PersonalElins route -- the run carries the selected relationship", () => {
  test("mount runs the default seed anonymously; Re-run sends thread_id", async () => {
    vi.mocked(api.runEmotionalPhysics).mockResolvedValue(EP as never);
    vi.mocked(api.runElinsV2).mockRejectedValue(new Error("no elins"));
    vi.mocked(api.getRelationshipTurns).mockResolvedValue({
      thread_id: "r1", turn_count: 0, turns: [],
      trust_signal: { status: "no_prior_yet", scored_turns: 0, theta_floor: 7, theta_ready: false },
    } as never);
    await act(async () => { await cockpit.relationships.actions.open("r1"); });

    render(<MemoryRouter><PersonalElins /></MemoryRouter>);
    await waitFor(() => expect(api.runEmotionalPhysics).toHaveBeenCalledTimes(1));
    // the mount run: the default seed, NO relationship
    expect(vi.mocked(api.runEmotionalPhysics).mock.calls[0][1]).toBeNull();
    expect(screen.getByTestId("personal-relationship")).toHaveTextContent("r1");

    fireEvent.click(await screen.findByTestId("personal-elins-rerun"));
    await waitFor(() => expect(api.runEmotionalPhysics).toHaveBeenCalledTimes(2));
    const [seed, rel] = vi.mocked(api.runEmotionalPhysics).mock.calls[1];
    expect(rel).toBe("r1");
    expect(typeof seed).toBe("string");
    await waitFor(() => expect(api.runElinsV2).toHaveBeenLastCalledWith(seed, null, "r1"));
  });
});
