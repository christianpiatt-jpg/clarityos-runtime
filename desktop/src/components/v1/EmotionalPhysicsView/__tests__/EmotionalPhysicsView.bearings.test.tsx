/**
 * #167b / rule #167c -- the desktop physics view reads like the web: five
 * NAMED bearing rows (one missing, one "unclear"), the stop mark on a
 * non-end_turn reply, and the generic loop never prints the five keys.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import EmotionalPhysicsView from "../EmotionalPhysicsView";
import type { EmotionalPhysicsResponse } from "../../../../lib/emotionalPhysics";

const RESP = {
  field_curvature: { intensity: "medium", notes: "n1" },
  edge_pressure: { signal_clarity: "mixed", notes: "n2" },
  relational_primitives: { trust: "low", alignment: "unclear", boundary: "contested", agency: "constrained", dominant_pattern: ["boundary_uncertainty", "withdrawal"], notes: "n3" },
  external_expression: { recommended_posture: ["clarify"], notes: "n4" },
  _meta: { model_id: "anthropic:claude-haiku-4-5-20251001", ts_ms: 1, parse_error: null,
           stop_reason: "max_tokens", stop_class: "cut" },
} as unknown as EmotionalPhysicsResponse;

describe("EmotionalPhysicsView -- five bearings and the stop mark (#167b)", () => {
  it("\u2605 five named rows: a missing bearing reads a dash, unclear reads its word", () => {
    render(<EmotionalPhysicsView response={RESP} />);
    expect(screen.getByTestId("bearing-trust")).toHaveTextContent("low");
    expect(screen.getByTestId("bearing-alignment")).toHaveTextContent("unclear");
    expect(screen.getByTestId("bearing-boundary")).toHaveTextContent("contested");
    expect(screen.getByTestId("bearing-agency")).toHaveTextContent("constrained");
    expect(screen.getByTestId("bearing-distance")).toHaveTextContent("\u2014");
    expect(screen.getByTitle("trust")).toHaveTextContent("trust");
    expect(screen.getByTitle("relational_primitives")).toHaveTextContent("relational primitives");
    // the pattern rides beside the five (the web's sixth row)
    expect(screen.getByTestId("bearing-pattern")).toHaveTextContent("boundary_uncertainty, withdrawal");
  });
  it("\u2605 the stop mark only when the stop is not end_turn", () => {
    render(<EmotionalPhysicsView response={RESP} />);
    expect(screen.getByTestId("stop-mark")).toHaveTextContent("stopped early: max_tokens");
  });
  it("\u2605 #196 -- a normal OpenAI \"stop\" and an unknown word mark nothing", () => {
    const normal = { ...RESP, _meta: { ...RESP._meta, stop_reason: "stop", stop_class: "normal" } } as EmotionalPhysicsResponse;
    const { unmount } = render(<EmotionalPhysicsView response={normal} />);
    expect(screen.queryByTestId("stop-mark")).toBeNull();
    unmount();
    const unknown = { ...RESP, _meta: { ...RESP._meta, stop_reason: "tool_use", stop_class: "unknown" } } as EmotionalPhysicsResponse;
    render(<EmotionalPhysicsView response={unknown} />);
    expect(screen.queryByTestId("stop-mark")).toBeNull();
  });
  it("end_turn and a mock (absent) -> no mark", () => {
    const ok = { ...RESP, _meta: { ...RESP._meta, stop_reason: "end_turn", stop_class: "normal" } } as EmotionalPhysicsResponse;
    const { unmount } = render(<EmotionalPhysicsView response={ok} />);
    expect(screen.queryByTestId("stop-mark")).toBeNull();
    unmount();
    const mock = { ...RESP, _meta: { model_id: null, ts_ms: 1, parse_error: null } } as EmotionalPhysicsResponse;
    render(<EmotionalPhysicsView response={mock} />);
    expect(screen.queryByTestId("stop-mark")).toBeNull();
  });
  it("rule #167c -- the generic loop does not print the five keys a second time", () => {
    render(<EmotionalPhysicsView response={RESP} />);
    expect(screen.getAllByTestId(/^bearing-/)).toHaveLength(6);   // five bearings + the pattern row
    expect(screen.queryAllByText(/^trust$/)).toHaveLength(1);       // the one named row's label
    expect(screen.getByTestId("bearings-block")).toHaveTextContent("n3");   // the notes stay prose
  });
});
