/**
 * "send to corpus" in the ElinsV2View footer.
 *
 * ★ WHAT THESE PIN. After a run renders WITH its input text in hand
 * (runOn.rawText), the footer offers "send to corpus"; pressing it posts
 * that same text through ingestManual with source "elins_v2_view" and shows
 * the created id. After success the button is disabled -- a second press
 * would mint a duplicate row. When the text changes (new turn, other
 * thread) the control remounts (key={text}) and never claims the new text
 * was sent. Without the input text -- or with whitespace only -- the control
 * is not offered at all: a button that could send nothing is not a button.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../../../lib/api", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  ingestManual: vi.fn(),
}));

import { ingestManual } from "../../../../lib/api";
import ElinsV2View from "../ElinsV2View";

const mocked = vi.mocked(ingestManual);

function envelope() {
  return {
    elins_version: "v2",
    region: null,
    input: { raw_text: "x" },
    pipeline: {
      L1_ingest: {}, L2_normalize: { normalized: true, note: "" }, L3_domain: {}, L4_narrative: {},
      L5_pressure:  { primitive: "pressure",  intensity: 0, edge_count: 0 },
      L6_drift:     { primitive: "drift",     intensity: 0, edge_count: 0 },
      L7_basin: { region: null, available: false },
      L8_temporal: { forecast_5day: {}, forecast_engine: {}, etf_table: {},
                     etf_agg: { n_365: 0, n_3650: 0, n_18250: 0 } },
      L9_alignment: { primitive: "alignment", intensity: 0, edge_count: 0 },
      L10_signature: {},
    },
    outputs: {
      collapse_state: "none", attractor: "S1",
      state_distribution: { S1: 0.25, S2: 0.25, S3: 0.25, S4: 0.25 },
      P0_P8: {}, geography_tier: null,
      timeline: { short_term_days: 1, mid_term_days: 2, long_term_days: 3 },
      multiplier: 1,
    },
    meta: { engine: "clarity_elins_v2", view_kind: "v2" },
  } as never;
}

function view(runOn?: { rawText: string; region?: string | null } | null) {
  return (
    <MemoryRouter>
      <ElinsV2View envelope={envelope()} runOn={runOn} />
    </MemoryRouter>
  );
}

describe("ElinsV2View — send to corpus", () => {
  beforeEach(() => { mocked.mockReset(); });

  it("★ a run with its input text offers 'send to corpus'; pressing it posts that text", async () => {
    mocked.mockResolvedValue({ ok: true, library_id: "l_fromrun", envelope: {} });
    render(view({ rawText: "the run's own input", region: "us" }));
    const btn = screen.getByTestId("send-to-corpus");
    expect(btn).toBeEnabled();
    fireEvent.click(btn);
    await waitFor(() => expect(screen.getByTestId("send-to-corpus-result")).toBeInTheDocument());
    expect(mocked).toHaveBeenCalledTimes(1);
    expect(mocked).toHaveBeenCalledWith({ text: "the run's own input", region: "us", source: "elins_v2_view" });
    expect(screen.getByTestId("send-to-corpus-result")).toHaveTextContent("l_fromrun");
    expect(screen.getByTestId("send-to-corpus-result").querySelector('a[href="/library"]')).not.toBeNull();
    expect(screen.getByTestId("send-to-corpus")).toHaveTextContent("sent to corpus");
  });

  it("★ after success the button is disabled: a second press cannot mint a duplicate", async () => {
    mocked.mockResolvedValue({ ok: true, library_id: "l_once", envelope: {} });
    render(view({ rawText: "once" }));
    fireEvent.click(screen.getByTestId("send-to-corpus"));
    await waitFor(() => expect(screen.getByTestId("send-to-corpus")).toBeDisabled());
    fireEvent.click(screen.getByTestId("send-to-corpus"));
    expect(mocked).toHaveBeenCalledTimes(1);
  });

  it("★ when the text changes the control is fresh: it never claims the new text was sent", async () => {
    mocked.mockResolvedValue({ ok: true, library_id: "l_A", envelope: {} });
    const { rerender } = render(view({ rawText: "transcript A" }));
    fireEvent.click(screen.getByTestId("send-to-corpus"));
    await waitFor(() => expect(screen.getByTestId("send-to-corpus-result")).toHaveTextContent("l_A"));

    rerender(view({ rawText: "transcript A plus a new turn" }));
    expect(screen.queryByTestId("send-to-corpus-result")).toBeNull();
    expect(screen.getByTestId("send-to-corpus")).toBeEnabled();
    expect(screen.getByTestId("send-to-corpus")).toHaveTextContent("send to corpus");
  });

  it("the button names what it sends", () => {
    render(view({ rawText: "abcdef" }));
    expect(screen.getByTestId("send-to-corpus")).toHaveAttribute("title", expect.stringContaining("6 characters"));
  });

  it("without the run's input text the control is not offered", () => {
    render(view());
    expect(screen.queryByTestId("send-to-corpus")).toBeNull();
  });

  it("an empty input text does not offer the control", () => {
    render(view({ rawText: "" }));
    expect(screen.queryByTestId("send-to-corpus")).toBeNull();
  });

  it("whitespace-only input text does not offer the control (matches the Re-run gate)", () => {
    render(view({ rawText: "   \n\t " }));
    expect(screen.queryByTestId("send-to-corpus")).toBeNull();
  });

  it("a failed post is shown in the footer as an error, not swallowed", async () => {
    mocked.mockRejectedValue(new Error("network down"));
    render(view({ rawText: "t" }));
    fireEvent.click(screen.getByTestId("send-to-corpus"));
    await waitFor(() => expect(screen.getByTestId("send-to-corpus-error")).toBeInTheDocument());
    expect(screen.getByTestId("send-to-corpus-error")).toHaveTextContent("network down");
    // and the member may try again
    expect(screen.getByTestId("send-to-corpus")).toBeEnabled();
  });
});
