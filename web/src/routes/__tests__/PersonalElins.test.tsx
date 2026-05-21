// v54-followup — Personal ELINS route tests. Mocks the API helpers
// from ../../lib/api at module scope so the component renders without
// hitting fetch / localStorage / the real backend.

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import type {
  ElinsV2Envelope,
  EmotionalPhysicsResponse,
} from "../../lib/api";
import PersonalElins from "../PersonalElins";

// ---------------------------------------------------------------------------
// API mocks
// ---------------------------------------------------------------------------
vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>(
    "../../lib/api",
  );
  return {
    ...actual,
    runEmotionalPhysics: vi.fn(),
    runElinsV2: vi.fn(),
  };
});

import { runEmotionalPhysics, runElinsV2 } from "../../lib/api";
const mockEp = vi.mocked(runEmotionalPhysics);
const mockElins = vi.mocked(runElinsV2);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------
function makeEp(): EmotionalPhysicsResponse {
  return {
    field_curvature: {
      intensity: "medium",
      gradient_direction: "mixed",
      stability: "unstable",
      dominant_forces: ["time_pressure"],
      notes: "split between two roles",
    },
    edge_pressure: {
      signal_clarity: "mixed",
      signal_intensity: "medium",
      coherence: "fragmented",
      perceived_posture: ["ambivalent"],
      risk_of_misread: "high",
      notes: "may read as distant",
    },
    relational_primitives: {
      trust: "fluctuating",
      alignment: "partially_aligned",
      boundary: "soft",
      agency: "partial",
      distance: "increasing",
      dominant_pattern: ["boundary_uncertainty"],
      notes: "boundary needs naming",
    },
    external_expression: {
      recommended_posture: ["clarify_intent"],
      message_guidance: ["state the constraint plainly"],
      friction_reduction_moves: ["propose a single next checkpoint"],
      risk_if_unchanged: "drift continues",
      next_step: "send a 3-line clarification",
      notes: "send a 3-line clarification within 24h",
    },
    _meta: {
      model_id: "anthropic:claude-3.7",
      ts_ms: 1_700_000_000_000,
      parse_error: null,
    },
  };
}

function makeElins(): ElinsV2Envelope {
  return {
    elins_version: "elins.v2.0",
    region: null,
    outputs: {
      collapse_state: "soft",
      attractor: "S2",
      state_distribution: { S1: 0.22, S2: 0.30, S3: 0.28, S4: 0.20 },
      P0_P8: {
        P0: 0.18, P1: 0.12, P2: 0.07,
        P3: 0.15, P4: 0.10, P5: 0.05,
        P6: 0.13, P7: 0.12, P8: 0.08,
      },
      geography_tier: "T2",
      timeline: { short_term_days: 365, mid_term_days: 3650, long_term_days: 18250 },
      multiplier: 1.43,
    },
  };
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------
beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests — Section 4 of the brief
// ---------------------------------------------------------------------------
describe("PersonalElins route", () => {
  test("Personal ELINS loads on mount", async () => {
    mockEp.mockResolvedValue(makeEp());
    mockElins.mockResolvedValue(makeElins());

    render(
      <MemoryRouter>
        <PersonalElins />
      </MemoryRouter>,
    );

    // Scope to the heading — the same label also appears as a NavItem
    // button in the sidebar, so a bare findByText would be ambiguous.
    expect(
      await screen.findByRole("heading", { name: "Personal ELINS" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Your personal macro snapshot/i),
    ).toBeInTheDocument();
    // The endpoints were called with the default seed text.
    await waitFor(() => {
      expect(mockEp).toHaveBeenCalledTimes(1);
      expect(mockElins).toHaveBeenCalledTimes(1);
    });
    // Sections rendered with results.
    expect(screen.getByTestId("section-emotional-physics")).toBeInTheDocument();
    expect(screen.getByTestId("section-attractor")).toBeInTheDocument();
    expect(screen.getByTestId("section-collapse-risk")).toBeInTheDocument();
    expect(screen.getByTestId("section-field-weather")).toBeInTheDocument();
  });

  test("Emotional Physics fields render when EP returns", async () => {
    mockEp.mockResolvedValue(makeEp());
    mockElins.mockResolvedValue(makeElins());

    render(
      <MemoryRouter>
        <PersonalElins />
      </MemoryRouter>,
    );

    // The 4 layer notes from the fixture should land in the DOM.
    expect(
      await screen.findByText(/split between two roles/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/may read as distant/i)).toBeInTheDocument();
    expect(screen.getByText(/boundary needs naming/i)).toBeInTheDocument();
    expect(
      screen.getByText(/send a 3-line clarification/i),
    ).toBeInTheDocument();
  });

  test("ELINS v2 run updates state on Re-run click", async () => {
    // First load returns one envelope; re-run returns a different one.
    mockEp.mockResolvedValue(makeEp());
    const first = makeElins();   // attractor S2
    const second = makeElins();
    second.outputs.attractor = "S4";
    second.outputs.collapse_state = "hard";
    mockElins
      .mockResolvedValueOnce(first)
      .mockResolvedValueOnce(second);

    render(
      <MemoryRouter>
        <PersonalElins />
      </MemoryRouter>,
    );

    // First render: S2 chip appears.
    await waitFor(() => {
      const attractorSection = screen.getByTestId("section-attractor");
      expect(attractorSection).toHaveTextContent("S2");
    });

    // Click Re-run.
    const btn = screen.getByTestId("personal-elins-rerun");
    fireEvent.click(btn);

    // After re-run: S4 chip appears and ELINS was called twice.
    await waitFor(() => {
      expect(mockElins).toHaveBeenCalledTimes(2);
      const attractorSection = screen.getByTestId("section-attractor");
      expect(attractorSection).toHaveTextContent("S4");
    });
  });
});
