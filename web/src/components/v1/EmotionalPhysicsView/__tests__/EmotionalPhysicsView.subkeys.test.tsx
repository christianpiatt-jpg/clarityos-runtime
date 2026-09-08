/**
 * #180a (j) -- the physics layers' sub-keys render CT-1's words (labels.ts)
 * with the internal key in a title; the layer captions carry the
 * instrument "physics · model-read".
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("../../../../lib/emotionalPhysics", async () => {
  const actual = await vi.importActual<typeof import("../../../../lib/emotionalPhysics")>(
    "../../../../lib/emotionalPhysics",
  );
  return { ...actual, analyzeEmotionalPhysics: vi.fn() };
});

import EmotionalPhysicsView from "../EmotionalPhysicsView";
import { labelFor } from "../../../../lib/labels";

const READING = {
  field_curvature: { intensity: 0.8, gradient_direction: "inward", stability: "low", dominant_forces: ["shame"], notes: "n1" },
  edge_pressure: { signal_clarity: "high", signal_intensity: 0.6, coherence: "partial", perceived_posture: "defensive", risk_of_misread: "moderate", notes: "n2" },
  relational_primitives: { trust: "fluctuating" },
  external_expression: { unknown_key: "raw" },
  _meta: { model_id: "anthropic:claude-haiku-4-5-20251001", ts_ms: Date.now(), parse_error: null, stop_reason: "end_turn" },
};

describe("EmotionalPhysicsView -- sub-keys are CT-1's words (#180a j)", () => {
  it("the nine words, each with its key in the title", () => {
    render(<EmotionalPhysicsView response={READING as never} text="t" />);
    expect(screen.getByTitle("intensity")).toHaveTextContent("how strong");
    expect(screen.getByTitle("gradient_direction")).toHaveTextContent("which way");
    expect(screen.getByTitle("stability")).toHaveTextContent("steady");
    expect(screen.getByTitle("dominant_forces")).toHaveTextContent("what's pushing");
    expect(screen.getByTitle("signal_clarity")).toHaveTextContent("how clear");
    expect(screen.getByTitle("signal_intensity")).toHaveTextContent("how loud");
    expect(screen.getByTitle("coherence")).toHaveTextContent("holding together");
    expect(screen.getByTitle("perceived_posture")).toHaveTextContent("leaning");
    expect(screen.getByTitle("risk_of_misread")).toHaveTextContent("chance of misread");
    // the raw names no longer show as text
    expect(screen.queryByText("signal_clarity")).toBeNull();
    expect(screen.queryByText("gradient_direction")).toBeNull();
    // an unknown key shows itself, never blank
    expect(screen.getByTitle("unknown_key")).toHaveTextContent("unknown_key");
  });

  it("the layer captions carry the instrument and the layer key", () => {
    render(<EmotionalPhysicsView response={READING as never} text="t" />);
    expect(screen.getByTestId("layer-field_curvature")).toHaveTextContent("Field curvature · physics · model-read");
    expect(screen.getByTestId("layer-edge_pressure")).toHaveTextContent("Edge pressure · physics · model-read");
    expect(screen.getByTestId("layer-external_expression")).toHaveTextContent("External expression · physics · model-read");
    expect(screen.getByTitle("field_curvature")).toBeInTheDocument();
  });

  it("labels.ts carries the nine, all on the physics instrument", () => {
    for (const k of ["signal_clarity", "signal_intensity", "coherence", "perceived_posture",
      "risk_of_misread", "intensity", "gradient_direction", "stability", "dominant_forces"]) {
      expect(labelFor(k).instrument).toBe("physics · model-read");
      expect(labelFor(k).word).not.toBe(k);
    }
  });
});
