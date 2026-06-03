// Card 8.5a / Phase 8.5 — desktop OperatorConsoleShell tile tests.
//
// Verifies the two new operator-facing tiles (Causal Chains + Structural
// Motifs) render from the GET /operator/telemetry payload, mirroring the
// web suite's Phase-8.5 coverage. Read-only: the console never writes; the
// backend owns the Phase-8 reasoning.
//
// The shell wraps its body in the heavy v1 DesktopShell chrome (top bar /
// sidebar / insights). We stub DesktopShell down to a passthrough that
// renders only `center`, so these tests target the console body in
// isolation — exactly as the web test renders OperatorConsole directly.
import type { ReactNode } from "react";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("../DesktopShell", () => ({
  default: ({ center }: { center: ReactNode }) => center,
}));

import OperatorConsoleShell from "../OperatorConsoleShell";

function renderConsole() {
  return render(<OperatorConsoleShell onSignOut={vi.fn()} onNavigate={vi.fn()} />);
}

// The shell fetches GET /operator/telemetry on mount. Stub fetch for every
// test so the suite stays network-free; each test overrides with its payload.
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

describe("Phase 8.5 — desktop Causal Chains + Structural Motifs tiles", () => {
  it("renders the Causal Chains tile with chains, scores, and motif flags", async () => {
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

    const { container } = renderConsole();

    expect(screen.getByText("Causal Chains")).toBeInTheDocument();
    // Chains arrive after the mount fetch resolves.
    await waitFor(() => expect(container.textContent).toContain("Chain 1"));
    expect(container.textContent).toContain("score 0.78");
    expect(container.textContent).toContain("Chain 2");
    expect(container.textContent).toContain("score 0.55");
    // Node labels render under each chain.
    expect(container.textContent).toContain("Drift velocity: 0.60");
    expect(container.textContent).toContain("prune (contribution: 0.50)");
    // Per-chain motif flags render as yes/no.
    expect(container.textContent).toContain("bottleneck=yes");
    expect(container.textContent).toContain("attractor=yes"); // from chain 2
    expect(container.textContent).toContain("loop=no");
  });

  it("renders the Structural Motifs tile with loops, bottlenecks, attractors", async () => {
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

    const { container } = renderConsole();

    expect(screen.getByText("Structural Motifs")).toBeInTheDocument();
    expect(screen.getByText("Feedback Loops")).toBeInTheDocument();
    expect(screen.getByText("Bottlenecks")).toBeInTheDocument();
    expect(screen.getByText("Attractors")).toBeInTheDocument();
    // Loops render as " → "-joined node sequences.
    await waitFor(() => expect(container.textContent).toContain("a → b"));
    expect(container.textContent).toContain("x → y → z");
    expect(container.textContent).toContain("drift_velocity");
  });

  it("renders fallbacks when chains + motifs are empty", async () => {
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

    const { container } = renderConsole();

    await waitFor(() => expect(container.textContent).toContain("No causal chains detected"));
    // Each of the three motif categories shows its empty sentinel.
    expect((container.textContent?.match(/None/g) ?? []).length).toBeGreaterThanOrEqual(3);
  });

  it("renders the Causal Stability tile with score, trend, and drivers", async () => {
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

    const { container } = renderConsole();

    expect(screen.getByText("Causal Stability")).toBeInTheDocument();
    await waitFor(() => expect(container.textContent).toContain("Stability Score: 0.75"));
    expect(container.textContent).toContain("Trend: destabilizing");
    expect(screen.getByText("Rising Influence")).toBeInTheDocument();
    expect(screen.getByText("Chain Weakening")).toBeInTheDocument();
    expect(container.textContent).toContain("stability_forecast");        // falling influence
    expect(container.textContent).toContain("a → b");                     // new loop
    expect(container.textContent).toContain("drift_velocity → narrative"); // chain strengthening
  });

  it("renders the Unified Narrative tile inside a <pre> block", async () => {
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

    const heading = screen.getByText("Unified Narrative");
    expect(heading).toBeInTheDocument();
    // The narrative renders verbatim in the <pre> sibling of the heading.
    const pre = heading.nextElementSibling;
    expect(pre?.tagName).toBe("PRE");
    await waitFor(() => expect(pre?.textContent).toContain("Unified Temporal–Causal Narrative"));
    expect(pre?.textContent).toContain("Overall Assessment:");
    expect(pre?.textContent).toContain(unified);
  });
});

