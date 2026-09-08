/**
 * #180a (i) -- the dashboard literals "EP mean" / "Top primitive" carry
 * their instrument (elins v38 snapshot) and the snapshot key in a title.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import GlobalPanel from "../GlobalPanel";
import RegionalGrid from "../RegionalGrid";
import MacroSummary from "../MacroSummary";

const SECTION = {
  scenario_id: null, ep_mean: 0.4213, domains: { personal: 1 },
  top_primitives: [{ key: "pressure", intensity: 0.7 }],
  forecast: [0.5, 0.4, 0.3], has_eso: false, available: true,
};

describe("dashboard literals carry the instrument (#180a i)", () => {
  it("GlobalPanel: EP mean · elins v38 snapshot, Top primitive · elins v38 snapshot", () => {
    render(<GlobalPanel section={SECTION as never} />);
    expect(screen.getByTitle("snapshot.global.ep_mean")).toHaveTextContent("EP mean · elins v38 snapshot");
    expect(screen.getByTitle("snapshot.global.top_primitives[0].key")).toHaveTextContent("Top primitive · elins v38 snapshot");
    expect(screen.getByTitle("snapshot.global.forecast")).toHaveTextContent("Forecast horizon · elins v38 snapshot");
    expect(screen.getByText("0.421")).toBeInTheDocument();
    expect(screen.queryByText("EP mean")).toBeNull();
  });

  it("RegionalGrid: each region's rows name the instrument and the region's key", () => {
    render(
      <MemoryRouter>
        <RegionalGrid regional={{ US: SECTION, EU: { ...SECTION, available: false } } as never} />
      </MemoryRouter>,
    );
    expect(screen.getByTitle("snapshot.regional.US.ep_mean")).toHaveTextContent("EP mean · elins v38 snapshot");
    expect(screen.getByTitle("snapshot.regional.US.top_primitives[0].key")).toHaveTextContent("Top primitive · elins v38 snapshot");
    expect(screen.queryByTitle("snapshot.regional.EU.ep_mean")).toBeNull();
    expect(screen.getByText("No runs yet")).toBeInTheDocument();
  });

  it("MacroSummary: the macro card's EP mean carries the instrument too", () => {
    render(
      <MemoryRouter>
        <MacroSummary macro={{ last_run_id: "run_1", last_run_ts: 1_788_000_000, ep_mean: 0.512, regions_count: 6, external_signal_mode: "cloud_only" } as never} />
      </MemoryRouter>,
    );
    expect(screen.getByTitle("snapshot.macro.ep_mean")).toHaveTextContent("EP mean · elins v38 snapshot");
    expect(screen.getByText("0.512")).toBeInTheDocument();
    expect(screen.getByText("Regions")).toBeInTheDocument();
  });
});
