/**
 * #116 — a count at its cap is a floor, and the page says so.
 *
 * ★ WHAT THIS PINS. primitives_extract caps each category (terms 30,
 * clauses 20, tensions 12, hydronic 4x12). A long paste renders "P1: 30",
 * which reads as a measurement when it is "at least 30". The backend now
 * ships the caps in primitives_meta.caps; when a count EQUALS its cap the
 * page renders "30+ (cap)"; below the cap it renders the number; with no
 * caps block (an older backend) it renders the number, never a guess.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...actual, markov: vi.fn() };
});

import * as api from "../../lib/api";
import Markov from "../Markov";

// hydronic carries NO cap: it counts distinct keyword types over a fixed
// 29-word vocabulary and is never truncated, so it is never a floor.
const CAPS = { P1: 30, P2: 30, P3: 20, P4: 20, Ts: 12, Te: 12, M: 12 };

// `null` = omit the caps block. (Not `undefined`: an explicit undefined
// re-applies a JS default parameter, and the test would silently get CAPS.)
function payload(counts: Record<string, number>, caps: Record<string, number> | null = CAPS) {
  return {
    ok: true,
    engine: "markov",
    data: {
      model: "openai:gpt-5.4", provider: "openai", output: "r", mock: false, user: "u",
      primitives: {
        P1: [], P2: [], P3: [], P4: [], Ts: [], Te: [], M: [],
        hydronic: { flows: [], blockages: [], gradients: [], pressure_points: [] },
      },
      primitives_formatted: "## P1\n",
      primitives_meta: { status: "extracted", counts, ...(caps ? { caps } : {}) },
      recast: "r",
    },
  };
}

async function run() {
  render(<Markov />);
  await userEvent.type(screen.getByLabelText("Input"), "some long text");
  await userEvent.click(screen.getByRole("button", { name: /^RUN$/ }));
  await waitFor(() => expect(screen.getByTestId("markov-run")).toBeTruthy());
}

beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.clearAllMocks());

describe("Markov page — counts at their cap (#116)", () => {
  it("★ a count equal to its cap renders '30+ (cap)'", async () => {
    vi.mocked(api.markov).mockResolvedValue(
      payload({ P1: 30, P2: 3, P3: 20, P4: 0, Ts: 12, Te: 1, M: 0, hydronic: 48 }) as never,
    );
    await run();
    const counts = screen.getByTestId("markov-counts");
    expect(counts).toHaveTextContent("P1: 30+ (cap)");
    expect(counts).toHaveTextContent("P3: 20+ (cap)");
    expect(counts).toHaveTextContent("Ts: 12+ (cap)");
    // hydronic has no cap on the wire: a high count is a count, never a floor
    expect(counts).toHaveTextContent("hydronic: 48");
    expect(counts.textContent).not.toMatch(/hydronic: 48\+/);
    // below the cap: the number, nothing else
    expect(counts).toHaveTextContent("P2: 3");
    expect(counts.textContent).not.toMatch(/P2: 3\+/);
    expect(counts).toHaveTextContent("Te: 1");
  });

  it("one below the cap is a measurement, not a floor", async () => {
    vi.mocked(api.markov).mockResolvedValue(
      payload({ P1: 29, P2: 0, P3: 19, P4: 0, Ts: 11, Te: 0, M: 0, hydronic: 47 }) as never,
    );
    await run();
    const counts = screen.getByTestId("markov-counts");
    expect(counts).toHaveTextContent("P1: 29");
    expect(counts.textContent).not.toMatch(/\(cap\)/);
  });

  it("no caps block (older backend): the number renders, never a guessed cap", async () => {
    vi.mocked(api.markov).mockResolvedValue(
      payload({ P1: 30, P2: 0, P3: 20, P4: 0, Ts: 12, Te: 0, M: 0, hydronic: 48 }, null) as never,
    );
    await run();
    const counts = screen.getByTestId("markov-counts");
    expect(counts).toHaveTextContent("P1: 30");
    expect(counts.textContent).not.toMatch(/\(cap\)/);
  });
});