// Card 9.5 / Phase 9.5 — desktop Behavioral Patterns tile tests. Verifies the
// new operator-facing behavioral-motif tile renders from the GET
// /operator/telemetry behavioral_motifs block, scrolls long sections, preserves
// backend ordering, and is purely additive (no causal-tile regression).
describe("Phase 9.5 — desktop Behavioral Patterns tile", () => {
  it("renders the Behavioral Patterns tile with all five sections", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          history: [{}],
          behavioral_motifs: {
            action_loops: [["open_settings", "adjust_param"]],
            trigger_chains: [["open_settings", "factor_load", "adjust_param"]],
            habits: ["daily_review"],
            action_bottlenecks: ["bottleneck_node"],
            action_attractors: ["attractor_node"],
          },
        }),
      })),
    );

    const { container } = renderConsole();

    expect(screen.getByText("Behavioral Patterns")).toBeInTheDocument();
    // Motifs arrive after the mount fetch resolves.
    await waitFor(() => expect(container.textContent).toContain("open_settings → adjust_param"));
    expect(container.textContent).toContain("Action Loops");
    expect(container.textContent).toContain("Trigger Chains");
    expect(container.textContent).toContain("Habits");
    expect(container.textContent).toContain("Action Bottlenecks");
    expect(container.textContent).toContain("Action Attractors");
    // action_loops + trigger_chains render as " → "-joined sequences.
    expect(container.textContent).toContain("open_settings → factor_load → adjust_param");
    // Label families render verbatim.
    expect(container.textContent).toContain("daily_review");
    expect(container.textContent).toContain("bottleneck_node");
    expect(container.textContent).toContain("attractor_node");
  });

  it("makes a behavioral section scrollable when it exceeds 10 items", async () => {
    const habits = Array.from({ length: 11 }, (_, i) => `habit_${i}`);
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          history: [{}],
          behavioral_motifs: {
            action_loops: [["a", "b"]],
            trigger_chains: [],
            habits,
            action_bottlenecks: [],
            action_attractors: [],
          },
        }),
      })),
    );

    renderConsole();

    // The 11-item habits list becomes independently scrollable…
    const habitsList = await screen.findByTestId("oc-behavioral-habits");
    expect(habitsList.style.overflowY).toBe("auto");
    expect(habitsList.style.maxHeight).toBe("20rem");
    // …while the 1-item loops list stays unbounded (no scroll style).
    const loopsList = screen.getByTestId("oc-behavioral-loops");
    expect(loopsList.style.overflowY).toBe("");
  });

  it("renders behavioral motifs in backend array order (no client re-sort)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          history: [{}],
          behavioral_motifs: {
            action_loops: [],
            trigger_chains: [],
            // Deliberately NOT alphabetical — the tile must preserve the
            // backend's deterministic ordering verbatim.
            habits: ["zebra_action", "alpha_action", "mid_action"],
            action_bottlenecks: [],
            action_attractors: [],
          },
        }),
      })),
    );

    renderConsole();

    const habitsList = await screen.findByTestId("oc-behavioral-habits");
    const rows = Array.from(habitsList.querySelectorAll("li")).map((li) => li.textContent);
    expect(rows).toEqual(["zebra_action", "alpha_action", "mid_action"]);
  });

  it("renders the Behavioral Patterns tile alongside the existing causal tiles (no layout regression)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          history: [{}],
          causal_motifs: { feedback_loops: [["a", "b"]], bottlenecks: ["x"], attractors: ["y"] },
          behavioral_motifs: {
            action_loops: [["open_settings", "adjust_param"]],
            trigger_chains: [],
            habits: [],
            action_bottlenecks: [],
            action_attractors: [],
          },
        }),
      })),
    );

    renderConsole();

    // The existing causal tiles and the new behavioral tile coexist in the same
    // body — the Phase 9.5 tile is purely additive.
    expect(screen.getByText("Structural Motifs")).toBeInTheDocument();
    expect(screen.getByText("Unified Narrative")).toBeInTheDocument();
    expect(screen.getByText("Behavioral Patterns")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByTestId("oc-behavioral-loops").textContent).toContain(
        "open_settings → adjust_param",
      ),
    );
  });
});

