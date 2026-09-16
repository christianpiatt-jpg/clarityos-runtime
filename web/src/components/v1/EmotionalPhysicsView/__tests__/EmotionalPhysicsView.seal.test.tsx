/**
 * #303 A1 A3 · #306 -- the thread panel's physics view: a map and a
 * projection, the ring beside the model line, the seal in turns; on a parse
 * miss two facts about the reply and never the reply; a list field that is
 * not a list reads a dash, and a list never reads "[n]".
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import EmotionalPhysicsView from "../EmotionalPhysicsView";

const READ = {
  field_curvature: { intensity: "medium", dominant_forces: ["a", "b", "c", "d", "e", "f"], notes: "n1" },
  edge_pressure: { signal_clarity: "high", perceived_posture: "defensive", notes: "n2" },
  relational_primitives: { trust: "fluctuating" },
  external_expression: {
    risk_if_unchanged: "drift continues",
    recommended_posture: ["clarify_intent"],
    counsel: { message_guidance: ["say it plainly"], next_step: "send three lines" },
  },
  _meta: { model_id: "anthropic:m", ts_ms: 5, parse_error: null, ring: "meaning", window_last_message: 12 },
};

describe("#303 A1/A3 -- a map, a projection, the ring, the seal", () => {
  it("renders the three map layers and ONE projection field; counsel is not on the glass", () => {
    render(<EmotionalPhysicsView response={READ as never} text="t" />);
    expect(screen.getByTestId("layer-field_curvature")).toBeInTheDocument();
    expect(screen.getByTestId("layer-edge_pressure")).toBeInTheDocument();
    expect(screen.getByTestId("bearings")).toBeInTheDocument();
    expect(screen.getByTestId("layer-external_expression")).toHaveTextContent("External expression · physics · model-read");
    expect(screen.getByTestId("projection-risk_if_unchanged")).toHaveTextContent("drift continues");
    expect(screen.getByTitle("risk_if_unchanged")).toHaveTextContent("if nothing changes");
    expect(screen.queryByText(/say it plainly/)).toBeNull();
    expect(screen.queryByText(/send three lines/)).toBeNull();
    expect(screen.queryByText(/clarify_intent/)).toBeNull();
  });

  it("the ring rides beside the model line, and the seal is a turn", () => {
    render(<EmotionalPhysicsView response={READ as never} text="t" />);
    expect(screen.getByText("model: anthropic:m · ring: meaning")).toBeInTheDocument();
    expect(screen.getByTestId("physics-sealed-at")).toHaveTextContent("sealed at turn 12");
  });

  it("no window on the wire: a dash, never a date", () => {
    render(<EmotionalPhysicsView response={{ ...READ, _meta: { model_id: "m", ts_ms: 5, parse_error: null } } as never} text="t" />);
    expect(screen.getByTestId("physics-sealed-at")).toHaveTextContent("sealed at turn —");
    expect(screen.getByText("model: m")).toBeInTheDocument();
  });
});

describe("#306 -- a parse miss reports two facts; list fields", () => {
  it("raw_len and refusal_shape ride on the parse-error line; the text never does", () => {
    const miss = {
      field_curvature: {}, edge_pressure: {}, relational_primitives: {}, external_expression: {},
      _meta: { model_id: "m", ts_ms: 5, parse_error: "could not parse JSON from model response", raw_len: 1234, refusal_shape: true },
    };
    render(<EmotionalPhysicsView response={miss as never} text="t" />);
    const line = screen.getByTestId("physics-parse-error");
    expect(line).toHaveTextContent("parse error: could not parse JSON from model response · raw 1,234 chars · refusal shape");
  });

  it("a non-list under a list field reads a dash; a long list reads its members, never '[n]'", () => {
    render(<EmotionalPhysicsView response={READ as never} text="t" />);
    const posture = screen.getByTitle("perceived_posture").nextElementSibling;
    expect(posture).toHaveTextContent("—");
    const forces = screen.getByTitle("dominant_forces").nextElementSibling;
    expect(forces).toHaveTextContent("a, b, c, d, e, f");
    expect(screen.queryByText(/\[6\]/)).toBeNull();
  });
});
