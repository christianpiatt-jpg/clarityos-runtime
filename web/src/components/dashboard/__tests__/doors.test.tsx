/**
 * #145 -- /dashboard is the WINDOW every member may look through; the
 * doors are the admin's. #308 -- the four card links are in-page anchors
 * (/dashboard#regional etc.), no longer doors into /founder; the footer
 * keeps one /founder door and the /elins link. All of them render only for
 * the controller.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const authState: {
  session: string | null;
  user: string | null;
  profile: { cohort?: string | null; controller?: boolean } | null;
} = { session: "sess_test", user: "u", profile: null };

vi.mock("../../../lib/auth", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/auth")>("../../../lib/auth");
  return { ...actual, getAuthSnapshot: () => authState, subscribeAuth: () => () => {} };
});
vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, elinsDashboard: vi.fn() };
});

import * as api from "../../../lib/api";
import DashboardRoot from "../DashboardRoot";

const SNAPSHOT = {
  ts: 1_788_000_000,
  date: "2026-09-04",
  global: { scenario_id: null, ep_mean: 0.42, domains: {}, top_primitives: [], forecast: [], has_eso: false, available: false },
  regional: {},
  macro: { last_run_id: null, last_run_ts: null, ep_mean: null, regions_count: null, external_signal_mode: null },
  entity_graph: { entity_count: 0, edge_count: 0, updated_ts: 0, top_entities: [], available: false },
  version: "test",
};

function doors(container: HTMLElement) {
  return {
    founder: container.querySelectorAll('a[href="/founder"]').length,
    elins: container.querySelectorAll('a[href="/elins"]').length,
    anchors: ["regional", "macro", "entities", "continuity"]
      .filter((a) => container.querySelector(`a[href="/dashboard#${a}"]`) !== null).length,
  };
}

beforeEach(() => {
  vi.mocked(api.elinsDashboard).mockResolvedValue({ ok: true, snapshot: SNAPSHOT } as never);
});

describe("the dashboard doors (#145)", () => {
  it("★ a member sees the window and no door", async () => {
    authState.profile = { cohort: "founding", controller: false };
    const { container } = render(<MemoryRouter><DashboardRoot /></MemoryRouter>);
    await screen.findByText("Entity graph");
    expect(screen.getByText("Macro-ELINS")).toBeInTheDocument();
    expect(doors(container)).toEqual({ founder: 0, elins: 0, anchors: 0 });
  });

  it("★ the controller sees ONE founder door, the feed link, and four in-page anchors (#308)", async () => {
    authState.profile = { cohort: "controller", controller: true };
    const { container } = render(<MemoryRouter><DashboardRoot /></MemoryRouter>);
    await screen.findByText("Entity graph");
    expect(doors(container)).toEqual({ founder: 1, elins: 1, anchors: 4 });
    for (const id of ["global", "regional", "macro", "entities", "continuity"]) {
      expect(container.querySelector(`#${id}`)).not.toBeNull();
    }
  });

  it("a null profile fails closed: no door", async () => {
    authState.profile = null;
    const { container } = render(<MemoryRouter><DashboardRoot /></MemoryRouter>);
    await screen.findByText("Entity graph");
    expect(doors(container)).toEqual({ founder: 0, elins: 0, anchors: 0 });
  });
});

describe("the dashboard anchors (#308)", () => {
  it("★ the fragment walks to its card once the snapshot has rendered", async () => {
    authState.profile = { cohort: "founding", controller: true };
    const spy = vi.spyOn(Element.prototype, "scrollIntoView").mockImplementation(() => {});
    render(<MemoryRouter initialEntries={["/dashboard#regional"]}><DashboardRoot /></MemoryRouter>);
    await waitFor(() => expect(spy).toHaveBeenCalled());
    expect((spy.mock.contexts as Element[]).map((e) => e.id)).toContain("regional");
    // a Refresh replaces the snapshot; it must not walk the page back to the card
    const fetches = vi.mocked(api.elinsDashboard).mock.calls.length;   // the mock's count spans the file
    fireEvent.click(screen.getByText("Refresh"));
    await waitFor(() => expect(vi.mocked(api.elinsDashboard).mock.calls.length).toBe(fetches + 1));
    await act(async () => { await Promise.resolve(); });
    expect(spy).toHaveBeenCalledTimes(1);
    spy.mockRestore();
  });
});
