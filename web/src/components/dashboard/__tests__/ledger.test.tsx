/**
 * #180b (7) -- /elins/dashboard: the scenario and version as provenance,
 * the entity row complete (degree · ep mean · domains), the primitive
 * intensity titled.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../../lib/auth", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/auth")>("../../../lib/auth");
  const state = { session: "s", user: "u", profile: null };
  return { ...actual, getAuthSnapshot: () => state, subscribeAuth: () => () => {} };
});
vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, elinsDashboard: vi.fn() };
});

import * as api from "../../../lib/api";
import DashboardRoot from "../DashboardRoot";
import EntitySummary from "../EntitySummary";
import GlobalPanel from "../GlobalPanel";

const DASH = "—";
const SECTION = { scenario_id: "sc_global_1", ep_mean: 0.42, domains: {}, top_primitives: [{ key: "pressure", intensity: 0.7 }], forecast: [], has_eso: false, available: true };
const SNAPSHOT = {
  ts: 1_788_000_000, date: "2026-09-04", global: SECTION, regional: {},
  macro: { last_run_id: null, last_run_ts: null, ep_mean: null, regions_count: null, external_signal_mode: null },
  entity_graph: { entity_count: 2, edge_count: 1, updated_ts: 1_788_000_000, top_entities: [
    { name: "Ava", degree: 4, ep_mean: 0.412, top_domains: ["personal", "social"] },
    { name: "Sproesser", degree: 1, ep_mean: 0.1, top_domains: [] },
  ], available: true },
  version: "dashboard.v38",
};

beforeEach(() => vi.mocked(api.elinsDashboard).mockResolvedValue({ ok: true, snapshot: SNAPSHOT } as never));

describe("dashboard provenance + the entity row (#180b 7)", () => {
  it("★ the scenario and the version beside the stamp", async () => {
    render(<MemoryRouter><DashboardRoot /></MemoryRouter>);
    const prov = await screen.findByTestId("dash-provenance");
    expect(prov).toHaveTextContent("scenario sc_global_1 · dashboard.v38");
    expect(within(prov).getByTitle("snapshot.global.scenario_id")).toBeInTheDocument();
    expect(within(prov).getByTitle("snapshot.version")).toBeInTheDocument();
  });
  it("★ the entity row: degree · ep mean · domains, a dash for no domains", () => {
    render(<MemoryRouter><EntitySummary entityGraph={SNAPSHOT.entity_graph as never} /></MemoryRouter>);
    const stats = screen.getAllByTestId("entity-stats");
    expect(stats[0]).toHaveTextContent("degree 4 · ep mean 0.412");
    const domains = screen.getAllByTestId("entity-domains");
    expect(domains[0]).toHaveTextContent("personal · social");
    expect(domains[1]).toHaveTextContent(DASH);
    expect(screen.getAllByTitle("snapshot.entity_graph.top_entities[].top_domains")).toHaveLength(2);
  });
  it("the primitive intensity carries its key", () => {
    render(<GlobalPanel section={SECTION as never} />);
    expect(screen.getByTitle("snapshot.global.top_primitives[].intensity")).toHaveTextContent("0.700");
  });
  it("no scenario reads a dash", async () => {
    vi.mocked(api.elinsDashboard).mockResolvedValue({ ok: true, snapshot: { ...SNAPSHOT, global: { ...SECTION, scenario_id: null }, version: "" } } as never);
    render(<MemoryRouter><DashboardRoot /></MemoryRouter>);
    const prov = await screen.findByTestId("dash-provenance");
    expect(prov).toHaveTextContent(`scenario ${DASH} · ${DASH}`);
  });
});
