// v80 — RegressionFirstPanel packet runner tests.

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import type { RegressionFirstChain } from "../../../lib/api";
import RegressionFirstPanel from "../RegressionFirstPanel";

vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>(
    "../../../lib/api",
  );
  return {
    ...actual,
    postRegressionFirstPacket: vi.fn(),
    replayRegressionFirstChain: vi.fn(),
  };
});

import {
  ApiError,
  postRegressionFirstPacket,
  replayRegressionFirstChain,
} from "../../../lib/api";

const mockPost   = vi.mocked(postRegressionFirstPacket);
const mockReplay = vi.mocked(replayRegressionFirstChain);

function makeChain(overrides: Partial<RegressionFirstChain> = {}): RegressionFirstChain {
  return {
    chain_id:   "chain-uuid-1",
    created_at: 1700000000000,
    closed_at:  null,
    title:      "Identify root cause of rendering failure.",
    notes:      null,
    layers: [
      {
        layer_index: 0,
        status:      "unknown",
        notes:       "Domain & Routing | Which page... | (look here: Settings) | (goal: Correct)",
        updated_at:  1700000001000,
      },
    ],
    tags: {},
    archived: false,
    ...overrides,
  };
}

beforeEach(() => {
  mockPost.mockReset();
  mockReplay.mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("RegressionFirstPanel", () => {
  test("renders the packet editor pre-filled with an example", () => {
    render(<RegressionFirstPanel />);
    const editor = screen.getByTestId("regression-first-packet-editor") as HTMLTextAreaElement;
    expect(editor).toBeInTheDocument();
    // Pre-filled with the canonical example shape.
    expect(editor.value).toContain('"classification"');
    expect(editor.value).toContain("structure-dominant");
    expect(editor.value).toContain("regression_chain");
  });

  test("renders the run button", () => {
    render(<RegressionFirstPanel />);
    const btn = screen.getByTestId("regression-first-run");
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveTextContent(/run regression first/i);
  });

  test("posts the parsed packet to the API on click", async () => {
    mockPost.mockResolvedValue(makeChain());
    render(<RegressionFirstPanel />);
    fireEvent.click(screen.getByTestId("regression-first-run"));
    await waitFor(() => expect(mockPost).toHaveBeenCalledTimes(1));
    const [packet] = mockPost.mock.calls[0];
    // The posted object is the parsed JSON of the pre-filled example.
    expect(packet).toMatchObject({
      classification: "structure-dominant",
      regression_required: true,
    });
  });

  test("renders the chain summary on success", async () => {
    mockPost.mockResolvedValue(makeChain());
    render(<RegressionFirstPanel />);
    fireEvent.click(screen.getByTestId("regression-first-run"));
    const summary = await screen.findByTestId("regression-first-summary");
    expect(summary).toHaveTextContent(/Identify root cause/);
    expect(summary).toHaveTextContent(/chain-uuid-1/);
    expect(summary).toHaveTextContent(/Seeded layer:/i);
    expect(summary).toHaveTextContent(/unknown/);
  });

  test("renders the ok marker after a successful run", async () => {
    mockPost.mockResolvedValue(makeChain());
    render(<RegressionFirstPanel />);
    fireEvent.click(screen.getByTestId("regression-first-run"));
    await screen.findByTestId("regression-first-ok");
  });

  test("renders the error message on API failure", async () => {
    mockPost.mockRejectedValue(
      new ApiError("packet_rejected", "missing field: classification", 422),
    );
    render(<RegressionFirstPanel />);
    fireEvent.click(screen.getByTestId("regression-first-run"));
    const err = await screen.findByTestId("regression-first-error");
    expect(err).toHaveTextContent(/packet_rejected/);
    expect(err).toHaveTextContent(/missing field/);
  });

  test("flags invalid JSON without hitting the API", async () => {
    render(<RegressionFirstPanel />);
    const editor = screen.getByTestId("regression-first-packet-editor");
    fireEvent.change(editor, { target: { value: "not json at all" } });
    fireEvent.click(screen.getByTestId("regression-first-run"));
    const err = await screen.findByTestId("regression-first-error");
    expect(err).toHaveTextContent(/invalid_json/);
    expect(mockPost).not.toHaveBeenCalled();
  });

  test("rejects non-object JSON without hitting the API", async () => {
    render(<RegressionFirstPanel />);
    const editor = screen.getByTestId("regression-first-packet-editor");
    fireEvent.change(editor, { target: { value: '"a bare string"' } });
    fireEvent.click(screen.getByTestId("regression-first-run"));
    const err = await screen.findByTestId("regression-first-error");
    expect(err).toHaveTextContent(/invalid_json/);
    expect(mockPost).not.toHaveBeenCalled();
  });

  test("renders fallback when chain has no layers", async () => {
    mockPost.mockResolvedValue(makeChain({ layers: [] }));
    render(<RegressionFirstPanel />);
    fireEvent.click(screen.getByTestId("regression-first-run"));
    const summary = await screen.findByTestId("regression-first-summary");
    // Summary still renders title + chain_id, just without the
    // "Seeded layer:" line.
    expect(summary).toHaveTextContent(/Identify root cause/);
    expect(summary).not.toHaveTextContent(/Seeded layer:/i);
  });
});

// ===========================================================================
// V82 — Rerun regression affordance
// ===========================================================================
describe("RegressionFirstPanel — Rerun (v82)", () => {
  test("rerun button appears after successful packet run", async () => {
    mockPost.mockResolvedValue(makeChain());
    render(<RegressionFirstPanel />);
    expect(screen.queryByTestId("regression-first-rerun")).toBeNull();
    fireEvent.click(screen.getByTestId("regression-first-run"));
    await screen.findByTestId("regression-first-rerun");
  });

  test("rerun calls /replay with the current chain_id", async () => {
    mockPost.mockResolvedValue(makeChain({ chain_id: "alpha" }));
    mockReplay.mockResolvedValue(makeChain({ chain_id: "beta" }));
    render(<RegressionFirstPanel />);
    fireEvent.click(screen.getByTestId("regression-first-run"));
    const rerun = await screen.findByTestId("regression-first-rerun");
    fireEvent.click(rerun);
    await waitFor(() => expect(mockReplay).toHaveBeenCalledTimes(1));
    expect(mockReplay).toHaveBeenCalledWith("alpha");
  });

  test("rerun success swaps the summary to the new chain + tags replay", async () => {
    mockPost.mockResolvedValue(makeChain({ chain_id: "alpha" }));
    mockReplay.mockResolvedValue(
      makeChain({ chain_id: "beta", title: "replayed run" }),
    );
    render(<RegressionFirstPanel />);
    fireEvent.click(screen.getByTestId("regression-first-run"));
    const rerun = await screen.findByTestId("regression-first-rerun");
    fireEvent.click(rerun);
    await screen.findByTestId("regression-first-source-replay");
    const summary = await screen.findByTestId("regression-first-summary");
    expect(summary).toHaveTextContent("beta");
    expect(summary).toHaveTextContent(/replayed run/);
  });

  test("rerun error surfaces via the error banner", async () => {
    mockPost.mockResolvedValue(makeChain({ chain_id: "alpha" }));
    mockReplay.mockRejectedValue(
      new ApiError("not_found", "no original packet stored", 404),
    );
    render(<RegressionFirstPanel />);
    fireEvent.click(screen.getByTestId("regression-first-run"));
    const rerun = await screen.findByTestId("regression-first-rerun");
    fireEvent.click(rerun);
    const err = await screen.findByTestId("regression-first-error");
    expect(err).toHaveTextContent(/not_found/);
  });

  test("rerun is absent before any successful run", () => {
    render(<RegressionFirstPanel />);
    expect(screen.queryByTestId("regression-first-rerun")).toBeNull();
  });
});
