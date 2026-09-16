/**
 * #315 -- /markov renders the verb-owner set: one row "verbs · G1–G7 · D/N/T"
 * under the P-series counts, read off `data.verb_owner_set` (the dict the
 * thread shadow logs). A missing block (older backend) or a flow with no
 * denominator (the "UNMAPPED" marker) reads "—"; nothing is computed here.
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

const SET = {
  G1: 13, G2: 0, G3: 0, G4: 0, G5: 0, G6: 1, G7: 0,
  G4_reflexive_only: true, G_sentences: 38,
  D: 23, D_status: "CANDIDATE",
  T: 0.0526, T_status: "CANDIDATE",
  N: "UNMAPPED", N_status: "UNMAPPED",
  E: "UNMAPPED", E_status: "UNMAPPED",
  counts: { P1: 23, P2: 0, P3: 0, P4: 0, Ts: 0, Te: 0, M: 0, hydronic: 0 },
  computed: false,
  // the kernel's real shape: three segments joined with " · ", each prefixed by its letter
  reason: "T: hedge ratio ported from langbridg.ts; arousal mapping unruled · N: no primitives extracted, p_i undefined · E: no producer identified; not computed, not defaulted",
};

function payload(over: Record<string, unknown> = {}) {
  return {
    ok: true,
    engine: "markov",
    data: {
      model: "m", provider: "p", output: "o", mock: true, user: "u",
      primitives: { P1: [], P2: [], P3: [], P4: [], Ts: [], Te: [], M: [],
        hydronic: { flows: [], blockages: [], gradients: [], pressure_points: [] } },
      primitives_formatted: "## P1\n",
      primitives_meta: { status: "extracted", counts: { P1: 0, P2: 0, P3: 0, P4: 0, Ts: 0, Te: 0, M: 0, hydronic: 0 } },
      recast: "o",
      ...over,
    },
  };
}

async function run() {
  render(<Markov />);
  await userEvent.type(screen.getByLabelText("Input"), "some text");
  await userEvent.click(screen.getByRole("button", { name: /^RUN$/ }));
  await waitFor(() => expect(screen.getByTestId("markov-run")).toBeTruthy());
}

beforeEach(() => vi.mocked(api.markov).mockResolvedValue(payload({ verb_owner_set: SET }) as never));
afterEach(() => vi.clearAllMocks());

describe("#315 -- the verbs row", () => {
  it("★ renders G1–G7 and D / N / T off the wire; a flow with no denominator reads a dash", async () => {
    await run();
    const row = screen.getByTestId("markov-verbs");
    expect(row).toHaveTextContent("verbs · G1–G7 · D/N/T");
    expect(row).toHaveTextContent("G1: 13");
    expect(row).toHaveTextContent("G6: 1");
    expect(row).toHaveTextContent("G7: 0");
    expect(row).toHaveTextContent("D: 23");
    expect(row).toHaveTextContent("T: 0.0526");
    expect(row).toHaveTextContent("N: —");
    expect(row.querySelector('[data-verb="N"]')?.getAttribute("title")).toBe("N: UNMAPPED — no primitives extracted, p_i undefined");
    expect(row.querySelector('[data-verb="D"]')?.getAttribute("title")).toBe("D: CANDIDATE");
    expect(row.querySelector('[data-verb="G1"]')?.getAttribute("title")).toBe("G1: grammar counter (#135)");
  });

  it("★ a measured zero ratio reads four places, not like a counter's zero", async () => {
    vi.mocked(api.markov).mockResolvedValue(payload({ verb_owner_set: { ...SET, T: 0, N: 1 } }) as never);
    await run();
    const row = screen.getByTestId("markov-verbs");
    expect(row).toHaveTextContent("T: 0.0000");
    expect(row).toHaveTextContent("N: 1.0000");
    expect(row).toHaveTextContent("G7: 0");
  });

  it("★ an older backend without the block: every cell is a dash, nothing is invented", async () => {
    vi.mocked(api.markov).mockResolvedValue(payload() as never);
    await run();
    const row = screen.getByTestId("markov-verbs");
    for (const k of ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "D", "N", "T"]) {
      expect(row).toHaveTextContent(`${k}: —`);
    }
    expect(row.querySelector('[data-verb="T"]')?.getAttribute("title")).toBe("T: flow (absent)");
    expect(row.querySelector('[data-verb="G3"]')?.getAttribute("title")).toBe("G3: grammar counter (#135)");
    // and the P-series row above it is untouched
    expect(screen.getByTestId("markov-counts")).toHaveTextContent("P1: 0");
  });
});
