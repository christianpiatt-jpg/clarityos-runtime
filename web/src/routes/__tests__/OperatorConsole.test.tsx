// Card 40 — OperatorConsole smoke test.
//
// Renders the operator console, pastes a minimal valid multi-run
// context JSON, clicks Load, and asserts the four diagnostic panes
// populate with non-empty JSON content.
//
// Not a logic test — Cards 28-37 already pin every helper's
// behaviour. This just verifies the route wires the textarea + Load
// button to the Card 39 EngineV1OperatorAPI correctly.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import OperatorConsole from "../OperatorConsole";

// Minimal valid two-run multi-run context, shaped per Card 28
// EngineV1OperatorContext + Card 29 EngineV1MultiRunContext. Hand-
// constructed (no fetch) so the smoke test stays fully offline.
const STUB_CONTEXT = {
  runs: [
    {
      primitives:     [],
      projectionDays: 7,
      raw: {
        ok: true,
        primitives:  [
          {
            metadata: {
              primitive_id:   "p1",
              primitive_type: "signal",
              timestamp:      "2026-05-28T00:00:00+00:00",
              version:        "1.0.0",
              domain:         "general",
              source:         "Card 40 smoke fixture",
              parent_id:      null,
              ancestors:      [],
              depends_on:     [],
              influences:     [],
              confidence:     1.0,
              completeness:   1.0,
              reliability:    1.0,
            },
            content:           { note: "p1" },
            hydraulic_state:   {
              pressure: 5, gradient: 0, flow: 4, resistance: 2,
              timestamp: "2026-05-28T00:00:00+00:00",
            },
            origin_state:      null,
            historical_states: [],
          },
        ],
        overlays: [
          {
            primitive_id:     "p1",
            reynolds_number:  1000,
            flow_regime:      "laminar",
            stability:        0.9,
            in_critical_zone: false,
            distance_to_fold: 3.0,
            resilience:       4.0,
            curve_position:   2.0,
            on_upper_branch:  false,
            sensitivity:      1.0,
            hysteresis:       3.0,
          },
        ],
        regression:  null,
        projection:  null,
        diagnostics: {
          observation_id:    "obs_40_001",
          observer_notes:    "Card 40 fixture",
          confidence_level:  0.7,
          validation_status: "unvalidated",
          early_warnings:    {},
          errors:            [],
          interventions:     [],
        },
      },
      normalized: {
        primitives: [
          {
            metadata: {
              primitive_id:   "p1",
              primitive_type: "signal",
              timestamp:      "2026-05-28T00:00:00+00:00",
              version:        "1.0.0",
              domain:         "general",
              source:         "Card 40 smoke fixture",
              parent_id:      null,
              ancestors:      [],
              depends_on:     [],
              influences:     [],
              confidence:     1.0,
              completeness:   1.0,
              reliability:    1.0,
            },
            content:           { note: "p1" },
            hydraulic_state:   {
              pressure: 5, gradient: 0, flow: 4, resistance: 2,
              timestamp: "2026-05-28T00:00:00+00:00",
            },
            origin_state:      null,
            historical_states: [],
          },
        ],
        overlays: [
          {
            primitive_id:     "p1",
            reynolds_number:  1000,
            flow_regime:      "laminar",
            stability:        0.9,
            in_critical_zone: false,
            distance_to_fold: 3.0,
            resilience:       4.0,
            curve_position:   2.0,
            on_upper_branch:  false,
            sensitivity:      1.0,
            hysteresis:       3.0,
          },
        ],
        regression: null,
        projection: null,
        diagnostics: {
          observation_id:    "obs_40_001",
          observer_notes:    "Card 40 fixture",
          confidence_level:  0.7,
          validation_status: "unvalidated",
          early_warnings:    {},
          errors:            [],
          interventions:     [],
        },
        primitiveCount: 1,
        overlayCount:   1,
      },
      classified: {
        signals: [], entities: [], attitudes: [], relationships: [], events: [], temperatures: [],
        laminarOverlays: [], transitionalOverlays: [], turbulentOverlays: [],
        criticalZoneOverlays: [], upperBranchOverlays: [],
        regression: null, projection: null,
        diagnostics: {
          observation_id:    "obs_40_001",
          observer_notes:    "Card 40 fixture",
          confidence_level:  0.7,
          validation_status: "unvalidated",
          early_warnings:    {},
          errors:            [],
          interventions:     [],
        },
      },
    },
    // Second run — same shape, p1 still present with same hydraulic
    // state. Two runs is the minimum for the regression diff section
    // to render against fromIndex=0, toIndex=1.
    {
      primitives:     [],
      projectionDays: 7,
      raw: {
        ok: true,
        primitives:  [
          {
            metadata: {
              primitive_id:   "p1",
              primitive_type: "signal",
              timestamp:      "2026-05-28T00:00:00+00:00",
              version:        "1.0.0",
              domain:         "general",
              source:         "Card 40 smoke fixture",
              parent_id:      null,
              ancestors:      [],
              depends_on:     [],
              influences:     [],
              confidence:     1.0,
              completeness:   1.0,
              reliability:    1.0,
            },
            content:           { note: "p1" },
            hydraulic_state:   {
              pressure: 5, gradient: 0, flow: 4, resistance: 2,
              timestamp: "2026-05-28T00:00:00+00:00",
            },
            origin_state:      null,
            historical_states: [],
          },
        ],
        overlays: [
          {
            primitive_id:     "p1",
            reynolds_number:  1000,
            flow_regime:      "laminar",
            stability:        0.9,
            in_critical_zone: false,
            distance_to_fold: 3.0,
            resilience:       4.0,
            curve_position:   2.0,
            on_upper_branch:  false,
            sensitivity:      1.0,
            hysteresis:       3.0,
          },
        ],
        regression:  null,
        projection:  null,
        diagnostics: {
          observation_id:    "obs_40_002",
          observer_notes:    "Card 40 fixture run 2",
          confidence_level:  0.7,
          validation_status: "unvalidated",
          early_warnings:    {},
          errors:            [],
          interventions:     [],
        },
      },
      normalized: {
        primitives: [
          {
            metadata: {
              primitive_id:   "p1",
              primitive_type: "signal",
              timestamp:      "2026-05-28T00:00:00+00:00",
              version:        "1.0.0",
              domain:         "general",
              source:         "Card 40 smoke fixture",
              parent_id:      null,
              ancestors:      [],
              depends_on:     [],
              influences:     [],
              confidence:     1.0,
              completeness:   1.0,
              reliability:    1.0,
            },
            content:           { note: "p1" },
            hydraulic_state:   {
              pressure: 5, gradient: 0, flow: 4, resistance: 2,
              timestamp: "2026-05-28T00:00:00+00:00",
            },
            origin_state:      null,
            historical_states: [],
          },
        ],
        overlays: [
          {
            primitive_id:     "p1",
            reynolds_number:  1000,
            flow_regime:      "laminar",
            stability:        0.9,
            in_critical_zone: false,
            distance_to_fold: 3.0,
            resilience:       4.0,
            curve_position:   2.0,
            on_upper_branch:  false,
            sensitivity:      1.0,
            hysteresis:       3.0,
          },
        ],
        regression: null,
        projection: null,
        diagnostics: {
          observation_id:    "obs_40_002",
          observer_notes:    "Card 40 fixture run 2",
          confidence_level:  0.7,
          validation_status: "unvalidated",
          early_warnings:    {},
          errors:            [],
          interventions:     [],
        },
        primitiveCount: 1,
        overlayCount:   1,
      },
      classified: {
        signals: [], entities: [], attitudes: [], relationships: [], events: [], temperatures: [],
        laminarOverlays: [], transitionalOverlays: [], turbulentOverlays: [],
        criticalZoneOverlays: [], upperBranchOverlays: [],
        regression: null, projection: null,
        diagnostics: {
          observation_id:    "obs_40_002",
          observer_notes:    "Card 40 fixture run 2",
          confidence_level:  0.7,
          validation_status: "unvalidated",
          early_warnings:    {},
          errors:            [],
          interventions:     [],
        },
      },
    },
  ],
};

function renderConsole() {
  return render(
    <MemoryRouter>
      <OperatorConsole />
    </MemoryRouter>,
  );
}

