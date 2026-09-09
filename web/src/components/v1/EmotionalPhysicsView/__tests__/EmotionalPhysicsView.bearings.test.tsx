/**
 * #162 (a)(b) -- five NAMED bearing rows on the physics panel; the stop mark.
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

function reading(
  rp: Record<string, unknown>,
  stop: string | null | undefined = "end_turn",
  stopClass: string | null | undefined = "normal",
) {
  return {
    field_curvature: { intensity: "high", notes: "n" },
    edge_pressure: {},
    relational_primitives: rp,
    external_expression: {},
    _meta: { model_id: "anthropic:claude-haiku-4-5-20251001", ts_ms: Date.now(), parse_error: null,
             stop_reason: stop, stop_class: stopClass },
  } as never;
}

const FULL = {
  trust: "fluctuating", alignment: "partially_aligned", boundary: "soft", agency: "partial",
  distance: "increasing", dominant_pattern: ["boundary_uncertainty"], notes: "boundary needs naming",
};

describe("EmotionalPhysicsView -- the five bearings are named rows", () => {
  it("a full reading: five rows, the instrument on the label, notes as prose", () => {
    render(<EmotionalPhysicsView response={reading(FULL)} text="t" />);
    expect(screen.getByTestId("bearing-trust")).toHaveTextContent("fluctuating");
    expect(screen.getByTestId("bearing-alignment")).toHaveTextContent("partially_aligned");
    expect(screen.getByTestId("bearing-boundary")).toHaveTextContent("soft");
    expect(screen.getByTestId("bearing-agency")).toHaveTextContent("partial");
    expect(screen.getByTestId("bearing-distance")).toHaveTextContent("increasing");
    expect(screen.getByTestId("bearings")).toHaveTextContent("physics \u00b7 model-read");
    expect(screen.getByTestId("bearings")).toHaveTextContent("boundary needs naming");
    // the internal key rides in a title attribute, the word in the row
    expect(screen.getByTitle("trust")).toBeInTheDocument();
    expect(screen.queryByText("notes")).toBeNull();
  });
  it("a missing key renders an em dash; unclear renders the word", () => {
    render(<EmotionalPhysicsView response={reading({ trust: "unclear", boundary: "clear" })} text="t" />);
    expect(screen.getByTestId("bearing-trust")).toHaveTextContent("unclear");
    expect(screen.getByTestId("bearing-distance")).toHaveTextContent("\u2014");
    expect(screen.getByTestId("bearing-distance")).toHaveAttribute("data-missing", "true");
    expect(screen.getByTestId("bearing-agency")).toHaveTextContent("\u2014");
  });
  it("an empty layer after a parse failure is five dashes, still named", () => {
    render(<EmotionalPhysicsView response={reading({})} text="t" />);
    for (const k of ["trust", "alignment", "boundary", "agency", "distance"]) {
      expect(screen.getByTestId(`bearing-${k}`)).toHaveTextContent("\u2014");
    }
  });
});

describe("EmotionalPhysicsView -- the stop mark", () => {
  it("#196 -- renders only when the vocabulary called it a cut, and NAMES the raw token", () => {
    const { unmount } = render(<EmotionalPhysicsView response={reading(FULL, "max_tokens", "cut")} text="t" />);
    expect(screen.getByTestId("stop-mark")).toHaveTextContent("max_tokens");
    unmount();
    render(<EmotionalPhysicsView response={reading(FULL, "end_turn", "normal")} text="t" />);
    expect(screen.queryByTestId("stop-mark")).toBeNull();
  });
  it("\u2605 #196 -- a NORMAL OpenAI \"stop\" and Gemini \"STOP\" mark nothing", () => {
    const { unmount } = render(<EmotionalPhysicsView response={reading(FULL, "stop", "normal")} text="t" />);
    expect(screen.queryByTestId("stop-mark")).toBeNull();
    unmount();
    render(<EmotionalPhysicsView response={reading(FULL, "STOP", "normal")} text="t" />);
    expect(screen.queryByTestId("stop-mark")).toBeNull();
  });
  it("#196 -- an UNKNOWN word renders nothing: not a cut, not a completion", () => {
    render(<EmotionalPhysicsView response={reading(FULL, "tool_use", "unknown")} text="t" />);
    expect(screen.queryByTestId("stop-mark")).toBeNull();
  });
  it("a mock (null) or an absent stop_reason is not a cut", () => {
    const { unmount } = render(<EmotionalPhysicsView response={reading(FULL, null, null)} text="t" />);
    expect(screen.queryByTestId("stop-mark")).toBeNull();
    unmount();
    render(<EmotionalPhysicsView response={reading(FULL, undefined, undefined)} text="t" />);
    expect(screen.queryByTestId("stop-mark")).toBeNull();
  });
});
