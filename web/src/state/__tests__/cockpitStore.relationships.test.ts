/**
 * #23 W2 -- the store: open() fetches what the relationship saved into
 * relationships.detail[id]; the personal read is kept per relationship.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    listThreads: vi.fn(),
    getRelationshipTurns: vi.fn(),
    runEmotionalPhysics: vi.fn(),
    runElinsV2: vi.fn(),
    createProject: vi.fn(),
    createThread: vi.fn(),
  };
});

import * as api from "../../lib/api";
import { cockpit, useCockpit } from "../cockpitStore";

const REL = (id: string, title: string) => ({
  thread_id: id, title, created_at: 1, updated_at: 2, message_count: 0,
  archived: false, summary: null, summary_ts_ms: null, project_id: "relationships",
});
const EMPTY = (id: string) => ({
  thread_id: id, turn_count: 0, turns: [],
  trust_signal: { status: "no_prior_yet", scored_turns: 0, theta_floor: 7, theta_ready: false },
});

afterEach(() => vi.clearAllMocks());

describe("relationships.open() reads what the relationship saved", () => {
  it("populates detail[id] loading -> ready", async () => {
    vi.mocked(api.listThreads).mockResolvedValue([REL("r1", "Copilot-me-system_install")] as never);
    vi.mocked(api.getRelationshipTurns).mockResolvedValue(EMPTY("r1") as never);
    const { result } = renderHook(() => useCockpit((s) => s.relationships));
    await act(async () => { await cockpit.relationships.actions.load(); });
    await act(async () => { await cockpit.relationships.actions.open("r1"); });
    expect(api.getRelationshipTurns).toHaveBeenCalledWith("r1");
    expect(result.current.activeId).toBe("r1");
    expect(result.current.detailStatus).toBe("ready");
    expect(result.current.detail.r1.turn_count).toBe(0);
    expect(result.current.detail.r1.trust_signal.status).toBe("no_prior_yet");
  });

  it("a failed read lands in detailError and leaves the other details alone", async () => {
    vi.mocked(api.getRelationshipTurns).mockRejectedValueOnce(new Error("thread not found"));
    const { result } = renderHook(() => useCockpit((s) => s.relationships));
    await act(async () => { await cockpit.relationships.actions.open("r-foreign"); });
    expect(result.current.detailStatus).toBe("error");
    expect(result.current.detailError).toMatch(/thread not found/);
    expect(result.current.detail.r1).toBeDefined();
    expect(result.current.detail["r-foreign"]).toBeUndefined();
  });

  it("the personal read is kept per relationship: switching shows that one's last run or nothing", async () => {
    vi.mocked(api.getRelationshipTurns).mockResolvedValue(EMPTY("r1") as never);
    const EP = { field_curvature: {}, edge_pressure: {}, relational_primitives: {}, _meta: {} };
    vi.mocked(api.runEmotionalPhysics).mockResolvedValue(EP as never);
    vi.mocked(api.runElinsV2).mockRejectedValue(new Error("no elins"));
    const { result } = renderHook(() => useCockpit((s) => s.personal));

    await act(async () => { await cockpit.relationships.actions.open("r1"); });
    await act(async () => { await cockpit.personal.actions.run("seed text"); });
    expect(api.runEmotionalPhysics).toHaveBeenCalledWith("seed text", "r1");
    expect(result.current.ep).toBe(EP);
    expect(result.current.runs.r1?.ep).toBe(EP);
    // the run re-reads what the relationship saved (the count moves)
    expect(api.getRelationshipTurns).toHaveBeenLastCalledWith("r1");

    await act(async () => { await cockpit.relationships.actions.open("r2"); });
    expect(result.current.ep).toBeNull();           // r2 has no run yet
    expect(result.current.status).toBe("ready");    // and does NOT auto-run

    await act(async () => { await cockpit.relationships.actions.open("r1"); });
    expect(result.current.ep).toBe(EP);             // r1's read comes back
  });
});

describe("the refuter pass", () => {
  it("create() opens the new relationship: no run yet under the new name, its turns read", async () => {
    vi.mocked(api.createProject).mockResolvedValue({ project_id: "relationships" } as never);
    vi.mocked(api.createThread).mockResolvedValue(REL("r-new", "Ava") as never);
    vi.mocked(api.getRelationshipTurns).mockResolvedValue(EMPTY("r-new") as never);
    // two hooks with STABLE selectors: an object literal selector is a new
    // snapshot every render and useSyncExternalStore loops on it
    const rel = renderHook(() => useCockpit((s) => s.relationships));
    const per = renderHook(() => useCockpit((s) => s.personal));
    // r1 carries a run from the test above; the new relationship must not inherit it
    await act(async () => { await cockpit.relationships.actions.open("r1"); });
    expect(per.result.current.ep).not.toBeNull();
    await act(async () => { await cockpit.relationships.actions.create("Ava"); });
    expect(rel.result.current.activeId).toBe("r-new");
    expect(per.result.current.ep).toBeNull();
    expect(api.getRelationshipTurns).toHaveBeenLastCalledWith("r-new");
    expect(rel.result.current.detail["r-new"].turn_count).toBe(0);
  });

  it("a run that lands after a switch is kept under ITS relationship and never shown under the new one", async () => {
    let resolveEp: (v: unknown) => void = () => {};
    vi.mocked(api.runEmotionalPhysics).mockImplementation(
      () => new Promise((res) => { resolveEp = res; }) as never,
    );
    vi.mocked(api.runElinsV2).mockRejectedValue(new Error("no elins"));
    vi.mocked(api.getRelationshipTurns).mockImplementation(async (id: string) => EMPTY(id) as never);
    // two hooks with STABLE selectors: an object literal selector is a new
    // snapshot every render and useSyncExternalStore loops on it
    const rel = renderHook(() => useCockpit((s) => s.relationships));
    const per = renderHook(() => useCockpit((s) => s.personal));
    await act(async () => { await cockpit.relationships.actions.open("r-a"); });
    let running: Promise<void> = Promise.resolve();
    act(() => { running = cockpit.personal.actions.run("seed for a"); });
    await act(async () => { await cockpit.relationships.actions.open("r-b"); });
    expect(per.result.current.status).toBe("loading");   // a run is in flight
    const LATE = { field_curvature: {}, edge_pressure: {}, relational_primitives: {}, _meta: {} };
    await act(async () => { resolveEp(LATE); await running; });
    expect(rel.result.current.activeId).toBe("r-b");
    expect(per.result.current.runs["r-a"]?.ep).toBe(LATE);   // kept under r-a
    expect(per.result.current.ep).toBeNull();                 // r-b shows nothing
    expect(per.result.current.status).toBe("ready");
  });
});