// OperatorConsole now fetches GET /operator/telemetry on mount (Phase 7
// tile). Stub fetch for every test so the suite stays network-free; the
// Phase 7 test overrides this with a populated payload.
beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({ history: [], latest: null }),
    })),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Card 40 — OperatorConsole smoke test", () => {
  it("renders the page chrome and all 4 diagnostic sections", () => {
    renderConsole();
    expect(screen.getByText("Operator Console")).toBeInTheDocument();
    expect(screen.getByTestId("oc-input")).toBeInTheDocument();
    expect(screen.getByTestId("oc-load")).toBeInTheDocument();
    expect(screen.getByTestId("oc-lineage-map")).toBeInTheDocument();
    expect(screen.getByTestId("oc-hydraulic-evolution")).toBeInTheDocument();
    expect(screen.getByTestId("oc-system-overlay")).toBeInTheDocument();
    expect(screen.getByTestId("oc-regression")).toBeInTheDocument();
  });

  it("Phase 7 — renders the Operator Continuity tile from /operator/telemetry", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          history: [{}, {}, {}],
          latest: { drift: 0.42, coherence_health: 0.88, trust_band: "HIGH" },
        }),
      })),
    );

    renderConsole();

    const tile = screen.getByTestId("oc-operator-continuity");
    expect(tile.textContent).toContain("Operator Continuity (Phase 7)");
    // Values arrive after the mount fetch resolves.
    await waitFor(() => expect(tile.textContent).toContain("Trust Band: HIGH"));
    expect(tile.textContent).toContain("Drift: 0.42");
    expect(tile.textContent).toContain("Coherence Health: 0.88");
    expect(tile.textContent).toContain("History Count: 3");
  });

  it("Phase 7.5 — renders the Operator Forecast tile from /operator/telemetry analytics", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          history: [{}, {}],
          latest: { drift: 0.2, coherence_health: 0.8, trust_band: "HIGH" },
          analytics: {
            drift_velocity: 0.12,
            drift_acceleration: -0.05,
            coherence_trend: 0.3,
            stability_forecast: 0.66,
            trajectory: "Recovering",
          },
        }),
      })),
    );

    renderConsole();

    const tile = screen.getByTestId("oc-operator-forecast");
    expect(tile.textContent).toContain("Operator Forecast (Phase 7 Analytics)");
    // Values arrive after the mount fetch resolves.
    await waitFor(() => expect(tile.textContent).toContain("Trajectory: Recovering"));
    expect(tile.textContent).toContain("Drift Velocity: 0.12");
    expect(tile.textContent).toContain("Drift Acceleration: -0.05");
    expect(tile.textContent).toContain("Coherence Trend: 0.30");
    expect(tile.textContent).toContain("Stability Forecast: 0.66");
  });

  it("Phase 7.6 — renders the Operator Stability Alerts tile from /operator/telemetry", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          history: [{}, {}],
          latest: { drift: 0.9, coherence_health: 0.1, trust_band: "LOW" },
          analytics: {
            drift_velocity: 0.5, drift_acceleration: 0.0, coherence_trend: -0.5,
            stability_forecast: 0.2, trajectory: "Diverging",
          },
          alerts: [
            "High drift detected — operator identity destabilizing",
            "Rapid drift — identity moving faster than expected",
          ],
        }),
      })),
    );

    renderConsole();

    const tile = screen.getByTestId("oc-operator-alerts");
    expect(tile.textContent).toContain("Operator Stability Alerts");
    // Alerts arrive after the mount fetch resolves; rendered as "- <alert>" lines.
    await waitFor(() => expect(tile.textContent).toContain("- High drift detected"));
    expect(tile.textContent).toContain("- Rapid drift");
  });

  it("Phase 7.8 — renders the Causal Drift Factors tile with factor rows", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          history: [{}, {}],
          latest: { drift: 0.5, coherence_health: 0.5, trust_band: "MEDIUM" },
          analytics: {
            drift_velocity: 0.3, drift_acceleration: 0.0, coherence_trend: -0.2,
            stability_forecast: 0.45, trajectory: "Recovering",
          },
          alerts: ["Rapid drift — identity moving faster than expected"],
          causal_factors: [
            { action: "aggressive_prune", correlation: 0.62, contribution: 0.41 },
            { action: "rapid_edit", correlation: -0.18, contribution: 0.12 },
          ],
        }),
      })),
    );

    renderConsole();

    const tile = screen.getByTestId("oc-operator-causal");
    expect(tile.textContent).toContain("Causal Drift Factors");
    await waitFor(() =>
      expect(tile.textContent).toContain("aggressive_prune (correlation: 0.62, contribution: 0.41)"),
    );
    expect(tile.textContent).toContain("rapid_edit (correlation: -0.18, contribution: 0.12)");
  });

  it("Phase 7.8 — renders the Causal Drift Factors fallback for the 'none' sentinel", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          history: [],
          latest: null,
          analytics: {
            drift_velocity: 0.0, drift_acceleration: 0.0, coherence_trend: 0.0,
            stability_forecast: 0.0, trajectory: "Stable",
          },
          alerts: ["No alerts — operator trajectory stable"],
          causal_factors: [{ action: "none", correlation: 0.0, contribution: 0.0 }],
        }),
      })),
    );

    renderConsole();

    const tile = screen.getByTestId("oc-operator-causal");
    await waitFor(() =>
      expect(tile.textContent).toContain("No significant contributing actions detected"),
    );
    // Fallback shows the message, not a factor row.
    expect(tile.textContent).not.toContain("correlation:");
  });

  it("Phase 7.10 — renders the Causal Narrative tile preserving line breaks", async () => {
    const narrative =
      "Identity Movement Summary:\n- Drift velocity: 0.30\n\nOverall Interpretation:\n" +
      "Identity movement is stabilizing. Contributing actions appear to support recovery.";
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          history: [{}],
          latest: { drift: 0.3, coherence_health: 0.7, trust_band: "HIGH" },
          analytics: {
            drift_velocity: 0.3, drift_acceleration: 0.0, coherence_trend: 0.2,
            stability_forecast: 0.6, trajectory: "Recovering",
          },
          alerts: ["No alerts — operator trajectory stable"],
          causal_factors: [{ action: "none", correlation: 0.0, contribution: 0.0 }],
          narrative,
        }),
      })),
    );

    renderConsole();

    const tile = screen.getByTestId("oc-operator-narrative");
    expect(tile.textContent).toContain("Causal Narrative");
    await waitFor(() => expect(tile.textContent).toContain("Identity Movement Summary:"));
    // The <pre> renders the narrative verbatim, line breaks preserved.
    expect(tile.textContent).toContain(narrative);
    const pre = tile.querySelector("pre");
    expect(pre).not.toBeNull();
    expect(pre?.textContent).toContain("Overall Interpretation:");
  });

  it("Phase 8.5 — renders the Causal Chains tile with chains, scores, and motif flags", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          history: [{}, {}],
          latest: { drift: 0.6, coherence_health: 0.3, trust_band: "LOW" },
          causal_chains: [
            {
              nodes: [
                { id: "drift_velocity", type: "drift", label: "Drift velocity: 0.60", timestamp: null, value: 0.6 },
                { id: "factor_0", type: "action", label: "prune (contribution: 0.50)", timestamp: null, value: 0.5 },
                { id: "narrative", type: "narrative", label: "Causal Narrative", timestamp: null, value: null },
              ],
              edges: [
                { source: "drift_velocity", target: "factor_0", weight: 0.5 },
                { source: "factor_0", target: "narrative", weight: 0.5 },
              ],
              score: 0.78,
              motifs: { passes_bottleneck: true, passes_attractor: false, in_feedback_loop: false },
            },
            {
              nodes: [
                { id: "drift_velocity", type: "drift", label: "Drift velocity: 0.60", timestamp: null, value: 0.6 },
                { id: "narrative", type: "narrative", label: "Causal Narrative", timestamp: null, value: null },
              ],
              edges: [{ source: "drift_velocity", target: "narrative", weight: 0.3 }],
              score: 0.55,
              motifs: { passes_bottleneck: false, passes_attractor: true, in_feedback_loop: false },
            },
          ],
        }),
      })),
    );

    renderConsole();

    const tile = screen.getByTestId("oc-operator-causal-chains");
    expect(tile.textContent).toContain("Causal Chains");
    // Chains arrive after the mount fetch resolves.
    await waitFor(() => expect(tile.textContent).toContain("Chain 1"));
    expect(tile.textContent).toContain("score 0.78");
    expect(tile.textContent).toContain("Chain 2");
    expect(tile.textContent).toContain("score 0.55");
    // Node labels render under each chain.
    expect(tile.textContent).toContain("Drift velocity: 0.60");
    expect(tile.textContent).toContain("prune (contribution: 0.50)");
    expect(tile.textContent).toContain("Causal Narrative");
    // Per-chain motif flags render as yes/no.
    expect(tile.textContent).toContain("bottleneck=yes");
    expect(tile.textContent).toContain("attractor=yes"); // from chain 2
    expect(tile.textContent).toContain("loop=no");
  });

  it("Phase 8.5 — renders the Structural Motifs tile with loops, bottlenecks, attractors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          history: [{}],
          causal_motifs: {
            feedback_loops: [["a", "b"], ["x", "y", "z"]],
            bottlenecks: ["drift_velocity"],
            attractors: ["narrative"],
          },
        }),
      })),
    );

    renderConsole();

    const tile = screen.getByTestId("oc-operator-motifs");
    expect(tile.textContent).toContain("Structural Motifs");
    expect(tile.textContent).toContain("Feedback Loops");
    expect(tile.textContent).toContain("Bottlenecks");
    expect(tile.textContent).toContain("Attractors");
    // Loops render as " → "-joined node sequences.
    await waitFor(() => expect(tile.textContent).toContain("a → b"));
    expect(tile.textContent).toContain("x → y → z");
    expect(tile.textContent).toContain("drift_velocity");
    expect(tile.textContent).toContain("narrative");
  });

  it("Phase 8.5 — renders fallbacks when chains + motifs are empty", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          history: [],
          causal_chains: [],
          causal_motifs: { feedback_loops: [], bottlenecks: [], attractors: [] },
        }),
      })),
    );

    renderConsole();

    const chainsTile = screen.getByTestId("oc-operator-causal-chains");
    const motifsTile = screen.getByTestId("oc-operator-motifs");
    await waitFor(() => expect(chainsTile.textContent).toContain("No causal chains detected"));
    // Each of the three motif categories shows its empty sentinel.
    expect((motifsTile.textContent?.match(/None/g) ?? []).length).toBe(3);
  });

  it("Phase 8.8 — renders the Causal Stability tile with score, trend, and drivers", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          history: [{}, {}],
          causal_stability: {
            stability_score: 0.75,
            trend: "destabilizing",
            drivers: {
              rising_influence: ["alert_0", "drift_velocity"],
              falling_influence: ["stability_forecast"],
              new_bottlenecks: ["drift_velocity"],
              resolved_bottlenecks: [],
              new_loops: [["a", "b"]],
              resolved_loops: [],
              chain_strengthening: [["drift_velocity", "narrative"]],
              chain_weakening: [],
            },
          },
        }),
      })),
    );

    renderConsole();

    const tile = screen.getByTestId("oc-operator-causal-stability");
    expect(tile.textContent).toContain("Causal Stability");
    await waitFor(() => expect(tile.textContent).toContain("Stability Score: 0.75"));
    expect(tile.textContent).toContain("Trend: destabilizing");
    // Driver sub-headers.
    expect(tile.textContent).toContain("Rising Influence");
    expect(tile.textContent).toContain("Chain Weakening");
    // Driver values: node ids, loop sequences, and chain signatures.
    expect(tile.textContent).toContain("stability_forecast");   // falling influence
    expect(tile.textContent).toContain("a → b");                // new loop
    expect(tile.textContent).toContain("drift_velocity → narrative"); // chain strengthening
    // Empty driver sections (resolved_bottlenecks / resolved_loops / chain_weakening)
    // each render "None".
    expect((tile.textContent?.match(/None/g) ?? []).length).toBeGreaterThanOrEqual(3);
  });

  it("Phase 8.8 — Causal Stability drivers all render 'None' when empty", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          history: [{}],
          causal_stability: {
            stability_score: 0.91,
            trend: "steady",
            drivers: {
              rising_influence: [],
              falling_influence: [],
              new_bottlenecks: [],
              resolved_bottlenecks: [],
              new_loops: [],
              resolved_loops: [],
              chain_strengthening: [],
              chain_weakening: [],
            },
          },
        }),
      })),
    );

    renderConsole();

    const tile = screen.getByTestId("oc-operator-causal-stability");
    await waitFor(() => expect(tile.textContent).toContain("Stability Score: 0.91"));
    expect(tile.textContent).toContain("Trend: steady");
    // All eight driver sub-sections show "None".
    expect((tile.textContent?.match(/None/g) ?? []).length).toBe(8);
  });

  it("Phase 8.11 — renders the Unified Narrative tile inside a <pre> block", async () => {
    const unified =
      "Unified Temporal–Causal Narrative\n\nTemporal Summary:\nIdentity drifting.\n\n" +
      "Causal Summary:\nPrimary Causal Chain:\n- drift_velocity → narrative\n\n" +
      "Overall Assessment:\nDestabilizing";
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({ history: [{}], unified_narrative: unified }),
      })),
    );

    renderConsole();

    const tile = screen.getByTestId("oc-operator-unified-narrative");
    expect(tile.textContent).toContain("Unified Narrative");
    await waitFor(() => expect(tile.textContent).toContain("Unified Temporal–Causal Narrative"));
    // Full narrative rendered verbatim inside a <pre> (line breaks preserved).
    const pre = tile.querySelector("pre");
    expect(pre).not.toBeNull();
    expect(pre?.textContent).toContain("Overall Assessment:");
    expect(pre?.textContent).toContain(unified);
  });

  it("Phase 8.11 — Unified Narrative tile still renders an empty <pre> for empty narrative", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({ history: [], unified_narrative: "" }),
      })),
    );

    renderConsole();

    const tile = screen.getByTestId("oc-operator-unified-narrative");
    expect(tile.textContent).toContain("Unified Narrative");   // heading still shows
    const pre = tile.querySelector("pre");
    expect(pre).not.toBeNull();
    expect(pre?.textContent).toBe("");
  });

  it("Phase 9.5 — renders the Behavioral Motifs tile with all five sections (backend shape)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          history: [{}],
          behavioral_motifs: {
            action_loops: [["open_settings", "adjust_param"], ["a", "b", "c"]],
            trigger_chains: [["open_settings", "factor_load", "adjust_param"]],
            habits: ["daily_review", "morning_sync"],
            action_bottlenecks: ["bottleneck_node"],
            action_attractors: ["attractor_node"],
          },
        }),
      })),
    );

    renderConsole();

    const tile = screen.getByTestId("oc-operator-behavioral-motifs");
    expect(tile.textContent).toContain("Behavioral Motifs");

    // All five section headers (one per backend behavioral_motifs key) render.
    const loops = await screen.findByTestId("oc-behavioral-loops");
    expect(tile.textContent).toContain("Action Loops");
    expect(tile.textContent).toContain("Trigger Chains");
    expect(tile.textContent).toContain("Habits");
    expect(tile.textContent).toContain("Action Bottlenecks");
    expect(tile.textContent).toContain("Action Attractors");

    // action_loops + trigger_chains render as " → "-joined sequences.
    expect(loops.textContent).toContain("open_settings → adjust_param");
    expect(loops.textContent).toContain("a → b → c");
    expect(screen.getByTestId("oc-behavioral-triggers").textContent).toContain(
      "open_settings → factor_load → adjust_param",
    );
    // Label families (habits / bottlenecks / attractors) render verbatim.
    expect(screen.getByTestId("oc-behavioral-habits").textContent).toContain("daily_review");
    expect(screen.getByTestId("oc-behavioral-habits").textContent).toContain("morning_sync");
    expect(screen.getByTestId("oc-behavioral-bottlenecks").textContent).toContain("bottleneck_node");
    expect(screen.getByTestId("oc-behavioral-attractors").textContent).toContain("attractor_node");
  });

  it("Phase 9.5 — empty behavioral sections collapse while populated ones render", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          history: [{}],
          behavioral_motifs: {
            action_loops: [],
            trigger_chains: [],
            habits: ["daily_review"],
            action_bottlenecks: [],
            action_attractors: [],
          },
        }),
      })),
    );

    renderConsole();

    // The single populated family renders…
    const habits = await screen.findByTestId("oc-behavioral-habits");
    expect(habits.textContent).toContain("daily_review");
    // …and the four empty families collapse entirely — no header, no list.
    const tile = screen.getByTestId("oc-operator-behavioral-motifs");
    expect(tile.textContent).toContain("Habits");
    expect(tile.textContent).not.toContain("Action Loops");
    expect(tile.textContent).not.toContain("Trigger Chains");
    expect(tile.textContent).not.toContain("Action Bottlenecks");
    expect(tile.textContent).not.toContain("Action Attractors");
    expect(screen.queryByTestId("oc-behavioral-loops")).toBeNull();
    expect(screen.queryByTestId("oc-behavioral-triggers")).toBeNull();
    expect(screen.queryByTestId("oc-behavioral-bottlenecks")).toBeNull();
    expect(screen.queryByTestId("oc-behavioral-attractors")).toBeNull();
  });

  it("Phase 9.5 — all-empty behavioral motifs render only the tile heading", () => {
    // The default beforeEach stub returns { history: [], latest: null } with no
    // behavioral_motifs key, so the tile falls back to the empty set and every
    // section collapses.
    renderConsole();
    const tile = screen.getByTestId("oc-operator-behavioral-motifs");
    expect(tile.textContent).toContain("Behavioral Motifs");
    expect(tile.querySelectorAll("ul").length).toBe(0);
    expect(tile.querySelectorAll("h3").length).toBe(0);
  });

  it("Phase 9.5 — renders behavioral motifs in backend array order (no client re-sort)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          history: [{}],
          behavioral_motifs: {
            action_loops: [],
            trigger_chains: [],
            // Deliberately NOT alphabetical — the component must preserve the
            // backend's deterministic ordering verbatim.
            habits: ["zebra_action", "alpha_action", "mid_action"],
            action_bottlenecks: [],
            action_attractors: [],
          },
        }),
      })),
    );

    renderConsole();

    const habits = await screen.findByTestId("oc-behavioral-habits");
    const rows = Array.from(habits.querySelectorAll("li")).map((li) => li.textContent);
    expect(rows).toEqual(["zebra_action", "alpha_action", "mid_action"]);
  });

  // Phase 10.4 (Card 10.4) — Behavioral Forecast tile. Read-only surfacing of the
  // 10.0-10.3 outputs via telemetry.behavioral_forecast (forecast / stability /
  // narrative). The shape mirrors the phase10 function outputs exactly.
  const BF_FULL = {
    forecast: {
      next_actions: [
        { action_id: "e2", label: "edit", score: 0.9, drivers: ["loop", "habit"] },
        { action_id: "p0", label: "prune", score: 0.4, drivers: ["trigger"] },
      ],
      loop_continuation: [
        { loop: ["edit", "prune"], continuation_probability: 0.95 },
        { loop: ["a", "b"], continuation_probability: 0.6 },
        { loop: ["c", "d"], continuation_probability: 0.5 },
        { loop: ["e", "f"], continuation_probability: 0.4 },   // 4th → dropped (top 3)
      ],
    },
    stability: {
      score: 0.62,
      drivers: { habit_stability: 0.8, trigger_stability: 0.5, loop_persistence: 0.4, action_variance: 0.7 },
    },
    narrative: {
      summary: "Behavioral patterns show moderate change. Detected 2 habit changes, 1 trigger change, and 2 loops.",
      habit_changes: [
        { action_id: "edit", trend: "strengthening", delta: 0.8 },
        { action_id: "prune", trend: "weakening", delta: -0.3 },
      ],
      trigger_changes: [
        { chain: ["a", "f", "b"], delta: 0.9 },
        { chain: ["c", "f", "d"], delta: 0.5 },
        { chain: ["e", "f", "g"], delta: 0.2 },
        { chain: ["h", "f", "i"], delta: 0.1 },   // 4th → dropped (top 3)
      ],
      forecast_highlights: [
        { action_id: "e2", score: 0.9, drivers: ["loop", "habit"] },
        { action_id: "p0", score: 0.4, drivers: ["trigger"] },
      ],
    },
  };

  it("Phase 10.4 — renders the Behavioral Forecast tile with all six sections (backend shape)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: true, json: async () => ({ history: [{}], behavioral_forecast: BF_FULL }) })),
    );

    renderConsole();

    const tile = screen.getByTestId("oc-operator-behavioral-forecast");
    expect(tile.textContent).toContain("Behavioral Forecast");

    const na = await screen.findByTestId("oc-bf-next-actions");
    expect(na.textContent).toContain("edit — score 0.90 (loop, habit)");    // A: label + score + drivers
    expect(na.textContent).toContain("prune — score 0.40 (trigger)");
    expect(screen.getByTestId("oc-bf-habits").textContent).toContain("edit — strengthening (Δ 0.80)");  // B
    expect(screen.getByTestId("oc-bf-triggers").textContent).toContain("a → f → b (Δ 0.90)");           // C
    expect(screen.getByTestId("oc-bf-loops").textContent).toContain("edit → prune (0.95)");             // D
    const stab = screen.getByTestId("oc-bf-stability");
    expect(stab.textContent).toContain("Score: 0.62");                                                  // E
    expect(stab.textContent).toContain("Habit stability: 0.80");
    expect(stab.textContent).toContain("Action variance: 0.70");
    expect(screen.getByTestId("oc-bf-narrative").textContent).toContain("moderate change");             // F
    // All six section headers render.
    for (const heading of ["Next Likely Actions", "Habit Trajectory", "Trigger Likelihood",
                           "Loop Continuation", "Stability", "Narrative"]) {
      expect(tile.textContent).toContain(heading);
    }
  });

  it("Phase 10.4 — caps triggers/loops at 3 and renders in backend array order", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: true, json: async () => ({ history: [{}], behavioral_forecast: BF_FULL }) })),
    );

    renderConsole();

    const triggers = await screen.findByTestId("oc-bf-triggers");
    const triggerRows = Array.from(triggers.querySelectorAll("li")).map((li) => li.textContent);
    expect(triggerRows).toEqual([
      "a → f → b (Δ 0.90)", "c → f → d (Δ 0.50)", "e → f → g (Δ 0.20)",     // 4th dropped, in order
    ]);
    const loopRows = Array.from(screen.getByTestId("oc-bf-loops").querySelectorAll("li")).map((li) => li.textContent);
    expect(loopRows).toEqual([
      "edit → prune (0.95)", "a → b (0.60)", "c → d (0.50)",                 // 4th dropped, in order
    ]);
  });

  it("Phase 10.4 — empty sections collapse while populated ones render", async () => {
    const partial = {
      forecast: { next_actions: [], loop_continuation: [] },
      narrative: {
        summary: "",
        habit_changes: [{ action_id: "edit", trend: "stable", delta: 0.0 }],
        trigger_changes: [],
        forecast_highlights: [],
      },
      // stability omitted → that section collapses too.
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: true, json: async () => ({ history: [{}], behavioral_forecast: partial }) })),
    );

    renderConsole();

    const habits = await screen.findByTestId("oc-bf-habits");
    expect(habits.textContent).toContain("edit — stable");
    // The five empty sections collapse entirely.
    expect(screen.queryByTestId("oc-bf-next-actions")).toBeNull();
    expect(screen.queryByTestId("oc-bf-triggers")).toBeNull();
    expect(screen.queryByTestId("oc-bf-loops")).toBeNull();
    expect(screen.queryByTestId("oc-bf-stability")).toBeNull();
    expect(screen.queryByTestId("oc-bf-narrative")).toBeNull();   // empty summary + no highlights
    const tile = screen.getByTestId("oc-operator-behavioral-forecast");
    expect(tile.textContent).toContain("Behavioral Forecast");    // heading still shows
    expect(tile.textContent).not.toContain("Next Likely Actions");
  });

  it("Phase 10.4 — renders only the tile heading when behavioral_forecast is absent", () => {
    // The default beforeEach stub returns { history: [], latest: null } with no
    // behavioral_forecast key → every section collapses.
    renderConsole();
    const tile = screen.getByTestId("oc-operator-behavioral-forecast");
    expect(tile.textContent).toContain("Behavioral Forecast");
    expect(tile.querySelectorAll("h3").length).toBe(0);
    expect(tile.querySelectorAll("ul").length).toBe(0);
  });

  // Phase 11.2 (Card 11.2) — Recommendations tile. Read-only surfacing of the
  // 11.0 recommendations + 11.1 narrative via telemetry.recommendation_narrative
  // (which embeds the drivers + stability context).
  const RN_FULL = {
    summary: "Behavioral system shows moderate variability; recommendations address key leverage points. "
      + "Generated 3 recommendations across 3 reason types. "
      + "Top recommendation: edit — forecast_alignment (score 0.90).",
    recommendations: [
      { action_id: "edit", label: "edit", reason: "forecast_alignment", score: 0.9,
        explanation: "This action is predicted as likely in the near future." },
      { action_id: "b1", label: "b1", reason: "bottleneck_relief", score: 0.8,
        explanation: "This action is recommended because it is a bottleneck with high inbound influence." },
      { action_id: "prune", label: "prune", reason: "habit_weakening", score: 0.5,
        explanation: "This action is recommended because its habit strength is decreasing." },
    ],
    drivers: {
      habit: [{ action_id: "prune", metric: 0.5, reason: "habit_weakening" }],
      triggers: [],
      loops: [],
      bottlenecks: [{ action_id: "b1", metric: 0.8, reason: "bottleneck_relief" }],
      attractors: [],
      forecast_alignment: [{ action_id: "edit", metric: 0.9, reason: "forecast_alignment" }],
    },
    stability_context: {
      score: 0.55,
      drivers: { habit_stability: 0.7, trigger_stability: 0.6, loop_persistence: 0.4, action_variance: 0.5 },
    },
  };

  it("Phase 11.2 — renders the Recommendations tile with all four sections (backend shape)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: true, json: async () => ({ history: [{}], recommendation_narrative: RN_FULL }) })),
    );

    renderConsole();

    const tile = screen.getByTestId("oc-operator-recommendations");
    expect(tile.textContent).toContain("Recommendations");

    const top = await screen.findByTestId("oc-rec-top");            // A
    expect(top.textContent).toContain("edit — forecast_alignment (score 0.90)");
    expect(top.textContent).toContain("prune — habit_weakening (score 0.50)");
    // B: non-empty driver buckets render; empty ones collapse.
    expect(screen.getByTestId("oc-rec-driver-habit").textContent).toContain("prune — habit_weakening (0.50)");
    expect(screen.getByTestId("oc-rec-driver-bottlenecks").textContent).toContain("b1 — bottleneck_relief (0.80)");
    expect(screen.getByTestId("oc-rec-driver-forecast_alignment").textContent).toContain("edit — forecast_alignment (0.90)");
    expect(screen.queryByTestId("oc-rec-driver-triggers")).toBeNull();
    expect(screen.queryByTestId("oc-rec-driver-loops")).toBeNull();
    expect(screen.queryByTestId("oc-rec-driver-attractors")).toBeNull();
    const stab = screen.getByTestId("oc-rec-stability");            // C
    expect(stab.textContent).toContain("Score: 0.55");
    expect(stab.textContent).toContain("Habit stability: 0.70");
    const narr = screen.getByTestId("oc-rec-narrative");            // D
    expect(narr.textContent).toContain("moderate variability");
    expect(narr.textContent).toContain("edit — This action is predicted as likely in the near future.");
  });

  it("Phase 11.2 — renders recommendations and driver buckets in deterministic order", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: true, json: async () => ({ history: [{}], recommendation_narrative: RN_FULL }) })),
    );

    renderConsole();

    const top = await screen.findByTestId("oc-rec-top");
    const rows = Array.from(top.querySelectorAll("li")).map((li) => li.textContent);
    expect(rows).toEqual([
      "edit — forecast_alignment (score 0.90)",
      "b1 — bottleneck_relief (score 0.80)",
      "prune — habit_weakening (score 0.50)",
    ]);
    // Driver sub-sections render in the fixed bucket order (empty buckets skipped).
    const headings = Array.from(screen.getByTestId("oc-rec-drivers").querySelectorAll("h4")).map((h) => h.textContent);
    expect(headings).toEqual(["Habit", "Bottlenecks", "Forecast Alignment"]);
  });

  it("Phase 11.2 — empty sections collapse while populated ones render", async () => {
    const partial = {
      summary: "",
      recommendations: [
        { action_id: "edit", label: "edit", reason: "forecast_alignment", score: 0.9, explanation: "exp" },
      ],
      drivers: { habit: [], triggers: [], loops: [], bottlenecks: [], attractors: [], forecast_alignment: [] },
      // stability_context omitted → that section collapses.
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: true, json: async () => ({ history: [{}], recommendation_narrative: partial }) })),
    );

    renderConsole();

    const top = await screen.findByTestId("oc-rec-top");
    expect(top.textContent).toContain("edit — forecast_alignment (score 0.90)");
    expect(screen.queryByTestId("oc-rec-drivers")).toBeNull();      // all buckets empty
    expect(screen.queryByTestId("oc-rec-stability")).toBeNull();    // stability absent
    // D still renders (the rec's explanation is present even though summary is empty).
    expect(screen.getByTestId("oc-rec-narrative").textContent).toContain("edit — exp");
  });

  it("Phase 11.2 — renders only the tile heading when recommendation_narrative is absent", () => {
    renderConsole();    // default stub has no recommendation_narrative
    const tile = screen.getByTestId("oc-operator-recommendations");
    expect(tile.textContent).toContain("Recommendations");
    expect(tile.querySelectorAll("h3").length).toBe(0);
    expect(tile.querySelectorAll("ul").length).toBe(0);
  });

  it("shows '(no context loaded)' placeholders before Load is clicked", () => {
    renderConsole();
    expect(screen.getByTestId("oc-lineage-map").textContent).toContain("(no context loaded)");
    expect(screen.getByTestId("oc-hydraulic-evolution").textContent).toContain("(no context loaded)");
    expect(screen.getByTestId("oc-system-overlay").textContent).toContain("(no context loaded)");
  });

  it("loads a valid multi-run context and populates all 4 panes", () => {
    renderConsole();

    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    // No parse error.
    expect(screen.queryByTestId("oc-error")).toBeNull();

    // Each pane now contains real JSON (Card 39 helpers ran).
    const lineageText = screen.getByTestId("oc-lineage-map").textContent ?? "";
    expect(lineageText).toContain('"primitive_ids"');
    expect(lineageText).toContain('"p1"');

    const hydraulicText = screen.getByTestId("oc-hydraulic-evolution").textContent ?? "";
    expect(hydraulicText).toContain('"perPrimitive"');
    expect(hydraulicText).toContain('"perRun"');

    const overlayText = screen.getByTestId("oc-system-overlay").textContent ?? "";
    expect(overlayText).toContain('"lineageMap"');
    expect(overlayText).toContain('"hydraulicEvolution"');

    const regressionText = screen.getByTestId("oc-regression").textContent ?? "";
    expect(regressionText).toContain('"fromIndex": 0');
    expect(regressionText).toContain('"toIndex": 1');
    expect(regressionText).toContain('"primitiveChanges"');
    expect(regressionText).toContain('"hydraulic"');
  });

  it("surfaces a parse error for invalid JSON without crashing", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "not json {" } });
    fireEvent.click(screen.getByTestId("oc-load"));
    expect(screen.getByTestId("oc-error").textContent).toContain("JSON parse error");
  });

  it("surfaces a shape error for JSON missing the `runs` array", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: '{ "not_runs": [] }' } });
    fireEvent.click(screen.getByTestId("oc-load"));
    expect(screen.getByTestId("oc-error").textContent).toContain("runs");
  });

  it("Card 41 — renders per-primitive drill-ins and regression diff markers", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    // Per-primitive drill-in node for p1 exists (Card 41 lineage map
    // primitive-level navigation).
    const p1Section = screen.getByTestId("oc-lineage-primitive-p1");
    expect(p1Section).toBeInTheDocument();
    // The full lineage JSON for p1 is reachable through the drill-in.
    expect(p1Section.textContent).toContain('"primitive_id"');
    expect(p1Section.textContent).toContain("p1");

    // Per-run drill-ins for run 0 and run 1 exist (Card 41 hydraulic
    // run-level navigation).
    expect(screen.getByTestId("oc-hydraulic-run-0")).toBeInTheDocument();
    expect(screen.getByTestId("oc-hydraulic-run-1")).toBeInTheDocument();

    // Regression-diff markers list exists. The stub context has p1 in
    // both runs with identical state, so the changed/added/removed
    // lists are all empty — the <ul> renders but has no <li> children.
    const markers = screen.getByTestId("oc-regression-markers");
    expect(markers).toBeInTheDocument();
    expect(markers.querySelectorAll("li").length).toBe(0);
  });

  it("Card 42 — renders semantic summary blocks under each section", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    // All four summary blocks must exist with semantic plain-text output.
    const lineageSummary = screen.getByTestId("oc-lineage-summary");
    expect(lineageSummary.textContent).toContain("Primitive: p1");
    expect(lineageSummary.textContent).toContain("First seen: run 0");
    expect(lineageSummary.textContent).toContain("Total appearances: 2");

    const hydraulicSummary = screen.getByTestId("oc-hydraulic-summary");
    expect(hydraulicSummary.textContent).toContain("Run 0:");
    expect(hydraulicSummary.textContent).toContain("laminar:");

    const overlaySummary = screen.getByTestId("oc-system-overlay-summary");
    expect(overlaySummary.textContent).toContain("System Overlay:");
    expect(overlaySummary.textContent).toContain("total primitives: 1");
    expect(overlaySummary.textContent).toContain("runs: 2");

    const regressionSummary = screen.getByTestId("oc-regression-summary");
    expect(regressionSummary.textContent).toContain("Regression (0 → 1):");
    expect(regressionSummary.textContent).toContain("hydraulic deltas:");
    expect(regressionSummary.textContent).toContain("laminar:");
  });

  it("Card 43 — renders the Evolution Timeline section with run blocks and a transition", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const timeline = screen.getByTestId("oc-evolution-timeline");
    expect(timeline).toBeInTheDocument();
    // Two-run stub → two per-run blocks + one transition block.
    expect(timeline.textContent).toContain("=== Run 0 ===");
    expect(timeline.textContent).toContain("=== Run 1 ===");
    expect(timeline.textContent).toContain("=== Run 0 → Run 1 ===");
    expect(timeline.textContent).toContain("Primitives active: [p1]");
    expect(timeline.textContent).toContain("Hydraulic:");
    expect(timeline.textContent).toContain("Hydraulic deltas:");
  });

  it("Card 44 — renders the Diff Viewer section with its own from/to inputs and a hierarchical diff", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const viewer = screen.getByTestId("oc-diff-viewer");
    expect(viewer).toBeInTheDocument();
    // Independent from/to inputs exist with their own test ids.
    expect(screen.getByTestId("oc-diff-from-index")).toBeInTheDocument();
    expect(screen.getByTestId("oc-diff-to-index")).toBeInTheDocument();
    // The hierarchical diff renders for the default 0→1 selection.
    expect(viewer.textContent).toContain("=== Diff: Run 0 → Run 1 ===");
    expect(viewer.textContent).toContain("[Primitives]");
    expect(viewer.textContent).toContain("[Hydraulic]");
    expect(viewer.textContent).toContain("[Primitive Details]");
    // Stub primitives are identical across runs → no field changes.
    expect(viewer.textContent).toContain("(no per-primitive field changes)");
  });

  it("Card 45 — renders the Structural Diagnostics section with all 5 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const diag = screen.getByTestId("oc-structural-diagnostics");
    expect(diag).toBeInTheDocument();
    // Header + all 5 section labels.
    expect(diag.textContent).toContain("=== Structural Diagnostics ===");
    expect(diag.textContent).toContain("[System Stability]");
    expect(diag.textContent).toContain("[Primitive Churn]");
    expect(diag.textContent).toContain("[Hydraulic Volatility]");
    expect(diag.textContent).toContain("[Structural Anomalies]");
    expect(diag.textContent).toContain("[System-Level Outliers]");
    // Stub primitives are identical across runs → fully stable system.
    expect(diag.textContent).toContain("- stability score: 1.00");
    expect(diag.textContent).toContain("- total primitives: 1");
  });

  it("Card 46 — renders the Structural Overlay (Multi-Run) section with all 4 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const overlaySection = screen.getByTestId("oc-structural-overlay");
    expect(overlaySection).toBeInTheDocument();
    // Header + all 4 section labels.
    expect(overlaySection.textContent).toContain("=== Multi-Run Structural Overlay ===");
    expect(overlaySection.textContent).toContain("[Primitive Structural Evolution]");
    expect(overlaySection.textContent).toContain("[System Structural Map]");
    expect(overlaySection.textContent).toContain("[Cross-Run Structural Deltas]");
    expect(overlaySection.textContent).toContain("[Structural Clusters]");
    // The stub fixture has p1 present in both runs as laminar — should
    // show up in Cluster A.
    expect(overlaySection.textContent).toContain("p1:");
    expect(overlaySection.textContent).toContain("- Cluster A (stable laminar): [p1]");
    expect(overlaySection.textContent).toContain("Run 0 → 1:");
  });

  it("Card 47 — renders the Structural Matrix section with legend + header + p1 row", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const matrix = screen.getByTestId("oc-structural-matrix");
    expect(matrix).toBeInTheDocument();
    expect(matrix.textContent).toContain("=== Structural Matrix ===");
    expect(matrix.textContent).toContain("Legend:");
    expect(matrix.textContent).toContain("L = laminar");
    expect(matrix.textContent).toContain("* = structural change");
    // Header row + p1 data row exist in the matrix body.
    expect(matrix.textContent).toContain("Primitive");
    expect(matrix.textContent).toContain("R0");
    expect(matrix.textContent).toContain("R1");
    expect(matrix.textContent).toContain("p1");
    // Stub fixture has p1 laminar in both runs → cells should show "L".
    expect(matrix.textContent).toMatch(/p1\s+\|\s+L\s+\|\s+L/);
  });

  it("Card 48 — renders the Structural Heatmap section with pressure-symbol legend", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const heatmap = screen.getByTestId("oc-structural-heatmap");
    expect(heatmap).toBeInTheDocument();
    expect(heatmap.textContent).toContain("=== Structural Heatmap ===");
    expect(heatmap.textContent).toContain(". = no structural pressure");
    expect(heatmap.textContent).toContain("# = high pressure");
    // Stub fixture has p1 laminar in both runs → pressure 0 in each
    // cell → "." marker.
    expect(heatmap.textContent).toContain("p1");
    expect(heatmap.textContent).toMatch(/p1\s+\|\s+\.\s+\|\s+\./);
  });

  it("Card 49 — renders the Structural Bands section with all 3 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const bands = screen.getByTestId("oc-structural-bands");
    expect(bands).toBeInTheDocument();
    expect(bands.textContent).toContain("=== Structural Bands ===");
    expect(bands.textContent).toContain("[Run-Level Bands]");
    expect(bands.textContent).toContain("[System-Level Phase Bands]");
    expect(bands.textContent).toContain("[Primitive-Level Band Summary]");
    // Stub has p1 stable laminar in both runs → "--" bands + (no phase
    // transitions) + p1 in stable bucket.
    expect(bands.textContent).toContain("R0: --");
    expect(bands.textContent).toContain("R1: --");
    expect(bands.textContent).toContain("(no phase transitions)");
    expect(bands.textContent).toContain("Stable primitives: [p1]");
  });

  it("Card 50 — renders the Structural Signature section with all 8 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const sig = screen.getByTestId("oc-structural-signature");
    expect(sig).toBeInTheDocument();
    // Header + all 8 section labels.
    expect(sig.textContent).toContain("=== Structural Signature ===");
    expect(sig.textContent).toContain("[Run-Level Structural Fingerprints]");
    expect(sig.textContent).toContain("[System-Level Signature String]");
    expect(sig.textContent).toContain("[Hydraulic Signature]");
    expect(sig.textContent).toContain("[Critical-Zone Signature]");
    expect(sig.textContent).toContain("[Upper-Branch Signature]");
    expect(sig.textContent).toContain("[Volatility Signature]");
    expect(sig.textContent).toContain("[Drift Signature]");
    expect(sig.textContent).toContain("[Phase-Transition Signature]");
    // Stub fixture has p1 laminar in both runs → fingerprints "L--",
    // signature "L-L-", hydraulic "L → L".
    expect(sig.textContent).toContain("R0: L--");
    expect(sig.textContent).toContain("R1: L--");
    expect(sig.textContent).toContain("L-L-");
    expect(sig.textContent).toContain("L → L");
  });

  it("Card 51 — renders the Signature Diff section with its own from/to inputs and the 9 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const diff = screen.getByTestId("oc-signature-diff");
    expect(diff).toBeInTheDocument();
    expect(screen.getByTestId("oc-sig-from-index")).toBeInTheDocument();
    expect(screen.getByTestId("oc-sig-to-index")).toBeInTheDocument();
    expect(diff.textContent).toContain("=== Structural Signature Diff ===");
    expect(diff.textContent).toContain("Run 0 → Run 1");
    expect(diff.textContent).toContain("[Fingerprint Diff]");
    expect(diff.textContent).toContain("[Hydraulic Diff]");
    expect(diff.textContent).toContain("[Pressure Band Diff]");
    expect(diff.textContent).toContain("[Critical-Zone Diff]");
    expect(diff.textContent).toContain("[Upper-Branch Diff]");
    expect(diff.textContent).toContain("[Volatility Diff]");
    expect(diff.textContent).toContain("[Drift Diff]");
    expect(diff.textContent).toContain("[Phase-Transition Diff]");
    expect(diff.textContent).toContain("[Identity Shift Classification]");
    // Stub fixture has identical signatures across runs → no shift.
    expect(diff.textContent).toContain("Type: No significant identity shift");
  });

  it("Card 52 — renders the Signature Overlay section with all 11 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const overlay = screen.getByTestId("oc-signature-overlay");
    expect(overlay).toBeInTheDocument();
    expect(overlay.textContent).toContain("=== Structural Signature Overlay ===");
    expect(overlay.textContent).toContain("[Run-Level Signatures]");
    expect(overlay.textContent).toContain("[Run-Level Signature Diffs]");
    expect(overlay.textContent).toContain("[Hydraulic Overlay]");
    expect(overlay.textContent).toContain("[Pressure Band Overlay]");
    expect(overlay.textContent).toContain("[Critical-Zone Overlay]");
    expect(overlay.textContent).toContain("[Upper-Branch Overlay]");
    expect(overlay.textContent).toContain("[Volatility Overlay]");
    expect(overlay.textContent).toContain("[Drift Overlay]");
    expect(overlay.textContent).toContain("[Phase-Transition Overlay]");
    expect(overlay.textContent).toContain("[Identity-Shift Overlay]");
    expect(overlay.textContent).toContain("[System-Level Structural Synthesis]");
    // Stub has 2 stable laminar runs → R0 + R1 signatures + a stable
    // transition + stable identity trajectory.
    expect(overlay.textContent).toContain("R0: L--");
    expect(overlay.textContent).toContain("R1: L--");
    expect(overlay.textContent).toContain("R0 → R1: L-- → L--  (stable)");
    expect(overlay.textContent).toContain("R0 → R1: Stabilization");
    expect(overlay.textContent).toContain("- identity shift: stable");
  });

  it("Card 53 — renders the Structural Trajectory section with all 11 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const trajectory = screen.getByTestId("oc-structural-trajectory");
    expect(trajectory).toBeInTheDocument();
    expect(trajectory.textContent).toContain("=== Structural Trajectory ===");
    expect(trajectory.textContent).toContain("[Hydraulic Trajectory]");
    expect(trajectory.textContent).toContain("[Pressure Trajectory]");
    expect(trajectory.textContent).toContain("[Critical-Zone Trajectory]");
    expect(trajectory.textContent).toContain("[Upper-Branch Trajectory]");
    expect(trajectory.textContent).toContain("[Volatility Trajectory]");
    expect(trajectory.textContent).toContain("[Drift Trajectory]");
    expect(trajectory.textContent).toContain("[Phase Trajectory]");
    expect(trajectory.textContent).toContain("[Identity-Shift Trajectory]");
    expect(trajectory.textContent).toContain("[Projected Structural Risks]");
    expect(trajectory.textContent).toContain("[Projected Structural Opportunities]");
    expect(trajectory.textContent).toContain("[System-Level Trajectory Summary]");
    // Stub has 2 stable laminar runs → no risks; stable laminar +
    // stable pressure + zero drift opportunities should fire.
    expect(trajectory.textContent).toContain("L → L → L (stable laminar regime)");
    expect(trajectory.textContent).toContain("[Projected Structural Risks]\n(none)");
    expect(trajectory.textContent).toContain("- hydraulic stabilization");
  });

  it("Card 54 — renders the Structural Risk section with all 12 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const risk = screen.getByTestId("oc-structural-risk");
    expect(risk).toBeInTheDocument();
    expect(risk.textContent).toContain("=== Structural Risk Assessment ===");
    expect(risk.textContent).toContain("[Primitive-Level Risk]");
    expect(risk.textContent).toContain("[Run-Level Risk]");
    expect(risk.textContent).toContain("[System-Level Risk]");
    expect(risk.textContent).toContain("[Hydraulic Risk]");
    expect(risk.textContent).toContain("[Pressure Risk]");
    expect(risk.textContent).toContain("[Critical-Zone Risk]");
    expect(risk.textContent).toContain("[Upper-Branch Risk]");
    expect(risk.textContent).toContain("[Volatility Risk]");
    expect(risk.textContent).toContain("[Drift Risk]");
    expect(risk.textContent).toContain("[Identity-Shift Risk]");
    expect(risk.textContent).toContain("[Risk Classification]");
    expect(risk.textContent).toContain("[System-Level Risk Summary]");
    // Stub fixture has 2 stable laminar runs → overall LOW, no classes.
    expect(risk.textContent).toContain("R0: LOW");
    expect(risk.textContent).toContain("R1: LOW");
    expect(risk.textContent).toContain("Overall: LOW");
    expect(risk.textContent).toContain("Structural risk level: LOW.");
  });

  it("Card 55 — renders the Structural Hotspots section with all 7 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const hotspots = screen.getByTestId("oc-structural-hotspots");
    expect(hotspots).toBeInTheDocument();
    expect(hotspots.textContent).toContain("=== Structural Hotspots ===");
    expect(hotspots.textContent).toContain("[Top Primitive Hotspots]");
    expect(hotspots.textContent).toContain("[Top Run Hotspots]");
    expect(hotspots.textContent).toContain("[Structural-Dimension Hotspots]");
    expect(hotspots.textContent).toContain("[Hotspot Clusters]");
    expect(hotspots.textContent).toContain("[Hotspot Evolution]");
    expect(hotspots.textContent).toContain("[Hotspot Trajectory]");
    expect(hotspots.textContent).toContain("[System-Level Hotspot Summary]");
    // Stub has 2 stable laminar runs → no hotspots detected; both
    // runs LOW; all dimensions stable.
    expect(hotspots.textContent).toContain("R0 — LOW");
    expect(hotspots.textContent).toContain("R1 — LOW");
    expect(hotspots.textContent).toContain("- Volatility: stable");
    expect(hotspots.textContent).toContain("Structural hotspots: none detected.");
  });

  it("Card 56 — renders the Structural Causality section with all 5 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const causality = screen.getByTestId("oc-structural-causality");
    expect(causality).toBeInTheDocument();
    expect(causality.textContent).toContain("=== Structural Causality ===");
    expect(causality.textContent).toContain("[Primitive-Level Causality]");
    expect(causality.textContent).toContain("[Run-Level Causality]");
    expect(causality.textContent).toContain("[Structural-Dimension Causality]");
    expect(causality.textContent).toContain("[Identity-Shift Causality]");
    expect(causality.textContent).toContain("[System-Level Causal Summary]");
    // Stub has 2 stable laminar runs → no non-LOW runs + stable identity
    // + no causal chain.
    expect(causality.textContent).toContain("(no non-LOW runs)");
    expect(causality.textContent).toContain("Root Cause: stable identity");
    expect(causality.textContent).toContain("Structural causality: no causal chain detected. System is operating in a stable regime.");
  });

  it("Card 57 — renders the Structural Interventions section with all 5 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const interventions = screen.getByTestId("oc-structural-interventions");
    expect(interventions).toBeInTheDocument();
    expect(interventions.textContent).toContain("=== Structural Interventions ===");
    expect(interventions.textContent).toContain("[Primitive-Level Interventions]");
    expect(interventions.textContent).toContain("[Run-Level Interventions]");
    expect(interventions.textContent).toContain("[Structural-Dimension Interventions]");
    expect(interventions.textContent).toContain("[Identity-Shift Interventions]");
    expect(interventions.textContent).toContain("[System-Level Intervention Summary]");
    // Stub has 2 stable laminar runs → no non-LOW runs + stable
    // identity + no interventions required.
    expect(interventions.textContent).toContain("(no non-LOW runs)");
    expect(interventions.textContent).toContain("(none — identity is stable)");
    expect(interventions.textContent).toContain("No interventions required. System is operating within stable bounds.");
  });

  it("Card 58 — renders the Structural Stabilization section with all 8 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const stab = screen.getByTestId("oc-structural-stabilization");
    expect(stab).toBeInTheDocument();
    expect(stab.textContent).toContain("=== Structural Stabilization ===");
    expect(stab.textContent).toContain("[Stabilization Indicators]");
    expect(stab.textContent).toContain("[Stabilization Window]");
    expect(stab.textContent).toContain("[Stabilization Probability]");
    expect(stab.textContent).toContain("[Stabilization Trajectory]");
    expect(stab.textContent).toContain("[Stabilization Blockers]");
    expect(stab.textContent).toContain("[Stabilization Accelerators]");
    expect(stab.textContent).toContain("[Post-Intervention Effects]");
    expect(stab.textContent).toContain("[System-Level Stabilization Summary]");
    // Stub has 2 stable laminar runs → already-stable short-circuit.
    expect(stab.textContent).toContain("(none — system has not shown structural risk)");
    expect(stab.textContent).toContain("(already stable)");
    expect(stab.textContent).toContain("No stabilization assessment needed. System is operating within stable bounds.");
  });

  it("Card 59 — renders the Structural Resilience section with all 9 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const res = screen.getByTestId("oc-structural-resilience");
    expect(res).toBeInTheDocument();
    expect(res.textContent).toContain("=== Structural Resilience ===");
    expect(res.textContent).toContain("[Resilience Score]");
    expect(res.textContent).toContain("[Resilience Profile]");
    expect(res.textContent).toContain("[Resilience Trajectory]");
    expect(res.textContent).toContain("[Resilience Drivers]");
    expect(res.textContent).toContain("[Resilience Inhibitors]");
    expect(res.textContent).toContain("[Resilience Decay]");
    expect(res.textContent).toContain("[Resilience Reinforcement]");
    expect(res.textContent).toContain("[Post-Stabilization Resistance]");
    expect(res.textContent).toContain("[System-Level Resilience Summary]");
    // Stub fixture is fully stable laminar → never-active short-
    // circuit → HIGH baseline resilience.
    expect(res.textContent).toContain("[Resilience Score]\nHIGH");
    expect(res.textContent).toContain("Volatility: strong");
    expect(res.textContent).toContain("Baseline resilience is HIGH and unchallenged.");
  });

  it("Card 60 — renders the Structural Immunity section with all 11 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const imm = screen.getByTestId("oc-structural-immunity");
    expect(imm).toBeInTheDocument();
    expect(imm.textContent).toContain("=== Structural Immunity ===");
    expect(imm.textContent).toContain("[Immunity Score]");
    expect(imm.textContent).toContain("[Immunity Profile]");
    expect(imm.textContent).toContain("[Immunity Trajectory]");
    expect(imm.textContent).toContain("[Immunity Drivers]");
    expect(imm.textContent).toContain("[Immunity Inhibitors]");
    expect(imm.textContent).toContain("[Immunity Thresholds]");
    expect(imm.textContent).toContain("[Immunity Breach Conditions]");
    expect(imm.textContent).toContain("[Immunity Reinforcement]");
    expect(imm.textContent).toContain("[Immunity Decay]");
    expect(imm.textContent).toContain("[Early-Warning Signals]");
    expect(imm.textContent).toContain("[System-Level Immunity Summary]");
    // Stub fixture is fully stable laminar → never-active short-
    // circuit → HIGH baseline immunity.
    expect(imm.textContent).toContain("[Immunity Score]\nHIGH");
    expect(imm.textContent).toContain("- strong CZ immunity");
    // Thresholds always show baseline operating bounds.
    expect(imm.textContent).toContain("- CZ must remain below 2");
    expect(imm.textContent).toContain("Baseline immunity is HIGH and well-positioned to prevent future instability.");
  });

  it("Card 61 — renders the Structural Governance section with all 11 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const gov = screen.getByTestId("oc-structural-governance");
    expect(gov).toBeInTheDocument();
    expect(gov.textContent).toContain("=== Structural Governance ===");
    expect(gov.textContent).toContain("[Governance Level]");
    expect(gov.textContent).toContain("[Structural Invariants]");
    expect(gov.textContent).toContain("[Governance Profile]");
    expect(gov.textContent).toContain("[Governance Trajectory]");
    expect(gov.textContent).toContain("[Governance Drivers]");
    expect(gov.textContent).toContain("[Governance Inhibitors]");
    expect(gov.textContent).toContain("[Governance Thresholds]");
    expect(gov.textContent).toContain("[Governance Breach Conditions]");
    expect(gov.textContent).toContain("[Governance Reinforcement]");
    expect(gov.textContent).toContain("[Governance Decay]");
    expect(gov.textContent).toContain("[System-Level Governance Summary]");
    // Stub fixture is stable laminar → never-active short-circuit →
    // HIGH baseline governance with invariants fully held.
    expect(gov.textContent).toContain("[Governance Level]\nHIGH");
    expect(gov.textContent).toContain("- full invariant compliance");
    expect(gov.textContent).toContain("- CZ must not exceed 2");
    expect(gov.textContent).toContain("Baseline governance is HIGH and invariants are fully held.");
  });

  it("Card 62 — renders the Structural Governance Diff section with all 9 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const diff = screen.getByTestId("oc-structural-governance-diff");
    expect(diff).toBeInTheDocument();
    expect(diff.textContent).toContain("=== Structural Governance Diff ===");
    expect(diff.textContent).toContain("[Governance Delta]");
    expect(diff.textContent).toContain("[Governance Direction]");
    expect(diff.textContent).toContain("[Governance Slope]");
    expect(diff.textContent).toContain("[Governance Pressure]");
    expect(diff.textContent).toContain("[Governance Stability]");
    expect(diff.textContent).toContain("[Governance Risk]");
    expect(diff.textContent).toContain("[Governance Delta Drivers]");
    expect(diff.textContent).toContain("[Governance Delta Inhibitors]");
    expect(diff.textContent).toContain("[Governance Delta Summary]");
    // Stub fixture is stable laminar in both runs → prev (run 0 alone)
    // and next (runs 0+1) both short-circuit to HIGH baseline →
    // HIGH → HIGH, slope=0, pressure=low, risk=low, no drivers,
    // no inhibitors, no-material-change summary.
    expect(diff.textContent).toContain("[Governance Delta]\nHIGH → HIGH");
    expect(diff.textContent).toContain("[Governance Direction]\nstable");
    expect(diff.textContent).toContain("[Governance Slope]\n0");
    expect(diff.textContent).toContain("Governance remains stable with no material change.");
  });

  it("Card 63 — renders the Structural Governance Stability section with all 12 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const stab = screen.getByTestId("oc-structural-governance-stability");
    expect(stab).toBeInTheDocument();
    expect(stab.textContent).toContain("=== Structural Governance Stability ===");
    expect(stab.textContent).toContain("[Stability Level]");
    expect(stab.textContent).toContain("[Governance Coherence]");
    expect(stab.textContent).toContain("[Governance Integrity]");
    expect(stab.textContent).toContain("[Governance Drift]");
    expect(stab.textContent).toContain("[Governance Volatility]");
    expect(stab.textContent).toContain("[Stabilization Trajectory]");
    expect(stab.textContent).toContain("[Stability Drivers]");
    expect(stab.textContent).toContain("[Stability Inhibitors]");
    expect(stab.textContent).toContain("[Stability Risks]");
    expect(stab.textContent).toContain("[Stability Reinforcement]");
    expect(stab.textContent).toContain("[Stability Decay]");
    expect(stab.textContent).toContain("[System-Level Stability Summary]");
    // Stub fixture is stable laminar in both runs → HIGH governance
    // baseline (all profile dims at full/strong) → stability=HIGH,
    // coherence=strong, integrity=strong, drift=low, volatility=low,
    // trajectory stable, no inhibitors, no risks, no decay, steady summary.
    expect(stab.textContent).toContain("[Stability Level]\nHIGH");
    expect(stab.textContent).toContain("[Governance Coherence]\nstrong");
    expect(stab.textContent).toContain("[Governance Integrity]\nstrong");
    expect(stab.textContent).toContain("[Governance Drift]\nlow");
    expect(stab.textContent).toContain("[Governance Volatility]\nlow");
    expect(stab.textContent).toContain("[Stabilization Trajectory]\nhigh → high → high (stable)");
    expect(stab.textContent).toContain("Governance stability is steady with no material changes.");
  });

  it("Card 64 — renders the Structural Governance Resilience section with all 12 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const res = screen.getByTestId("oc-structural-governance-resilience");
    expect(res).toBeInTheDocument();
    expect(res.textContent).toContain("=== Structural Governance Resilience ===");
    expect(res.textContent).toContain("[Resilience Level]");
    expect(res.textContent).toContain("[Load-Bearing Capacity]");
    expect(res.textContent).toContain("[Recovery Strength]");
    expect(res.textContent).toContain("[Fault Tolerance]");
    expect(res.textContent).toContain("[Pressure Response]");
    expect(res.textContent).toContain("[Resilience Trajectory]");
    expect(res.textContent).toContain("[Resilience Drivers]");
    expect(res.textContent).toContain("[Resilience Inhibitors]");
    expect(res.textContent).toContain("[Resilience Risks]");
    expect(res.textContent).toContain("[Resilience Reinforcement]");
    expect(res.textContent).toContain("[Resilience Decay]");
    expect(res.textContent).toContain("[System-Level Resilience Summary]");
    // Stub fixture is stable laminar in both runs → HIGH baseline
    // governance + Card 63 HIGH stability + strong coherence + strong
    // integrity + low drift/volatility → resilience=HIGH with all
    // strong sub-scores and the steady summary.
    expect(res.textContent).toContain("[Resilience Level]\nHIGH");
    expect(res.textContent).toContain("[Load-Bearing Capacity]\nstrong");
    expect(res.textContent).toContain("[Recovery Strength]\nstrong");
    expect(res.textContent).toContain("[Fault Tolerance]\nstrong");
    expect(res.textContent).toContain("[Pressure Response]\nstrong");
    expect(res.textContent).toContain("[Resilience Trajectory]\nhigh → high → high (stable)");
    expect(res.textContent).toContain("Governance resilience is steady with no material changes.");
    expect(res.textContent).toContain("Recovery strength is strong, and load-bearing capacity is strong.");
  });

  it("Card 65 — renders the Structural Governance Immunity section with all 13 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const imm = screen.getByTestId("oc-structural-governance-immunity");
    expect(imm).toBeInTheDocument();
    expect(imm.textContent).toContain("=== Structural Governance Immunity ===");
    expect(imm.textContent).toContain("[Immunity Level]");
    expect(imm.textContent).toContain("[Future-Resistance]");
    expect(imm.textContent).toContain("[Governance Hardening]");
    expect(imm.textContent).toContain("[Governance Vulnerability]");
    expect(imm.textContent).toContain("[Immunity Trajectory]");
    expect(imm.textContent).toContain("[Immunity Drivers]");
    expect(imm.textContent).toContain("[Immunity Inhibitors]");
    expect(imm.textContent).toContain("[Immunity Thresholds]");
    expect(imm.textContent).toContain("[Immunity Breach Conditions]");
    expect(imm.textContent).toContain("[Immunity Reinforcement]");
    expect(imm.textContent).toContain("[Immunity Decay]");
    expect(imm.textContent).toContain("[Early-Warning Signals]");
    expect(imm.textContent).toContain("[System-Level Immunity Summary]");
    // Stub fixture is stable laminar → HIGH baselines all the way
    // through Cards 61-64 → immunity=HIGH + strong future-resistance
    // + strong hardening + low vulnerability + no early-warning,
    // and the steady summary with no remaining inhibitors.
    expect(imm.textContent).toContain("[Immunity Level]\nHIGH");
    expect(imm.textContent).toContain("[Future-Resistance]\nstrong");
    expect(imm.textContent).toContain("[Governance Hardening]\nstrong");
    expect(imm.textContent).toContain("[Governance Vulnerability]\nlow");
    expect(imm.textContent).toContain("[Immunity Trajectory]\nhigh → high → high (stable)");
    // Threshold block is always emitted verbatim.
    expect(imm.textContent).toContain("- CZ < 2");
    expect(imm.textContent).toContain("- upper-branch = 0");
    expect(imm.textContent).toContain("[Early-Warning Signals]\n(none)");
    expect(imm.textContent).toContain("Governance immunity is steady with no material changes. Future-resistance is strong.");
  });

  it("Card 66 — renders the Structural Governance Coherence section with all 12 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const coh = screen.getByTestId("oc-structural-governance-coherence");
    expect(coh).toBeInTheDocument();
    expect(coh.textContent).toContain("=== Structural Governance Coherence ===");
    expect(coh.textContent).toContain("[Coherence Level]");
    expect(coh.textContent).toContain("[Governance Alignment]");
    expect(coh.textContent).toContain("[Governance Consistency]");
    expect(coh.textContent).toContain("[Cross-Dimension Agreement]");
    expect(coh.textContent).toContain("[Contradiction Risk]");
    expect(coh.textContent).toContain("[Coherence Trajectory]");
    expect(coh.textContent).toContain("[Coherence Drivers]");
    expect(coh.textContent).toContain("[Coherence Inhibitors]");
    expect(coh.textContent).toContain("[Coherence Risks]");
    expect(coh.textContent).toContain("[Coherence Reinforcement]");
    expect(coh.textContent).toContain("[Coherence Decay]");
    expect(coh.textContent).toContain("[System-Level Coherence Summary]");
    // Stub fixture is stable laminar → HIGH baselines all the way
    // through Cards 61-65 → coherence=HIGH, all-strong sub-scores,
    // no contradiction, no drivers/inhibitors, no risks/decay, and
    // the steady summary saying everything is strong.
    expect(coh.textContent).toContain("[Coherence Level]\nHIGH");
    expect(coh.textContent).toContain("[Governance Alignment]\nstrong");
    expect(coh.textContent).toContain("[Governance Consistency]\nstrong");
    expect(coh.textContent).toContain("[Cross-Dimension Agreement]\nstrong");
    expect(coh.textContent).toContain("[Contradiction Risk]\nlow");
    expect(coh.textContent).toContain("[Coherence Trajectory]\nhigh → high → high (stable)");
    expect(coh.textContent).toContain("[Coherence Drivers]\n(none)");
    expect(coh.textContent).toContain("[Coherence Inhibitors]\n(none)");
    expect(coh.textContent).toContain("[Coherence Risks]\n(none)");
    expect(coh.textContent).toContain("Governance coherence is steady with no material changes. Alignment is strong, and cross-dimension agreement is strong.");
  });

  it("Card 67 — renders the Structural Governance Synthesis section with all 12 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const syn = screen.getByTestId("oc-structural-governance-synthesis");
    expect(syn).toBeInTheDocument();
    expect(syn.textContent).toContain("=== Structural Governance Synthesis ===");
    expect(syn.textContent).toContain("[Synthesis Level]");
    expect(syn.textContent).toContain("[Governance Integration]");
    expect(syn.textContent).toContain("[Governance Unification]");
    expect(syn.textContent).toContain("[Meta-Consistency]");
    expect(syn.textContent).toContain("[Meta-Risk]");
    expect(syn.textContent).toContain("[Meta-Trajectory]");
    expect(syn.textContent).toContain("[Synthesis Drivers]");
    expect(syn.textContent).toContain("[Synthesis Inhibitors]");
    expect(syn.textContent).toContain("[Synthesis Risks]");
    expect(syn.textContent).toContain("[Synthesis Reinforcement]");
    expect(syn.textContent).toContain("[Synthesis Decay]");
    expect(syn.textContent).toContain("[System-Level Governance Synthesis Summary]");
    // Stub fixture is stable laminar → HIGH baselines through
    // Cards 61-66 → synthesis=HIGH, all-strong sub-scores, low
    // meta-risk, no drivers/inhibitors/risks/decay, and the steady
    // summary saying everything is strong.
    expect(syn.textContent).toContain("[Synthesis Level]\nHIGH");
    expect(syn.textContent).toContain("[Governance Integration]\nstrong");
    expect(syn.textContent).toContain("[Governance Unification]\nstrong");
    expect(syn.textContent).toContain("[Meta-Consistency]\nstrong");
    expect(syn.textContent).toContain("[Meta-Risk]\nlow");
    expect(syn.textContent).toContain("[Meta-Trajectory]\nhigh → high → high (stable)");
    expect(syn.textContent).toContain("[Synthesis Drivers]\n(none)");
    expect(syn.textContent).toContain("[Synthesis Inhibitors]\n(none)");
    expect(syn.textContent).toContain("[Synthesis Risks]\n(none)");
    expect(syn.textContent).toContain("[Synthesis Decay]\n(none)");
    expect(syn.textContent).toContain("Governance synthesis is steady with no material changes. Integration is strong, and cross-layer alignment is strong.");
  });

  it("Card 68 — renders the System-Level Governance section with all 13 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const sys = screen.getByTestId("oc-system-level-governance");
    expect(sys).toBeInTheDocument();
    expect(sys.textContent).toContain("=== System-Level Governance ===");
    expect(sys.textContent).toContain("[System Governance Level]");
    expect(sys.textContent).toContain("[Governance Integrity]");
    expect(sys.textContent).toContain("[Governance Cohesion]");
    expect(sys.textContent).toContain("[Governance Robustness]");
    expect(sys.textContent).toContain("[Governance Meta-Stability]");
    expect(sys.textContent).toContain("[Governance Meta-Risk]");
    expect(sys.textContent).toContain("[System Governance Trajectory]");
    expect(sys.textContent).toContain("[System Governance Drivers]");
    expect(sys.textContent).toContain("[System Governance Inhibitors]");
    expect(sys.textContent).toContain("[System Governance Risks]");
    expect(sys.textContent).toContain("[System Governance Reinforcement]");
    expect(sys.textContent).toContain("[System Governance Decay]");
    expect(sys.textContent).toContain("[System-Level Governance Summary]");
    // Stub fixture is stable laminar → HIGH baselines through
    // Cards 61-67 → system governance=HIGH, all-strong sub-scores,
    // low meta-risk, no drivers/inhibitors/risks/decay, and the
    // steady summary with strong cohesion + meta-stability.
    expect(sys.textContent).toContain("[System Governance Level]\nHIGH");
    expect(sys.textContent).toContain("[Governance Integrity]\nstrong");
    expect(sys.textContent).toContain("[Governance Cohesion]\nstrong");
    expect(sys.textContent).toContain("[Governance Robustness]\nstrong");
    expect(sys.textContent).toContain("[Governance Meta-Stability]\nstrong");
    expect(sys.textContent).toContain("[Governance Meta-Risk]\nlow");
    expect(sys.textContent).toContain("[System Governance Trajectory]\nhigh → high → high (stable)");
    expect(sys.textContent).toContain("[System Governance Drivers]\n(none)");
    expect(sys.textContent).toContain("[System Governance Inhibitors]\n(none)");
    expect(sys.textContent).toContain("[System Governance Risks]\n(none)");
    expect(sys.textContent).toContain("[System Governance Decay]\n(none)");
    expect(sys.textContent).toContain("System-level governance is steady with no material changes. Cohesion is strong, and meta-stability is strong.");
  });

  it("Card 69 — renders the Operator State section with all 10 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const op = screen.getByTestId("oc-operator-state");
    expect(op).toBeInTheDocument();
    expect(op.textContent).toContain("=== Operator State ===");
    expect(op.textContent).toContain("[Operator Level]");
    expect(op.textContent).toContain("[Operator Load]");
    expect(op.textContent).toContain("[Operator Drift]");
    expect(op.textContent).toContain("[Operator Clarity]");
    expect(op.textContent).toContain("[Operator Stability]");
    expect(op.textContent).toContain("[Operator Pressure]");
    expect(op.textContent).toContain("[Operator Risk]");
    expect(op.textContent).toContain("[Operator Drivers]");
    expect(op.textContent).toContain("[Operator Inhibitors]");
    expect(op.textContent).toContain("[Operator Summary]");
    // Stub fixture JSON has no `key=value` operator tokens → all
    // defaults → HIGH level, all-optimal sub-fields, no drivers/
    // inhibitors, and the steady summary.
    expect(op.textContent).toContain("[Operator Level]\nHIGH");
    expect(op.textContent).toContain("[Operator Load]\nlow");
    expect(op.textContent).toContain("[Operator Drift]\nlow");
    expect(op.textContent).toContain("[Operator Clarity]\nstrong");
    expect(op.textContent).toContain("[Operator Stability]\nstrong");
    expect(op.textContent).toContain("[Operator Pressure]\nlow");
    expect(op.textContent).toContain("[Operator Risk]\nlow");
    expect(op.textContent).toContain("[Operator Drivers]\n(none)");
    expect(op.textContent).toContain("[Operator Inhibitors]\n(none)");
    expect(op.textContent).toContain("Operator state is steady. Clarity is strong, drift is low, and stability is strong.");
  });

  it("Card 70 — renders the Operator Diff section with all 11 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const diff = screen.getByTestId("oc-operator-diff");
    expect(diff).toBeInTheDocument();
    expect(diff.textContent).toContain("=== Operator Diff ===");
    expect(diff.textContent).toContain("[Operator Slope]");
    expect(diff.textContent).toContain("[Drift Delta]");
    expect(diff.textContent).toContain("[Clarity Delta]");
    expect(diff.textContent).toContain("[Load Delta]");
    expect(diff.textContent).toContain("[Pressure Delta]");
    expect(diff.textContent).toContain("[Stability Delta]");
    expect(diff.textContent).toContain("[Risk Delta]");
    expect(diff.textContent).toContain("[Operator Diff Drivers]");
    expect(diff.textContent).toContain("[Operator Diff Inhibitors]");
    expect(diff.textContent).toContain("[Operator Diff Summary]");
    // Stub fixture JSON has no operator tokens → prev = curr = HIGH
    // baseline → slope=HIGH, all-stable deltas, no drivers/inhibitors,
    // steady summary.
    expect(diff.textContent).toContain("[Operator Slope]\nHIGH");
    expect(diff.textContent).toContain("[Drift Delta]\nlow");
    expect(diff.textContent).toContain("[Clarity Delta]\nstrong");
    expect(diff.textContent).toContain("[Load Delta]\nlow");
    expect(diff.textContent).toContain("[Pressure Delta]\nlow");
    expect(diff.textContent).toContain("[Stability Delta]\nstrong");
    expect(diff.textContent).toContain("[Risk Delta]\nlow");
    expect(diff.textContent).toContain("[Operator Diff Drivers]\n(none)");
    expect(diff.textContent).toContain("[Operator Diff Inhibitors]\n(none)");
    expect(diff.textContent).toContain("Operator trajectory is steady. Drift is low, clarity is steady, and stability is steady.");
  });

  it("Card 71 — renders the Operator Stability section with all 14 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const stab = screen.getByTestId("oc-operator-stability");
    expect(stab).toBeInTheDocument();
    expect(stab.textContent).toContain("=== Operator Stability ===");
    expect(stab.textContent).toContain("[Stability Level]");
    expect(stab.textContent).toContain("[Operator Equilibrium]");
    expect(stab.textContent).toContain("[Operator Volatility]");
    expect(stab.textContent).toContain("[Drift-Stability]");
    expect(stab.textContent).toContain("[Clarity-Stability]");
    expect(stab.textContent).toContain("[Load-Stability]");
    expect(stab.textContent).toContain("[Pressure-Stability]");
    expect(stab.textContent).toContain("[Stability Trajectory]");
    expect(stab.textContent).toContain("[Stability Drivers]");
    expect(stab.textContent).toContain("[Stability Inhibitors]");
    expect(stab.textContent).toContain("[Stability Risks]");
    expect(stab.textContent).toContain("[Stability Reinforcement]");
    expect(stab.textContent).toContain("[Stability Decay]");
    expect(stab.textContent).toContain("[Operator Stability Summary]");
    // Stub fixture JSON has no operator tokens → HIGH state + stable
    // diff → stability=HIGH, all-strong sub-fields, low volatility,
    // strong equilibrium, no drivers/inhibitors/risks, full
    // reinforcement, and the steady summary.
    expect(stab.textContent).toContain("[Stability Level]\nHIGH");
    expect(stab.textContent).toContain("[Operator Equilibrium]\nstrong");
    expect(stab.textContent).toContain("[Operator Volatility]\nlow");
    expect(stab.textContent).toContain("[Drift-Stability]\nstrong");
    expect(stab.textContent).toContain("[Clarity-Stability]\nstrong");
    expect(stab.textContent).toContain("[Load-Stability]\nstrong");
    expect(stab.textContent).toContain("[Pressure-Stability]\nstrong");
    expect(stab.textContent).toContain("[Stability Trajectory]\nhigh → high → high (stable)");
    expect(stab.textContent).toContain("[Stability Drivers]\n(none)");
    expect(stab.textContent).toContain("[Stability Inhibitors]\n(none)");
    expect(stab.textContent).toContain("[Stability Risks]\n(none)");
    expect(stab.textContent).toContain("Operator stability is steady. Drift-stability is strong, clarity-stability is strong, and volatility is low.");
  });

  it("Card 72 — renders the Operator Resilience section with all 14 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const res = screen.getByTestId("oc-operator-resilience");
    expect(res).toBeInTheDocument();
    expect(res.textContent).toContain("=== Operator Resilience ===");
    expect(res.textContent).toContain("[Resilience Level]");
    expect(res.textContent).toContain("[Operator Recovery]");
    expect(res.textContent).toContain("[Operator Rebound]");
    expect(res.textContent).toContain("[Drift-Recovery]");
    expect(res.textContent).toContain("[Clarity-Recovery]");
    expect(res.textContent).toContain("[Load-Recovery]");
    expect(res.textContent).toContain("[Pressure-Recovery]");
    expect(res.textContent).toContain("[Resilience Trajectory]");
    expect(res.textContent).toContain("[Resilience Drivers]");
    expect(res.textContent).toContain("[Resilience Inhibitors]");
    expect(res.textContent).toContain("[Resilience Risks]");
    expect(res.textContent).toContain("[Resilience Reinforcement]");
    expect(res.textContent).toContain("[Resilience Decay]");
    expect(res.textContent).toContain("[Operator Resilience Summary]");
    // Stub fixture JSON has no operator tokens → HIGH state + stable
    // diff + HIGH stability → resilience=HIGH, all-strong recoveries,
    // strong rebound, no drivers/inhibitors/risks, full reinforcement,
    // and the steady summary.
    expect(res.textContent).toContain("[Resilience Level]\nHIGH");
    expect(res.textContent).toContain("[Operator Recovery]\nstrong");
    expect(res.textContent).toContain("[Operator Rebound]\nstrong");
    expect(res.textContent).toContain("[Drift-Recovery]\nstrong");
    expect(res.textContent).toContain("[Clarity-Recovery]\nstrong");
    expect(res.textContent).toContain("[Load-Recovery]\nstrong");
    expect(res.textContent).toContain("[Pressure-Recovery]\nstrong");
    expect(res.textContent).toContain("[Resilience Trajectory]\nhigh → high → high (stable)");
    expect(res.textContent).toContain("[Resilience Drivers]\n(none)");
    expect(res.textContent).toContain("[Resilience Inhibitors]\n(none)");
    expect(res.textContent).toContain("[Resilience Risks]\n(none)");
    expect(res.textContent).toContain("Operator resilience is steady. Drift-recovery is strong, clarity-recovery is strong, and rebound is strong.");
  });

  it("Card 73 — renders the Operator Immunity section with all 14 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const imm = screen.getByTestId("oc-operator-immunity");
    expect(imm).toBeInTheDocument();
    expect(imm.textContent).toContain("=== Operator Immunity ===");
    expect(imm.textContent).toContain("[Immunity Level]");
    expect(imm.textContent).toContain("[Operator Resistance]");
    expect(imm.textContent).toContain("[Operator Shielding]");
    expect(imm.textContent).toContain("[Drift-Immunity]");
    expect(imm.textContent).toContain("[Clarity-Immunity]");
    expect(imm.textContent).toContain("[Load-Immunity]");
    expect(imm.textContent).toContain("[Pressure-Immunity]");
    expect(imm.textContent).toContain("[Immunity Trajectory]");
    expect(imm.textContent).toContain("[Immunity Drivers]");
    expect(imm.textContent).toContain("[Immunity Inhibitors]");
    expect(imm.textContent).toContain("[Immunity Risks]");
    expect(imm.textContent).toContain("[Immunity Reinforcement]");
    expect(imm.textContent).toContain("[Immunity Decay]");
    expect(imm.textContent).toContain("[Operator Immunity Summary]");
    // Stub fixture JSON has no operator tokens → HIGH state + stable
    // diff + HIGH stability + HIGH resilience → immunity=HIGH, all-
    // strong sub-fields, strong shielding, no drivers/inhibitors/risks,
    // full reinforcement, steady summary.
    expect(imm.textContent).toContain("[Immunity Level]\nHIGH");
    expect(imm.textContent).toContain("[Operator Resistance]\nstrong");
    expect(imm.textContent).toContain("[Operator Shielding]\nstrong");
    expect(imm.textContent).toContain("[Drift-Immunity]\nstrong");
    expect(imm.textContent).toContain("[Clarity-Immunity]\nstrong");
    expect(imm.textContent).toContain("[Load-Immunity]\nstrong");
    expect(imm.textContent).toContain("[Pressure-Immunity]\nstrong");
    expect(imm.textContent).toContain("[Immunity Trajectory]\nhigh → high → high (stable)");
    expect(imm.textContent).toContain("[Immunity Drivers]\n(none)");
    expect(imm.textContent).toContain("[Immunity Inhibitors]\n(none)");
    expect(imm.textContent).toContain("[Immunity Risks]\n(none)");
    expect(imm.textContent).toContain("Operator immunity is steady. Drift-immunity is strong, clarity-immunity is strong, and shielding is strong.");
  });

  it("Card 74 — renders the Operator Coherence section with all 14 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const coh = screen.getByTestId("oc-operator-coherence");
    expect(coh).toBeInTheDocument();
    expect(coh.textContent).toContain("=== Operator Coherence ===");
    expect(coh.textContent).toContain("[Coherence Level]");
    expect(coh.textContent).toContain("[Operator Alignment]");
    expect(coh.textContent).toContain("[Operator Integration]");
    expect(coh.textContent).toContain("[Clarity-Alignment]");
    expect(coh.textContent).toContain("[Drift-Alignment]");
    expect(coh.textContent).toContain("[Load-Alignment]");
    expect(coh.textContent).toContain("[Pressure-Alignment]");
    expect(coh.textContent).toContain("[Coherence Trajectory]");
    expect(coh.textContent).toContain("[Coherence Drivers]");
    expect(coh.textContent).toContain("[Coherence Inhibitors]");
    expect(coh.textContent).toContain("[Coherence Risks]");
    expect(coh.textContent).toContain("[Coherence Reinforcement]");
    expect(coh.textContent).toContain("[Coherence Decay]");
    expect(coh.textContent).toContain("[Operator Coherence Summary]");
    // Stub fixture JSON has no operator tokens → HIGH everything →
    // coherence=HIGH, strong alignment + integration, all-strong
    // per-dim alignments, no drivers/inhibitors/risks/decay, full
    // reinforcement, steady summary.
    expect(coh.textContent).toContain("[Coherence Level]\nHIGH");
    expect(coh.textContent).toContain("[Operator Alignment]\nstrong alignment");
    expect(coh.textContent).toContain("[Operator Integration]\nstrong integration");
    expect(coh.textContent).toContain("[Clarity-Alignment]\nstrong");
    expect(coh.textContent).toContain("[Drift-Alignment]\nstrong");
    expect(coh.textContent).toContain("[Load-Alignment]\nstrong");
    expect(coh.textContent).toContain("[Pressure-Alignment]\nstrong");
    expect(coh.textContent).toContain("[Coherence Trajectory]\nhigh → high → high (stable)");
    expect(coh.textContent).toContain("[Coherence Drivers]\n(none)");
    expect(coh.textContent).toContain("[Coherence Inhibitors]\n(none)");
    expect(coh.textContent).toContain("[Coherence Risks]\n(none)");
    expect(coh.textContent).toContain("[Coherence Decay]\n(none)");
    expect(coh.textContent).toContain("Operator coherence is steady, with strong clarity-alignment and strong integration.");
  });

  it("Card 75 — renders the Operator Synthesis section with all 14 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const syn = screen.getByTestId("oc-operator-synthesis");
    expect(syn).toBeInTheDocument();
    expect(syn.textContent).toContain("=== Operator Synthesis ===");
    expect(syn.textContent).toContain("[Synthesis Level]");
    expect(syn.textContent).toContain("[Operator Integration]");
    expect(syn.textContent).toContain("[Operator Unification]");
    expect(syn.textContent).toContain("[Clarity-Synthesis]");
    expect(syn.textContent).toContain("[Drift-Synthesis]");
    expect(syn.textContent).toContain("[Load-Synthesis]");
    expect(syn.textContent).toContain("[Pressure-Synthesis]");
    expect(syn.textContent).toContain("[Synthesis Trajectory]");
    expect(syn.textContent).toContain("[Synthesis Drivers]");
    expect(syn.textContent).toContain("[Synthesis Inhibitors]");
    expect(syn.textContent).toContain("[Synthesis Risks]");
    expect(syn.textContent).toContain("[Synthesis Reinforcement]");
    expect(syn.textContent).toContain("[Synthesis Decay]");
    expect(syn.textContent).toContain("[Operator Synthesis Summary]");
    // Stub fixture JSON has no operator tokens → HIGH everything →
    // synthesis=HIGH, strong integration + unification, all-strong
    // per-dim syntheses, no inhibitors/risks/decay, steady summary.
    expect(syn.textContent).toContain("[Synthesis Level]\nHIGH");
    expect(syn.textContent).toContain("[Operator Integration]\nstrong integration");
    expect(syn.textContent).toContain("[Operator Unification]\nstrong unification");
    expect(syn.textContent).toContain("[Clarity-Synthesis]\nstrong");
    expect(syn.textContent).toContain("[Drift-Synthesis]\nstable");
    expect(syn.textContent).toContain("[Load-Synthesis]\nstrong");
    expect(syn.textContent).toContain("[Pressure-Synthesis]\nstrong");
    expect(syn.textContent).toContain("[Synthesis Trajectory]\nhigh → high → high (stable)");
    expect(syn.textContent).toContain("[Synthesis Inhibitors]\n(none)");
    expect(syn.textContent).toContain("[Synthesis Risks]\n(none)");
    expect(syn.textContent).toContain("[Synthesis Decay]\n(none)");
    expect(syn.textContent).toContain("Operator synthesis is steady, with strong clarity-synthesis and stable drift-synthesis.");
  });

  it("Card 76 — renders the System-Operator Integration section with all 11 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const soi = screen.getByTestId("oc-system-operator-integration");
    expect(soi).toBeInTheDocument();
    expect(soi.textContent).toContain("=== System-Operator Integration ===");
    expect(soi.textContent).toContain("[Integration Level]");
    expect(soi.textContent).toContain("[System-Operator Alignment]");
    expect(soi.textContent).toContain("[System-Operator Coherence]");
    expect(soi.textContent).toContain("[System-Operator Synthesis]");
    expect(soi.textContent).toContain("[Integration Trajectory]");
    expect(soi.textContent).toContain("[Integration Drivers]");
    expect(soi.textContent).toContain("[Integration Inhibitors]");
    expect(soi.textContent).toContain("[Integration Risks]");
    expect(soi.textContent).toContain("[Integration Reinforcement]");
    expect(soi.textContent).toContain("[Integration Decay]");
    expect(soi.textContent).toContain("[System-Operator Integration Summary]");
    // Stub fixture JSON has no operator tokens → operator chain at
    // HIGH. The Phase-3 structural helpers (resilience/immunity/
    // stabilization) also report HIGH for the stable laminar stub
    // context → integration=HIGH, strong alignment/coherence/
    // synthesis, no inhibitors/risks/decay, steady summary.
    expect(soi.textContent).toContain("[Integration Level]\nHIGH");
    expect(soi.textContent).toContain("[System-Operator Alignment]\nstrong alignment");
    expect(soi.textContent).toContain("[System-Operator Coherence]\nstrong coherence");
    expect(soi.textContent).toContain("[System-Operator Synthesis]\nstrong synthesis");
    expect(soi.textContent).toContain("[Integration Trajectory]\nhigh → high → high (stable)");
    expect(soi.textContent).toContain("[Integration Inhibitors]\n(none)");
    expect(soi.textContent).toContain("[Integration Risks]\n(none)");
    expect(soi.textContent).toContain("[Integration Decay]\n(none)");
    expect(soi.textContent).toContain("System-operator integration is steady, with strong synthesis and strong coherence.");
  });

  it("Card 77 — renders the Operator Meta-Pattern section with all 12 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const mp = screen.getByTestId("oc-operator-meta-pattern");
    expect(mp).toBeInTheDocument();
    expect(mp.textContent).toContain("=== Operator Meta-Pattern ===");
    expect(mp.textContent).toContain("[Meta-Pattern Level]");
    expect(mp.textContent).toContain("[Meta-Alignment]");
    expect(mp.textContent).toContain("[Meta-Drift Detection]");
    expect(mp.textContent).toContain("[Meta-Load Interpretation]");
    expect(mp.textContent).toContain("[Meta-Pressure Interpretation]");
    expect(mp.textContent).toContain("[Meta-Trajectory]");
    expect(mp.textContent).toContain("[Meta-Pattern Drivers]");
    expect(mp.textContent).toContain("[Meta-Pattern Inhibitors]");
    expect(mp.textContent).toContain("[Meta-Pattern Risks]");
    expect(mp.textContent).toContain("[Meta-Pattern Reinforcement]");
    expect(mp.textContent).toContain("[Meta-Pattern Decay]");
    expect(mp.textContent).toContain("[Operator Meta-Pattern Summary]");
    // Stub fixture JSON has no operator tokens → full chain at HIGH
    // → meta-pattern=HIGH, strong alignment, low drift/load/pressure,
    // stable trajectory, no inhibitors/risks/decay, steady summary.
    expect(mp.textContent).toContain("[Meta-Pattern Level]\nHIGH");
    expect(mp.textContent).toContain("[Meta-Alignment]\nstrong alignment");
    expect(mp.textContent).toContain("[Meta-Drift Detection]\nlow drift detected");
    expect(mp.textContent).toContain("[Meta-Load Interpretation]\nlow load");
    expect(mp.textContent).toContain("[Meta-Pressure Interpretation]\nlow pressure");
    expect(mp.textContent).toContain("[Meta-Trajectory]\nhigh → high → high (stable)");
    expect(mp.textContent).toContain("[Meta-Pattern Inhibitors]\n(none)");
    expect(mp.textContent).toContain("[Meta-Pattern Risks]\n(none)");
    expect(mp.textContent).toContain("[Meta-Pattern Decay]\n(none)");
    expect(mp.textContent).toContain("Operator meta-pattern stability is steady, with strong synthesis and stable drift.");
  });

  it("Card 78 — renders the Operator Meta-Stability section with all 12 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const ms = screen.getByTestId("oc-operator-meta-stability");
    expect(ms).toBeInTheDocument();
    expect(ms.textContent).toContain("=== Operator Meta-Stability ===");
    expect(ms.textContent).toContain("[Meta-Stability Level]");
    expect(ms.textContent).toContain("[Transition-Stability]");
    expect(ms.textContent).toContain("[Load-Stability]");
    expect(ms.textContent).toContain("[Pressure-Stability]");
    expect(ms.textContent).toContain("[Drift-Stability]");
    expect(ms.textContent).toContain("[Meta-Stability Trajectory]");
    expect(ms.textContent).toContain("[Meta-Stability Drivers]");
    expect(ms.textContent).toContain("[Meta-Stability Inhibitors]");
    expect(ms.textContent).toContain("[Meta-Stability Risks]");
    expect(ms.textContent).toContain("[Meta-Stability Reinforcement]");
    expect(ms.textContent).toContain("[Meta-Stability Decay]");
    expect(ms.textContent).toContain("[Operator Meta-Stability Summary]");
    // Stub fixture JSON has no operator tokens → full chain at HIGH
    // → meta-stability=HIGH, all-strong stabilities, stable trajectory,
    // no inhibitors/risks/decay, steady summary.
    expect(ms.textContent).toContain("[Meta-Stability Level]\nHIGH");
    expect(ms.textContent).toContain("[Transition-Stability]\nstrong stability");
    expect(ms.textContent).toContain("[Load-Stability]\nstrong stability");
    expect(ms.textContent).toContain("[Pressure-Stability]\nstrong stability");
    expect(ms.textContent).toContain("[Drift-Stability]\nstrong stability");
    expect(ms.textContent).toContain("[Meta-Stability Trajectory]\nhigh → high → high (stable)");
    expect(ms.textContent).toContain("[Meta-Stability Inhibitors]\n(none)");
    expect(ms.textContent).toContain("[Meta-Stability Risks]\n(none)");
    expect(ms.textContent).toContain("[Meta-Stability Decay]\n(none)");
    expect(ms.textContent).toContain("Operator meta-stability is steady, with strong drift-stability and stable meta-pattern.");
  });

  it("Card 79 — renders the Operator Meta-Resilience section with all 12 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const mr = screen.getByTestId("oc-operator-meta-resilience");
    expect(mr).toBeInTheDocument();
    expect(mr.textContent).toContain("=== Operator Meta-Resilience ===");
    expect(mr.textContent).toContain("[Meta-Resilience Level]");
    expect(mr.textContent).toContain("[Volatility-Resilience]");
    expect(mr.textContent).toContain("[Pressure-Resilience]");
    expect(mr.textContent).toContain("[Drift-Resilience]");
    expect(mr.textContent).toContain("[Load-Resilience]");
    expect(mr.textContent).toContain("[Meta-Resilience Trajectory]");
    expect(mr.textContent).toContain("[Meta-Resilience Drivers]");
    expect(mr.textContent).toContain("[Meta-Resilience Inhibitors]");
    expect(mr.textContent).toContain("[Meta-Resilience Risks]");
    expect(mr.textContent).toContain("[Meta-Resilience Reinforcement]");
    expect(mr.textContent).toContain("[Meta-Resilience Decay]");
    expect(mr.textContent).toContain("[Operator Meta-Resilience Summary]");
    // Stub fixture JSON has no operator tokens → full chain at HIGH
    // → meta-resilience=HIGH, all-strong resiliences, stable
    // trajectory, no inhibitors/risks/decay, steady summary.
    expect(mr.textContent).toContain("[Meta-Resilience Level]\nHIGH");
    expect(mr.textContent).toContain("[Volatility-Resilience]\nstrong resilience");
    expect(mr.textContent).toContain("[Pressure-Resilience]\nstrong resilience");
    expect(mr.textContent).toContain("[Drift-Resilience]\nstrong resilience");
    expect(mr.textContent).toContain("[Load-Resilience]\nstrong resilience");
    expect(mr.textContent).toContain("[Meta-Resilience Trajectory]\nhigh → high → high (stable)");
    expect(mr.textContent).toContain("[Meta-Resilience Inhibitors]\n(none)");
    expect(mr.textContent).toContain("[Meta-Resilience Risks]\n(none)");
    expect(mr.textContent).toContain("[Meta-Resilience Decay]\n(none)");
    expect(mr.textContent).toContain("Operator meta-resilience is steady, with strong drift-resilience and stable meta-pattern.");
  });

  it("Card 80 — renders the Operator Meta-Immunity section with all 13 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const mi = screen.getByTestId("oc-operator-meta-immunity");
    expect(mi).toBeInTheDocument();
    expect(mi.textContent).toContain("=== Operator Meta-Immunity ===");
    expect(mi.textContent).toContain("[Meta-Immunity Level]");
    expect(mi.textContent).toContain("[Clarity-Immunity]");
    expect(mi.textContent).toContain("[Drift-Immunity]");
    expect(mi.textContent).toContain("[Load-Immunity]");
    expect(mi.textContent).toContain("[Pressure-Immunity]");
    expect(mi.textContent).toContain("[Volatility-Immunity]");
    expect(mi.textContent).toContain("[Meta-Immunity Trajectory]");
    expect(mi.textContent).toContain("[Meta-Immunity Drivers]");
    expect(mi.textContent).toContain("[Meta-Immunity Inhibitors]");
    expect(mi.textContent).toContain("[Meta-Immunity Risks]");
    expect(mi.textContent).toContain("[Meta-Immunity Reinforcement]");
    expect(mi.textContent).toContain("[Meta-Immunity Decay]");
    expect(mi.textContent).toContain("[Operator Meta-Immunity Summary]");
    // Stub fixture JSON has no operator tokens → full chain at HIGH
    // → meta-immunity=HIGH, all-strong immunities, stable trajectory,
    // no inhibitors/risks/decay, steady summary.
    expect(mi.textContent).toContain("[Meta-Immunity Level]\nHIGH");
    expect(mi.textContent).toContain("[Clarity-Immunity]\nstrong immunity");
    expect(mi.textContent).toContain("[Drift-Immunity]\nstrong immunity");
    expect(mi.textContent).toContain("[Load-Immunity]\nstrong immunity");
    expect(mi.textContent).toContain("[Pressure-Immunity]\nstrong immunity");
    expect(mi.textContent).toContain("[Volatility-Immunity]\nstrong immunity");
    expect(mi.textContent).toContain("[Meta-Immunity Trajectory]\nhigh → high → high (stable)");
    expect(mi.textContent).toContain("[Meta-Immunity Inhibitors]\n(none)");
    expect(mi.textContent).toContain("[Meta-Immunity Risks]\n(none)");
    expect(mi.textContent).toContain("[Meta-Immunity Decay]\n(none)");
    expect(mi.textContent).toContain("Operator meta-immunity is steady, with strong clarity- and drift-immunity.");
  });

  it("Card 81 — renders the Operator Meta-Integration section with all 14 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const mi2 = screen.getByTestId("oc-operator-meta-integration");
    expect(mi2).toBeInTheDocument();
    expect(mi2.textContent).toContain("=== Operator Meta-Integration ===");
    expect(mi2.textContent).toContain("[Meta-Integration Level]");
    expect(mi2.textContent).toContain("[Coherence-Integration]");
    expect(mi2.textContent).toContain("[Synthesis-Integration]");
    expect(mi2.textContent).toContain("[Stability-Integration]");
    expect(mi2.textContent).toContain("[Resilience-Integration]");
    expect(mi2.textContent).toContain("[Immunity-Integration]");
    expect(mi2.textContent).toContain("[Pattern-Integration]");
    expect(mi2.textContent).toContain("[Meta-Integration Trajectory]");
    expect(mi2.textContent).toContain("[Meta-Integration Drivers]");
    expect(mi2.textContent).toContain("[Meta-Integration Inhibitors]");
    expect(mi2.textContent).toContain("[Meta-Integration Risks]");
    expect(mi2.textContent).toContain("[Meta-Integration Reinforcement]");
    expect(mi2.textContent).toContain("[Meta-Integration Decay]");
    expect(mi2.textContent).toContain("[Operator Meta-Integration Summary]");
    // Stub fixture JSON has no operator tokens → full chain at HIGH
    // → meta-integration=HIGH, all-strong integrations, stable
    // trajectory, no inhibitors/risks/decay, steady summary.
    expect(mi2.textContent).toContain("[Meta-Integration Level]\nHIGH");
    expect(mi2.textContent).toContain("[Coherence-Integration]\nstrong integration");
    expect(mi2.textContent).toContain("[Synthesis-Integration]\nstrong integration");
    expect(mi2.textContent).toContain("[Stability-Integration]\nstrong stability");
    expect(mi2.textContent).toContain("[Resilience-Integration]\nstrong resilience");
    expect(mi2.textContent).toContain("[Immunity-Integration]\nstrong immunity");
    expect(mi2.textContent).toContain("[Pattern-Integration]\nstable pattern integration");
    expect(mi2.textContent).toContain("[Meta-Integration Trajectory]\nhigh → high → high (stable)");
    expect(mi2.textContent).toContain("[Meta-Integration Inhibitors]\n(none)");
    expect(mi2.textContent).toContain("[Meta-Integration Risks]\n(none)");
    expect(mi2.textContent).toContain("[Meta-Integration Decay]\n(none)");
    expect(mi2.textContent).toContain("Operator meta-integration is steady, with strong synthesis- and resilience-integration.");
  });

  it("Card 82 — renders the Operator Meta-Alignment section with all 14 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const ma = screen.getByTestId("oc-operator-meta-alignment");
    expect(ma).toBeInTheDocument();
    expect(ma.textContent).toContain("=== Operator Meta-Alignment ===");
    expect(ma.textContent).toContain("[Meta-Alignment Level]");
    expect(ma.textContent).toContain("[Coherence-Alignment]");
    expect(ma.textContent).toContain("[Synthesis-Alignment]");
    expect(ma.textContent).toContain("[Stability-Alignment]");
    expect(ma.textContent).toContain("[Resilience-Alignment]");
    expect(ma.textContent).toContain("[Immunity-Alignment]");
    expect(ma.textContent).toContain("[Pattern-Alignment]");
    expect(ma.textContent).toContain("[Meta-Alignment Trajectory]");
    expect(ma.textContent).toContain("[Meta-Alignment Drivers]");
    expect(ma.textContent).toContain("[Meta-Alignment Inhibitors]");
    expect(ma.textContent).toContain("[Meta-Alignment Risks]");
    expect(ma.textContent).toContain("[Meta-Alignment Reinforcement]");
    expect(ma.textContent).toContain("[Meta-Alignment Decay]");
    expect(ma.textContent).toContain("[Operator Meta-Alignment Summary]");
    // Stub fixture JSON has no operator tokens → full chain at HIGH
    // → meta-alignment=HIGH, all-strong alignments, stable trajectory,
    // no inhibitors/risks/decay, steady summary.
    expect(ma.textContent).toContain("[Meta-Alignment Level]\nHIGH");
    expect(ma.textContent).toContain("[Coherence-Alignment]\nstrong alignment");
    expect(ma.textContent).toContain("[Synthesis-Alignment]\nstrong alignment");
    expect(ma.textContent).toContain("[Stability-Alignment]\nstrong alignment");
    expect(ma.textContent).toContain("[Resilience-Alignment]\nstrong alignment");
    expect(ma.textContent).toContain("[Immunity-Alignment]\nstrong alignment");
    expect(ma.textContent).toContain("[Pattern-Alignment]\nstable pattern alignment");
    expect(ma.textContent).toContain("[Meta-Alignment Trajectory]\nhigh → high → high (stable)");
    expect(ma.textContent).toContain("[Meta-Alignment Inhibitors]\n(none)");
    expect(ma.textContent).toContain("[Meta-Alignment Risks]\n(none)");
    expect(ma.textContent).toContain("[Meta-Alignment Decay]\n(none)");
    expect(ma.textContent).toContain("Operator meta-alignment is steady, with strong synthesis- and resilience-alignment.");
  });

  it("Card 83 — renders the Operator Meta-Coherence section with all 14 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const mc = screen.getByTestId("oc-operator-meta-coherence");
    expect(mc).toBeInTheDocument();
    expect(mc.textContent).toContain("=== Operator Meta-Coherence ===");
    expect(mc.textContent).toContain("[Meta-Coherence Level]");
    expect(mc.textContent).toContain("[Synthesis-Coherence]");
    expect(mc.textContent).toContain("[Stability-Coherence]");
    expect(mc.textContent).toContain("[Resilience-Coherence]");
    expect(mc.textContent).toContain("[Immunity-Coherence]");
    expect(mc.textContent).toContain("[Integration-Coherence]");
    expect(mc.textContent).toContain("[Alignment-Coherence]");
    expect(mc.textContent).toContain("[Meta-Coherence Trajectory]");
    expect(mc.textContent).toContain("[Meta-Coherence Drivers]");
    expect(mc.textContent).toContain("[Meta-Coherence Inhibitors]");
    expect(mc.textContent).toContain("[Meta-Coherence Risks]");
    expect(mc.textContent).toContain("[Meta-Coherence Reinforcement]");
    expect(mc.textContent).toContain("[Meta-Coherence Decay]");
    expect(mc.textContent).toContain("[Operator Meta-Coherence Summary]");
    // Stub fixture JSON has no operator tokens → full chain at HIGH
    // → meta-coherence=HIGH, all-strong coherences, stable trajectory,
    // no inhibitors/risks/decay, steady summary.
    expect(mc.textContent).toContain("[Meta-Coherence Level]\nHIGH");
    expect(mc.textContent).toContain("[Synthesis-Coherence]\nstrong coherence");
    expect(mc.textContent).toContain("[Stability-Coherence]\nstrong coherence");
    expect(mc.textContent).toContain("[Resilience-Coherence]\nstrong coherence");
    expect(mc.textContent).toContain("[Immunity-Coherence]\nstrong coherence");
    expect(mc.textContent).toContain("[Integration-Coherence]\nstrong integration coherence");
    expect(mc.textContent).toContain("[Alignment-Coherence]\nstrong alignment coherence");
    expect(mc.textContent).toContain("[Meta-Coherence Trajectory]\nhigh → high → high (stable)");
    expect(mc.textContent).toContain("[Meta-Coherence Inhibitors]\n(none)");
    expect(mc.textContent).toContain("[Meta-Coherence Risks]\n(none)");
    expect(mc.textContent).toContain("[Meta-Coherence Decay]\n(none)");
    expect(mc.textContent).toContain("Operator meta-coherence is steady, with strong synthesis-, resilience-, and integration-coherence.");
  });

  it("Card 84 — renders the Operator Meta-Synthesis section with all 15 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const ms2 = screen.getByTestId("oc-operator-meta-synthesis");
    expect(ms2).toBeInTheDocument();
    expect(ms2.textContent).toContain("=== Operator Meta-Synthesis ===");
    expect(ms2.textContent).toContain("[Meta-Synthesis Level]");
    expect(ms2.textContent).toContain("[Coherence-Synthesis]");
    expect(ms2.textContent).toContain("[Stability-Synthesis]");
    expect(ms2.textContent).toContain("[Resilience-Synthesis]");
    expect(ms2.textContent).toContain("[Immunity-Synthesis]");
    expect(ms2.textContent).toContain("[Integration-Synthesis]");
    expect(ms2.textContent).toContain("[Alignment-Synthesis]");
    expect(ms2.textContent).toContain("[Pattern-Synthesis]");
    expect(ms2.textContent).toContain("[Meta-Synthesis Trajectory]");
    expect(ms2.textContent).toContain("[Meta-Synthesis Drivers]");
    expect(ms2.textContent).toContain("[Meta-Synthesis Inhibitors]");
    expect(ms2.textContent).toContain("[Meta-Synthesis Risks]");
    expect(ms2.textContent).toContain("[Meta-Synthesis Reinforcement]");
    expect(ms2.textContent).toContain("[Meta-Synthesis Decay]");
    expect(ms2.textContent).toContain("[Operator Meta-Synthesis Summary]");
    // Stub fixture JSON has no operator tokens → full chain at HIGH
    // → meta-synthesis=HIGH, all-strong syntheses, stable trajectory,
    // no inhibitors/risks/decay, capstone summary.
    expect(ms2.textContent).toContain("[Meta-Synthesis Level]\nHIGH");
    expect(ms2.textContent).toContain("[Coherence-Synthesis]\nstrong synthesis");
    expect(ms2.textContent).toContain("[Stability-Synthesis]\nstrong synthesis");
    expect(ms2.textContent).toContain("[Resilience-Synthesis]\nstrong synthesis");
    expect(ms2.textContent).toContain("[Immunity-Synthesis]\nstrong synthesis");
    expect(ms2.textContent).toContain("[Integration-Synthesis]\nstrong integration synthesis");
    expect(ms2.textContent).toContain("[Alignment-Synthesis]\nstrong alignment synthesis");
    expect(ms2.textContent).toContain("[Pattern-Synthesis]\nstable pattern synthesis");
    expect(ms2.textContent).toContain("[Meta-Synthesis Trajectory]\nhigh → high → high (stable)");
    expect(ms2.textContent).toContain("[Meta-Synthesis Inhibitors]\n(none)");
    expect(ms2.textContent).toContain("[Meta-Synthesis Risks]\n(none)");
    expect(ms2.textContent).toContain("[Meta-Synthesis Decay]\n(none)");
    expect(ms2.textContent).toContain("Operator meta-synthesis is strong, with high coherence-, resilience-, and integration-synthesis.");
  });

  it("Card 85 — renders the Operator Meta-Consolidation section with all 16 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const mco = screen.getByTestId("oc-operator-meta-consolidation");
    expect(mco).toBeInTheDocument();
    expect(mco.textContent).toContain("=== Operator Meta-Consolidation ===");
    expect(mco.textContent).toContain("[Meta-Consolidation Level]");
    expect(mco.textContent).toContain("[Pattern-Consolidation]");
    expect(mco.textContent).toContain("[Stability-Consolidation]");
    expect(mco.textContent).toContain("[Resilience-Consolidation]");
    expect(mco.textContent).toContain("[Immunity-Consolidation]");
    expect(mco.textContent).toContain("[Integration-Consolidation]");
    expect(mco.textContent).toContain("[Alignment-Consolidation]");
    expect(mco.textContent).toContain("[Coherence-Consolidation]");
    expect(mco.textContent).toContain("[Synthesis-Consolidation]");
    expect(mco.textContent).toContain("[Meta-Consolidation Trajectory]");
    expect(mco.textContent).toContain("[Meta-Consolidation Drivers]");
    expect(mco.textContent).toContain("[Meta-Consolidation Inhibitors]");
    expect(mco.textContent).toContain("[Meta-Consolidation Risks]");
    expect(mco.textContent).toContain("[Meta-Consolidation Reinforcement]");
    expect(mco.textContent).toContain("[Meta-Consolidation Decay]");
    expect(mco.textContent).toContain("[Operator Meta-Consolidation Summary]");
    // Stub fixture JSON has no operator tokens → full chain at HIGH
    // → meta-consolidation=HIGH, all-strong consolidations, stable
    // trajectory, no inhibitors/risks/decay, steady summary.
    expect(mco.textContent).toContain("[Meta-Consolidation Level]\nHIGH");
    expect(mco.textContent).toContain("[Pattern-Consolidation]\nstrong consolidation");
    expect(mco.textContent).toContain("[Stability-Consolidation]\nstrong consolidation");
    expect(mco.textContent).toContain("[Resilience-Consolidation]\nstrong consolidation");
    expect(mco.textContent).toContain("[Immunity-Consolidation]\nstrong consolidation");
    expect(mco.textContent).toContain("[Integration-Consolidation]\nstrong integration consolidation");
    expect(mco.textContent).toContain("[Alignment-Consolidation]\nstrong alignment consolidation");
    expect(mco.textContent).toContain("[Coherence-Consolidation]\nstrong coherence consolidation");
    expect(mco.textContent).toContain("[Synthesis-Consolidation]\nstrong synthesis consolidation");
    expect(mco.textContent).toContain("[Meta-Consolidation Trajectory]\nhigh → high → high (stable)");
    expect(mco.textContent).toContain("[Meta-Consolidation Inhibitors]\n(none)");
    expect(mco.textContent).toContain("[Meta-Consolidation Risks]\n(none)");
    expect(mco.textContent).toContain("[Meta-Consolidation Decay]\n(none)");
    expect(mco.textContent).toContain("Operator meta-consolidation is steady, with strong pattern-, resilience-, and synthesis-consolidation.");
  });

  it("Card 86 — renders the Operator Meta-Compression section with all 17 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const mcp = screen.getByTestId("oc-operator-meta-compression");
    expect(mcp).toBeInTheDocument();
    expect(mcp.textContent).toContain("=== Operator Meta-Compression ===");
    expect(mcp.textContent).toContain("[Meta-Compression Level]");
    expect(mcp.textContent).toContain("[Pattern-Compression]");
    expect(mcp.textContent).toContain("[Stability-Compression]");
    expect(mcp.textContent).toContain("[Resilience-Compression]");
    expect(mcp.textContent).toContain("[Immunity-Compression]");
    expect(mcp.textContent).toContain("[Integration-Compression]");
    expect(mcp.textContent).toContain("[Alignment-Compression]");
    expect(mcp.textContent).toContain("[Coherence-Compression]");
    expect(mcp.textContent).toContain("[Synthesis-Compression]");
    expect(mcp.textContent).toContain("[Consolidation-Compression]");
    expect(mcp.textContent).toContain("[Meta-Compression Trajectory]");
    expect(mcp.textContent).toContain("[Meta-Compression Drivers]");
    expect(mcp.textContent).toContain("[Meta-Compression Inhibitors]");
    expect(mcp.textContent).toContain("[Meta-Compression Risks]");
    expect(mcp.textContent).toContain("[Meta-Compression Reinforcement]");
    expect(mcp.textContent).toContain("[Meta-Compression Decay]");
    expect(mcp.textContent).toContain("[Operator Meta-Compression Summary]");
    // Stub fixture JSON has no operator tokens → full chain at HIGH
    // → meta-compression=HIGH, all-strong compressions, stable
    // trajectory, no inhibitors/risks/decay, steady summary.
    expect(mcp.textContent).toContain("[Meta-Compression Level]\nHIGH");
    expect(mcp.textContent).toContain("[Pattern-Compression]\nstrong compression");
    expect(mcp.textContent).toContain("[Stability-Compression]\nstrong compression");
    expect(mcp.textContent).toContain("[Resilience-Compression]\nstrong compression");
    expect(mcp.textContent).toContain("[Immunity-Compression]\nstrong compression");
    expect(mcp.textContent).toContain("[Integration-Compression]\nstrong integration compression");
    expect(mcp.textContent).toContain("[Alignment-Compression]\nstrong alignment compression");
    expect(mcp.textContent).toContain("[Coherence-Compression]\nstrong coherence compression");
    expect(mcp.textContent).toContain("[Synthesis-Compression]\nstrong synthesis compression");
    expect(mcp.textContent).toContain("[Consolidation-Compression]\nstrong consolidation compression");
    expect(mcp.textContent).toContain("[Meta-Compression Trajectory]\nhigh → high → high (stable)");
    expect(mcp.textContent).toContain("[Meta-Compression Inhibitors]\n(none)");
    expect(mcp.textContent).toContain("[Meta-Compression Risks]\n(none)");
    expect(mcp.textContent).toContain("[Meta-Compression Decay]\n(none)");
    expect(mcp.textContent).toContain("Operator meta-compression is steady, with strong pattern-, resilience-, and synthesis-compression.");
  });

  it("Card 87 — renders the Operator Meta-Reduction section with all 18 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const mrd = screen.getByTestId("oc-operator-meta-reduction");
    expect(mrd).toBeInTheDocument();
    expect(mrd.textContent).toContain("=== Operator Meta-Reduction ===");
    expect(mrd.textContent).toContain("[Meta-Reduction Level]");
    expect(mrd.textContent).toContain("[Pattern-Reduction]");
    expect(mrd.textContent).toContain("[Stability-Reduction]");
    expect(mrd.textContent).toContain("[Resilience-Reduction]");
    expect(mrd.textContent).toContain("[Immunity-Reduction]");
    expect(mrd.textContent).toContain("[Integration-Reduction]");
    expect(mrd.textContent).toContain("[Alignment-Reduction]");
    expect(mrd.textContent).toContain("[Coherence-Reduction]");
    expect(mrd.textContent).toContain("[Synthesis-Reduction]");
    expect(mrd.textContent).toContain("[Consolidation-Reduction]");
    expect(mrd.textContent).toContain("[Compression-Reduction]");
    expect(mrd.textContent).toContain("[Meta-Reduction Trajectory]");
    expect(mrd.textContent).toContain("[Meta-Reduction Drivers]");
    expect(mrd.textContent).toContain("[Meta-Reduction Inhibitors]");
    expect(mrd.textContent).toContain("[Meta-Reduction Risks]");
    expect(mrd.textContent).toContain("[Meta-Reduction Reinforcement]");
    expect(mrd.textContent).toContain("[Meta-Reduction Decay]");
    expect(mrd.textContent).toContain("[Operator Meta-Reduction Summary]");
    // Stub fixture JSON has no operator tokens → full chain at HIGH
    // → meta-reduction=HIGH, all-strong reductions, stable trajectory,
    // no inhibitors/risks/decay, steady summary.
    expect(mrd.textContent).toContain("[Meta-Reduction Level]\nHIGH");
    expect(mrd.textContent).toContain("[Pattern-Reduction]\nstrong reduction");
    expect(mrd.textContent).toContain("[Stability-Reduction]\nstrong reduction");
    expect(mrd.textContent).toContain("[Resilience-Reduction]\nstrong reduction");
    expect(mrd.textContent).toContain("[Immunity-Reduction]\nstrong reduction");
    expect(mrd.textContent).toContain("[Integration-Reduction]\nstrong integration reduction");
    expect(mrd.textContent).toContain("[Alignment-Reduction]\nstrong alignment reduction");
    expect(mrd.textContent).toContain("[Coherence-Reduction]\nstrong coherence reduction");
    expect(mrd.textContent).toContain("[Synthesis-Reduction]\nstrong synthesis reduction");
    expect(mrd.textContent).toContain("[Consolidation-Reduction]\nstrong consolidation reduction");
    expect(mrd.textContent).toContain("[Compression-Reduction]\nstrong compression reduction");
    expect(mrd.textContent).toContain("[Meta-Reduction Trajectory]\nhigh → high → high (stable)");
    expect(mrd.textContent).toContain("[Meta-Reduction Inhibitors]\n(none)");
    expect(mrd.textContent).toContain("[Meta-Reduction Risks]\n(none)");
    expect(mrd.textContent).toContain("[Meta-Reduction Decay]\n(none)");
    expect(mrd.textContent).toContain("Operator meta-reduction is steady, with strong pattern-, resilience-, and synthesis-reduction.");
  });

  it("Card 88 — renders the Operator Meta-Extraction section with all 19 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const mex = screen.getByTestId("oc-operator-meta-extraction");
    expect(mex).toBeInTheDocument();
    expect(mex.textContent).toContain("=== Operator Meta-Extraction ===");
    expect(mex.textContent).toContain("[Meta-Extraction Level]");
    expect(mex.textContent).toContain("[Pattern-Extraction]");
    expect(mex.textContent).toContain("[Stability-Extraction]");
    expect(mex.textContent).toContain("[Resilience-Extraction]");
    expect(mex.textContent).toContain("[Immunity-Extraction]");
    expect(mex.textContent).toContain("[Integration-Extraction]");
    expect(mex.textContent).toContain("[Alignment-Extraction]");
    expect(mex.textContent).toContain("[Coherence-Extraction]");
    expect(mex.textContent).toContain("[Synthesis-Extraction]");
    expect(mex.textContent).toContain("[Consolidation-Extraction]");
    expect(mex.textContent).toContain("[Compression-Extraction]");
    expect(mex.textContent).toContain("[Reduction-Extraction]");
    expect(mex.textContent).toContain("[Meta-Extraction Trajectory]");
    expect(mex.textContent).toContain("[Meta-Extraction Drivers]");
    expect(mex.textContent).toContain("[Meta-Extraction Inhibitors]");
    expect(mex.textContent).toContain("[Meta-Extraction Risks]");
    expect(mex.textContent).toContain("[Meta-Extraction Reinforcement]");
    expect(mex.textContent).toContain("[Meta-Extraction Decay]");
    expect(mex.textContent).toContain("[Operator Meta-Extraction Summary]");
    // Stub fixture JSON has no operator tokens → full chain at HIGH
    // → meta-extraction=HIGH, all-strong extractions, stable
    // trajectory, no inhibitors/risks/decay, steady summary.
    expect(mex.textContent).toContain("[Meta-Extraction Level]\nHIGH");
    expect(mex.textContent).toContain("[Pattern-Extraction]\nstrong extraction");
    expect(mex.textContent).toContain("[Stability-Extraction]\nstrong extraction");
    expect(mex.textContent).toContain("[Resilience-Extraction]\nstrong extraction");
    expect(mex.textContent).toContain("[Immunity-Extraction]\nstrong extraction");
    expect(mex.textContent).toContain("[Integration-Extraction]\nstrong integration extraction");
    expect(mex.textContent).toContain("[Alignment-Extraction]\nstrong alignment extraction");
    expect(mex.textContent).toContain("[Coherence-Extraction]\nstrong coherence extraction");
    expect(mex.textContent).toContain("[Synthesis-Extraction]\nstrong synthesis extraction");
    expect(mex.textContent).toContain("[Consolidation-Extraction]\nstrong consolidation extraction");
    expect(mex.textContent).toContain("[Compression-Extraction]\nstrong compression extraction");
    expect(mex.textContent).toContain("[Reduction-Extraction]\nstrong reduction extraction");
    expect(mex.textContent).toContain("[Meta-Extraction Trajectory]\nhigh → high → high (stable)");
    expect(mex.textContent).toContain("[Meta-Extraction Inhibitors]\n(none)");
    expect(mex.textContent).toContain("[Meta-Extraction Risks]\n(none)");
    expect(mex.textContent).toContain("[Meta-Extraction Decay]\n(none)");
    expect(mex.textContent).toContain("Operator meta-extraction is steady, with strong pattern-, resilience-, and synthesis-extraction.");
  });

  it("Card 89 — renders the Operator Meta-Distillation section with all 20 sub-blocks", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const mds = screen.getByTestId("oc-operator-meta-distillation");
    expect(mds).toBeInTheDocument();
    expect(mds.textContent).toContain("=== Operator Meta-Distillation ===");
    expect(mds.textContent).toContain("[Meta-Distillation Level]");
    expect(mds.textContent).toContain("[Pattern-Distillation]");
    expect(mds.textContent).toContain("[Stability-Distillation]");
    expect(mds.textContent).toContain("[Resilience-Distillation]");
    expect(mds.textContent).toContain("[Immunity-Distillation]");
    expect(mds.textContent).toContain("[Integration-Distillation]");
    expect(mds.textContent).toContain("[Alignment-Distillation]");
    expect(mds.textContent).toContain("[Coherence-Distillation]");
    expect(mds.textContent).toContain("[Synthesis-Distillation]");
    expect(mds.textContent).toContain("[Consolidation-Distillation]");
    expect(mds.textContent).toContain("[Compression-Distillation]");
    expect(mds.textContent).toContain("[Reduction-Distillation]");
    expect(mds.textContent).toContain("[Extraction-Distillation]");
    expect(mds.textContent).toContain("[Meta-Distillation Trajectory]");
    expect(mds.textContent).toContain("[Meta-Distillation Drivers]");
    expect(mds.textContent).toContain("[Meta-Distillation Inhibitors]");
    expect(mds.textContent).toContain("[Meta-Distillation Risks]");
    expect(mds.textContent).toContain("[Meta-Distillation Reinforcement]");
    expect(mds.textContent).toContain("[Meta-Distillation Decay]");
    expect(mds.textContent).toContain("[Operator Meta-Distillation Summary]");
    // Stub fixture JSON has no operator tokens → full chain at HIGH
    // → meta-distillation=HIGH, all-strong distillations, stable
    // trajectory, no inhibitors/risks/decay, capstone summary.
    expect(mds.textContent).toContain("[Meta-Distillation Level]\nHIGH");
    expect(mds.textContent).toContain("[Pattern-Distillation]\nstrong distillation");
    expect(mds.textContent).toContain("[Stability-Distillation]\nstrong distillation");
    expect(mds.textContent).toContain("[Resilience-Distillation]\nstrong distillation");
    expect(mds.textContent).toContain("[Immunity-Distillation]\nstrong distillation");
    expect(mds.textContent).toContain("[Integration-Distillation]\nstrong integration distillation");
    expect(mds.textContent).toContain("[Alignment-Distillation]\nstrong alignment distillation");
    expect(mds.textContent).toContain("[Coherence-Distillation]\nstrong coherence distillation");
    expect(mds.textContent).toContain("[Synthesis-Distillation]\nstrong synthesis distillation");
    expect(mds.textContent).toContain("[Consolidation-Distillation]\nstrong consolidation distillation");
    expect(mds.textContent).toContain("[Compression-Distillation]\nstrong compression distillation");
    expect(mds.textContent).toContain("[Reduction-Distillation]\nstrong reduction distillation");
    expect(mds.textContent).toContain("[Extraction-Distillation]\nstrong extraction distillation");
    expect(mds.textContent).toContain("[Meta-Distillation Trajectory]\nhigh → high → high (stable)");
    expect(mds.textContent).toContain("[Meta-Distillation Inhibitors]\n(none)");
    expect(mds.textContent).toContain("[Meta-Distillation Risks]\n(none)");
    expect(mds.textContent).toContain("[Meta-Distillation Decay]\n(none)");
    expect(mds.textContent).toContain("Operator meta-distillation is strong, with strong pattern-, resilience-, and synthesis-distillation.");
  });

  it("Card 90 — renders the Operator Meta-Essence section with all 20 sub-blocks (capstone)", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const mes = screen.getByTestId("oc-operator-meta-essence");
    expect(mes).toBeInTheDocument();
    expect(mes.textContent).toContain("=== Operator Meta-Essence ===");
    expect(mes.textContent).toContain("[Meta-Essence Level]");
    expect(mes.textContent).toContain("[Pattern-Essence]");
    expect(mes.textContent).toContain("[Stability-Essence]");
    expect(mes.textContent).toContain("[Resilience-Essence]");
    expect(mes.textContent).toContain("[Immunity-Essence]");
    expect(mes.textContent).toContain("[Integration-Essence]");
    expect(mes.textContent).toContain("[Alignment-Essence]");
    expect(mes.textContent).toContain("[Coherence-Essence]");
    expect(mes.textContent).toContain("[Synthesis-Essence]");
    expect(mes.textContent).toContain("[Consolidation-Essence]");
    expect(mes.textContent).toContain("[Compression-Essence]");
    expect(mes.textContent).toContain("[Reduction-Essence]");
    expect(mes.textContent).toContain("[Extraction-Essence]");
    expect(mes.textContent).toContain("[Distillation-Essence]");
    expect(mes.textContent).toContain("[Meta-Essence Trajectory]");
    expect(mes.textContent).toContain("[Meta-Essence Drivers]");
    expect(mes.textContent).toContain("[Meta-Essence Inhibitors]");
    expect(mes.textContent).toContain("[Meta-Essence Risks]");
    expect(mes.textContent).toContain("[Meta-Essence Reinforcement]");
    expect(mes.textContent).toContain("[Meta-Essence Decay]");
    expect(mes.textContent).toContain("[Operator Meta-Essence Summary]");
    // Stub fixture JSON has no operator tokens → full chain at HIGH
    // → terminal capstone elevates meta-essence to VERY-HIGH, all-strong
    // essences, stable trajectory, no inhibitors/risks/decay, capstone
    // summary.
    expect(mes.textContent).toContain("[Meta-Essence Level]\nVERY-HIGH");
    expect(mes.textContent).toContain("[Pattern-Essence]\nstrong essence");
    expect(mes.textContent).toContain("[Stability-Essence]\nstrong essence");
    expect(mes.textContent).toContain("[Resilience-Essence]\nstrong essence");
    expect(mes.textContent).toContain("[Immunity-Essence]\nstrong essence");
    expect(mes.textContent).toContain("[Integration-Essence]\nstrong integration essence");
    expect(mes.textContent).toContain("[Alignment-Essence]\nstrong alignment essence");
    expect(mes.textContent).toContain("[Coherence-Essence]\nstrong coherence essence");
    expect(mes.textContent).toContain("[Synthesis-Essence]\nstrong synthesis essence");
    expect(mes.textContent).toContain("[Consolidation-Essence]\nstrong consolidation essence");
    expect(mes.textContent).toContain("[Compression-Essence]\nstrong compression essence");
    expect(mes.textContent).toContain("[Reduction-Essence]\nstrong reduction essence");
    expect(mes.textContent).toContain("[Extraction-Essence]\nstrong extraction essence");
    expect(mes.textContent).toContain("[Distillation-Essence]\nstrong distillation essence");
    expect(mes.textContent).toContain("[Meta-Essence Trajectory]\nvery-high → very-high → very-high (stable)");
    expect(mes.textContent).toContain("[Meta-Essence Inhibitors]\n(none)");
    expect(mes.textContent).toContain("[Meta-Essence Risks]\n(none)");
    expect(mes.textContent).toContain("[Meta-Essence Decay]\n(none)");
    expect(mes.textContent).toContain("Operator meta-essence is strong, with strong pattern-, resilience-, and synthesis-essence.");
  });

  it("Phase 6 — renders the Operator Superstructure section from the meta-operator outputs", () => {
    renderConsole();
    const textarea = screen.getByTestId("oc-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: JSON.stringify(STUB_CONTEXT) } });
    fireEvent.click(screen.getByTestId("oc-load"));

    const sup = screen.getByTestId("oc-operator-superstructure");
    expect(sup).toBeInTheDocument();
    expect(sup.textContent).toContain("=== Operator Superstructure ===");
    expect(sup.textContent).toContain("[Pattern Identity]");
    expect(sup.textContent).toContain("[Integration Identity]");
    expect(sup.textContent).toContain("[Coherence Identity]");
    expect(sup.textContent).toContain("[Essence Invariant]");
    expect(sup.textContent).toContain("[Operator Identity]");
    // Stub fixture has no operator tokens → the whole meta chain sits at
    // HIGH (essence elevates to VERY-HIGH), so the re-derived identities
    // read: pattern strength 0.67, integration/coherence 0.67, and the
    // essence invariant carries the VERY-HIGH essence level (0.83).
    expect(sup.textContent).toContain("[Pattern Identity]\npattern:0.67");
    expect(sup.textContent).toContain("[Integration Identity]\nint-0.67-align-0.67");
    expect(sup.textContent).toContain("[Coherence Identity]\ncoh-0.67-drift-0.67-load-0.67");
    expect(sup.textContent).toContain("[Essence Invariant]\nstable-0.67-ess-0.83");
    expect(sup.textContent).toContain("[Operator Identity]\nclarityos-operator:s");
  });
});
