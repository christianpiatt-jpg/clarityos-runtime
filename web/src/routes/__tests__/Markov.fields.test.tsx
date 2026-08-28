/**
 * Markov page — reads the fields the adapter actually emits.
 *
 * ★ THE DEFECT. The page read `score` / `tags` / `interpretation`.
 * markov_adapter stopped emitting those when the v2.1 stub was replaced by
 * the v81 P-series recast (app.py:1031 records the replacement). Every
 * displayed field was `undefined`, and the interface in api.ts asserted a
 * shape the wire never carried — so TypeScript could not catch it.
 *
 * ★★ The fixture below is built from the adapter's RETURN STATEMENT
 * (app.py:1060-1070), not its docstring. A shared concept word is not a
 * match; the field names are the match.
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

function payload(over: Record<string, unknown> = {}) {
  return {
    ok: true,
    engine: "markov",
    data: {
      model: "openai:gpt-5.4",
      provider: "openai",
      output: "the recast text",
      mock: false,
      user: "u",
      primitives: {
        P1: ["Alpha"], P2: ["caused"], P3: ["x because y"], P4: [],
        Ts: ["tension"], Te: [], M: [],
        hydronic: { flows: [], blockages: ["bottleneck"], gradients: [], pressure_points: [] },
      },
      primitives_formatted: "## P1\n- Alpha\n",
      primitives_meta: {
        status: "extracted",
        counts: { P1: 1, P2: 1, P3: 1, P4: 0, Ts: 1, Te: 0, M: 0, hydronic: 1 },
      },
      recast: "the recast text",
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

beforeEach(() => vi.mocked(api.markov).mockResolvedValue(payload() as never));
afterEach(() => vi.clearAllMocks());

describe("Markov page — field bindings", () => {
  it("renders the 8-category distribution that already crossed the wire", async () => {
    await run();
    const counts = screen.getByTestId("markov-counts");
    for (const k of ["P1", "P2", "P3", "P4", "Ts", "Te", "M", "hydronic"]) {
      expect(counts).toHaveTextContent(k);
    }
    expect(counts).toHaveTextContent("P1: 1");
    expect(counts).toHaveTextContent("P4: 0");
  });

  it("renders the recast and the module's own formatted decomposition", async () => {
    await run();
    expect(screen.getByTestId("markov-recast")).toHaveTextContent("the recast text");
    expect(screen.getByTestId("markov-formatted")).toHaveTextContent("Alpha");
  });

  it("★ NEGATIVE CONTROL: a field the adapter omits renders (absent), never blank", async () => {
    vi.mocked(api.markov).mockResolvedValue(
      payload({ recast: undefined, output: undefined, primitives_formatted: undefined }) as never,
    );
    await run();
    expect(screen.getByTestId("markov-recast")).toHaveTextContent("(absent)");
    expect(screen.getByTestId("markov-formatted")).toHaveTextContent("(absent)");
  });

  it("★ a missing counts block renders (absent) per category, not a crash", async () => {
    vi.mocked(api.markov).mockResolvedValue(
      payload({ primitives_meta: undefined }) as never,
    );
    await run();
    expect(screen.getByTestId("markov-counts")).toHaveTextContent("P1: (absent)");
  });

  it("★★ the dead `score` binding is gone — it fed undefined to the status bar", async () => {
    // Layout.tsx:176 guards with `mqc.score !== null`, which undefined PASSES,
    // and then calls .toFixed(2) on it. That is a render crash, not a blank
    // cell. Nothing on this page may push a score any more.
    const layout = await import("../../components/Layout");
    const spy = vi.spyOn(layout, "pushMarkovScore");
    await run();
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });
});