// Card 10.4 / Phase 10.4 — desktop Behavioral Forecast tile tests. Verifies the
// read-only 10.0-10.3 surfacing (forecast / stability / narrative) from
// telemetry.behavioral_forecast renders, scrolls long sections, preserves
// backend ordering, and is purely additive (no existing-tile regression).
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
    summary: "Behavioral patterns show moderate change.",
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

describe("Phase 10.4 — desktop Behavioral Forecast tile", () => {
  it("renders the Behavioral Forecast tile with all six sections", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: true, json: async () => ({ history: [{}], behavioral_forecast: BF_FULL }) })),
    );

    renderConsole();

    expect(screen.getByText("Behavioral Forecast")).toBeInTheDocument();
    const na = await screen.findByTestId("oc-bf-next-actions");
    expect(na.textContent).toContain("edit — score 0.90 (loop, habit)");
    expect(screen.getByTestId("oc-bf-habits").textContent).toContain("edit — strengthening (Δ 0.80)");
    expect(screen.getByTestId("oc-bf-triggers").textContent).toContain("a → f → b (Δ 0.90)");
    expect(screen.getByTestId("oc-bf-loops").textContent).toContain("edit → prune (0.95)");
    expect(screen.getByTestId("oc-bf-stability").textContent).toContain("Score: 0.62");
    expect(screen.getByTestId("oc-bf-narrative").textContent).toContain("moderate change");
  });

  it("makes the habit section scrollable when it exceeds 10 items", async () => {
    const habit_changes = Array.from({ length: 11 }, (_, i) => ({
      action_id: `h${i}`, trend: "stable", delta: 0.1,
    }));
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          history: [{}],
          behavioral_forecast: {
            forecast: { next_actions: [{ action_id: "a", label: "A", score: 0.5, drivers: [] }], loop_continuation: [] },
            stability: BF_FULL.stability,
            narrative: { summary: "", habit_changes, trigger_changes: [], forecast_highlights: [] },
          },
        }),
      })),
    );

    renderConsole();

    // The 11-row habit list becomes scrollable…
    const habits = await screen.findByTestId("oc-bf-habits");
    const habitList = habits.querySelector("ul");
    expect(habitList?.style.overflowY).toBe("auto");
    expect(habitList?.style.maxHeight).toBe("20rem");
    // …while the 1-row next-actions list does not.
    const naList = screen.getByTestId("oc-bf-next-actions").querySelector("ul");
    expect(naList?.style.overflowY).toBe("");
  });

  it("caps triggers/loops at 3 and renders in backend array order", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: true, json: async () => ({ history: [{}], behavioral_forecast: BF_FULL }) })),
    );

    renderConsole();

    const triggers = await screen.findByTestId("oc-bf-triggers");
    const rows = Array.from(triggers.querySelectorAll("li")).map((li) => li.textContent);
    expect(rows).toEqual(["a → f → b (Δ 0.90)", "c → f → d (Δ 0.50)", "e → f → g (Δ 0.20)"]);
  });

  it("renders the Behavioral Forecast tile alongside the existing tiles (no layout regression)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          history: [{}],
          causal_motifs: { feedback_loops: [["a", "b"]], bottlenecks: ["x"], attractors: ["y"] },
          behavioral_motifs: {
            action_loops: [["open_settings", "adjust_param"]],
            trigger_chains: [], habits: [], action_bottlenecks: [], action_attractors: [],
          },
          behavioral_forecast: BF_FULL,
        }),
      })),
    );

    renderConsole();

    // The Phase-8 causal tile, the 9.5 motifs tile, and the 10.4 forecast tile
    // all coexist — 10.4 is purely additive.
    expect(screen.getByText("Structural Motifs")).toBeInTheDocument();
    expect(screen.getByText("Behavioral Patterns")).toBeInTheDocument();
    expect(screen.getByText("Behavioral Forecast")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByTestId("oc-bf-loops").textContent).toContain("edit → prune (0.95)"),
    );
  });
});

