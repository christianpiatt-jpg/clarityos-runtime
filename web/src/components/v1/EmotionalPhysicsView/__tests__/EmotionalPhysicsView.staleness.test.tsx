/**
 * The Physics block must report when it ANALYSED, not when it was fetched.
 *
 * ★★ THE DEFECT. `updatedAtMs` was initialised with
 * `response ? Date.now() : null`. ThreadInsightsPanel mounts this view only
 * while its Physics tab is selected, so tabbing away and back UNMOUNTS and
 * REMOUNTS it, the initialiser re-fires, and a reading up to four turns old
 * (PHYSICS_AUTO_EVERY_N = 5) is stamped "updated just now".
 *
 * ★ Looking at the panel is what required the tab — so the false timestamp
 * appeared every single time anyone checked it. That is why it read as
 * always-fresh rather than as an occasional glitch.
 *
 * ★★★ THE PERTURBATION IS UNMOUNT/REMOUNT, not a passing render. A test that
 * only renders once cannot see this bug at all.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("../../../../lib/emotionalPhysics", async () => {
  const actual = await vi.importActual<
    typeof import("../../../../lib/emotionalPhysics")
  >("../../../../lib/emotionalPhysics");
  return { ...actual, analyzeEmotionalPhysics: vi.fn() };
});

import EmotionalPhysicsView from "../EmotionalPhysicsView";

const HOUR = 60 * 60 * 1000;

function reading(tsMs: number | undefined) {
  return {
    field_curvature: { intensity: "high", notes: "n" },
    edge_pressure: {},
    relational_primitives: {},
    external_expression: {},
    _meta: { model_id: "anthropic:claude-haiku-4-5", ts_ms: tsMs, parse_error: null },
  } as never;
}

beforeEach(() => vi.useFakeTimers().setSystemTime(new Date("2026-08-28T12:00:00Z")));
afterEach(() => vi.useRealTimers());

describe("EmotionalPhysicsView — the timestamp travels with the reading", () => {
  it("★ THE PERTURBATION: unmount and remount must NOT reset the age", () => {
    const twoHoursAgo = Date.now() - 2 * HOUR;
    const { unmount } = render(
      <EmotionalPhysicsView response={reading(twoHoursAgo)} text="t" />,
    );
    const before = screen.getByText(/updated/).textContent;

    // Tab away (unmount) and back (remount) with the SAME cached reading —
    // exactly what ThreadInsightsPanel does on a tab switch.
    unmount();
    render(<EmotionalPhysicsView response={reading(twoHoursAgo)} text="t" />);
    const after = screen.getByText(/updated/).textContent;

    expect(before).toBe(after);
    expect(after).not.toMatch(/just now/i);
    expect(after).toMatch(/2h ago/);
  });

  it("a genuinely fresh reading does read as fresh", () => {
    render(<EmotionalPhysicsView response={reading(Date.now())} text="t" />);
    expect(screen.getByText(/updated/).textContent).toMatch(/just now/i);
  });

  it("★ a reading with NO stamp renders no timestamp at all", () => {
    // A missing timestamp and a fresh one must not render the same. Showing
    // "just now" for an unstamped reading is the original bug in miniature.
    render(<EmotionalPhysicsView response={reading(undefined)} text="t" />);
    expect(screen.queryByText(/updated/)).toBeNull();
  });

  it("a malformed stamp is treated as absent, not as epoch zero", () => {
    const bad = reading(undefined) as unknown as Record<string, unknown>;
    (bad._meta as Record<string, unknown>).ts_ms = "not-a-number";
    render(<EmotionalPhysicsView response={bad as never} text="t" />);
    expect(screen.queryByText(/updated/)).toBeNull();
  });

  it("the age advances with the clock rather than being pinned at render", () => {
    const t = Date.now();
    const { unmount } = render(<EmotionalPhysicsView response={reading(t)} text="x" />);
    expect(screen.getByText(/updated/).textContent).toMatch(/just now/i);
    unmount();

    vi.setSystemTime(new Date(t + 3 * HOUR));
    render(<EmotionalPhysicsView response={reading(t)} text="x" />);
    expect(screen.getByText(/updated/).textContent).toMatch(/3h ago/);
  });
});
