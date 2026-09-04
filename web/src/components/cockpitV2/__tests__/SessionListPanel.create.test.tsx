/**
 * #179 -- one create per click.
 *
 * The HAR of 09-04 21:03 shows three relationships of one name minted in
 * four seconds: Enter pressed again while the first POST was in flight.
 * Now the first press is the create (the button and the key are inert
 * until it lands), and a name already in the list opens THAT relationship
 * and says "already here" -- nothing is minted.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, act, waitFor } from "@testing-library/react";

vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return {
    ...actual,
    listThreads: vi.fn(),
    createThread: vi.fn(),
    createProject: vi.fn(),
    getRelationshipTurns: vi.fn(),
  };
});

import * as api from "../../../lib/api";
import SessionListPanel from "../SessionListPanel";
import { cockpit } from "../../../state/cockpitStore";

const REL = { thread_id: "r1", title: "me and Ava", created_at: 1, updated_at: 2,
  message_count: 0, archived: false, summary: null, summary_ts_ms: null, project_id: "relationships" };
const NEW = { ...REL, thread_id: "r2", title: "Ava and Sproesser" };
const NO_TURNS = { thread_id: "r2", turn_count: 0, turns: [],
  trust_signal: { status: "no_prior_yet", scored_turns: 0, theta_floor: 7, theta_ready: false } };

beforeEach(async () => {
  vi.clearAllMocks();
  vi.mocked(api.listThreads).mockResolvedValue([REL] as never);
  vi.mocked(api.createProject).mockResolvedValue({ project_id: "relationships" } as never);
  vi.mocked(api.getRelationshipTurns).mockResolvedValue(NO_TURNS as never);
  await act(async () => { await cockpit.relationships.actions.load(); });
  act(() => { cockpit.view.actions.select("personal"); });
});

function openNaming() {
  render(<SessionListPanel />);
  fireEvent.click(screen.getByText("+ NEW"));
  return screen.getByPlaceholderText("me and Ava · Ava and Sproesser") as HTMLInputElement;
}

describe("SessionListPanel — one create per click (#179)", () => {
  it("★ Enter pressed three times while the POST is in flight mints ONE relationship", async () => {
    let land!: (m: unknown) => void;
    vi.mocked(api.createThread).mockImplementation(
      () => new Promise((resolve) => { land = resolve; }) as never,
    );
    const input = openNaming();
    fireEvent.change(input, { target: { value: "Ava and Sproesser" } });
    fireEvent.keyDown(input, { key: "Enter" });
    fireEvent.keyDown(input, { key: "Enter" });
    fireEvent.keyDown(input, { key: "Enter" });
    // the button is inert too
    const button = screen.getByText("Creating…") as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    fireEvent.click(button);

    await waitFor(() => expect(api.createThread).toHaveBeenCalledTimes(1));
    await act(async () => { land(NEW); });
    await waitFor(() => expect(screen.queryByPlaceholderText("me and Ava · Ava and Sproesser")).toBeNull());
    expect(api.createThread).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Ava and Sproesser")).toBeInTheDocument();
  });

  it("★ a name already in the list opens it and says so; nothing is minted", async () => {
    const input = openNaming();
    fireEvent.change(input, { target: { value: "  ME AND AVA " } });
    fireEvent.click(screen.getByText("Create"));

    expect(await screen.findByTestId("rel-already-here")).toHaveTextContent("already here");
    expect(api.createThread).not.toHaveBeenCalled();
    // focused: the existing row is the selected one
    await waitFor(() => {
      const row = screen.getByText("me and Ava").closest("button");
      expect(row?.className).toContain("is-selected");
    });
    // the box stays open with the name, so the member sees what happened
    expect(input.value).toBe("  ME AND AVA ");
  });

  it("typing again clears the notice", async () => {
    const input = openNaming();
    fireEvent.change(input, { target: { value: "me and Ava" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(await screen.findByTestId("rel-already-here")).toBeInTheDocument();
    fireEvent.change(input, { target: { value: "me and Ava 2" } });
    expect(screen.queryByTestId("rel-already-here")).toBeNull();
  });
});
