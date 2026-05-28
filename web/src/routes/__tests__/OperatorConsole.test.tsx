// Card 40 — OperatorConsole smoke test.
//
// Renders the operator console, pastes a minimal valid multi-run
// context JSON, clicks Load, and asserts the four diagnostic panes
// populate with non-empty JSON content.
//
// Not a logic test — Cards 28-37 already pin every helper's
// behaviour. This just verifies the route wires the textarea + Load
// button to the Card 39 EngineV1OperatorAPI correctly.

import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
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
});