// Card 11.2 / Phase 11.2 — desktop Recommendations tile tests. Verifies the
// read-only 11.0 recommendations + 11.1 narrative surfacing (recommendations /
// drivers / stability / narrative) from telemetry.recommendation_narrative
// renders, scrolls long sections, preserves backend ordering, and is purely
// additive (no existing-tile regression).
const RN_FULL = {
  summary: "Behavioral system shows moderate variability; recommendations address key leverage points.",
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

describe("Phase 11.2 — desktop Recommendations tile", () => {
  it("renders the Recommendations tile with all four sections", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: true, json: async () => ({ history: [{}], recommendation_narrative: RN_FULL }) })),
    );

    renderConsole();

    expect(screen.getByText("Recommendations")).toBeInTheDocument();
    const top = await screen.findByTestId("oc-rec-top");
    expect(top.textContent).toContain("edit — forecast_alignment (score 0.90)");
    expect(screen.getByTestId("oc-rec-driver-habit").textContent).toContain("prune — habit_weakening (0.50)");
    expect(screen.getByTestId("oc-rec-stability").textContent).toContain("Score: 0.55");
    expect(screen.getByTestId("oc-rec-narrative").textContent).toContain("moderate variability");
  });

  it("makes the recommendations section scrollable when it exceeds 10 items", async () => {
    const recommendations = Array.from({ length: 11 }, (_, i) => ({
      action_id: `r${i}`, label: `r${i}`, reason: "habit_weakening", score: 0.5, explanation: "e",
    }));
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          history: [{}],
          recommendation_narrative: {
            summary: "",
            recommendations,
            drivers: { habit: [], triggers: [], loops: [], bottlenecks: [], attractors: [], forecast_alignment: [] },
            stability_context: RN_FULL.stability_context,
          },
        }),
      })),
    );

    renderConsole();

    const top = await screen.findByTestId("oc-rec-top");
    const ul = top.querySelector("ul");
    expect(ul?.style.overflowY).toBe("auto");
    expect(ul?.style.maxHeight).toBe("20rem");
  });

  it("renders driver buckets in deterministic order", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: true, json: async () => ({ history: [{}], recommendation_narrative: RN_FULL }) })),
    );

    renderConsole();

    const drivers = await screen.findByTestId("oc-rec-drivers");
    const headings = Array.from(drivers.querySelectorAll("h4")).map((h) => h.textContent);
    expect(headings).toEqual(["Habit", "Bottlenecks", "Forecast Alignment"]);
  });

  it("renders the Recommendations tile alongside the existing tiles (no layout regression)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          history: [{}],
          causal_motifs: { feedback_loops: [["a", "b"]], bottlenecks: ["x"], attractors: ["y"] },
          behavioral_forecast: BF_FULL,
          recommendation_narrative: RN_FULL,
        }),
      })),
    );

    renderConsole();

    // The Phase-8 causal tile, the 10.4 forecast tile, and the 11.2 recs tile
    // all coexist — 11.2 is purely additive.
    expect(screen.getByText("Structural Motifs")).toBeInTheDocument();
    expect(screen.getByText("Behavioral Forecast")).toBeInTheDocument();
    expect(screen.getByText("Recommendations")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByTestId("oc-rec-top").textContent).toContain("edit — forecast_alignment"),
    );
  });
});
