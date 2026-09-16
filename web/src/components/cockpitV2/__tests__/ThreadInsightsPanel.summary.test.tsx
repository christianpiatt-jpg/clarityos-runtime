/**
 * #304 (CT-1 2026-09-16) -- the summary box says what it read and who wrote
 * it: "last 8,000 of M — messages a-b of c · model X", every number the
 * backend's stamp. A SECOND press inside 10 minutes sends force:true
 * ("re-summarise now"); a press on an older summary sends none; the busy
 * guard stays (a press while one is in flight does nothing).
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";

vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return {
    ...actual, listThreads: vi.fn(), createThread: vi.fn(), getThread: vi.fn(),
    postThreadMessage: vi.fn(), summarizeThread: vi.fn(),
  };
});
vi.mock("../../../lib/elinsV2", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/elinsV2")>("../../../lib/elinsV2");
  return { ...actual, runElinsV2: vi.fn(() => new Promise(() => {})) };
});
vi.mock("../../../lib/emotionalPhysics", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/emotionalPhysics")>("../../../lib/emotionalPhysics");
  return { ...actual, analyzeEmotionalPhysics: vi.fn(() => new Promise(() => {})) };
});
vi.mock("../../../hooks/useLiveCommitSha", () => ({
  useLiveCommitSha: () => ({ sha: "abc1234def5678", loading: false, error: null }),
}));

import * as api from "../../../lib/api";
import ThreadInsightsPanel from "../ThreadInsightsPanel";
import { cockpit, isSummaryRecent, SUMMARY_RECENT_WINDOW_MS } from "../../../state/cockpitStore";
import { summaryBoxLine } from "../../../lib/summaryCurrency";

let n = 0;
function meta(over: Record<string, unknown>) {
  n += 1;
  return {
    thread_id: `s${n}`, title: "Box", created_at: 1, updated_at: 2, message_count: 9, archived: false,
    summary: "a summary", summary_ts_ms: 1, summary_commit_sha: "abc1234def5678", summary_turn: 9, project_id: null,
    ...over,
  };
}

async function mount(m: ReturnType<typeof meta>) {
  vi.mocked(api.listThreads).mockResolvedValue([m] as never);
  vi.mocked(api.getThread).mockResolvedValue({ meta: m, messages: [] } as never);
  render(<ThreadInsightsPanel />);
  await act(async () => { await cockpit.thread.actions.init(); });
  await act(async () => { cockpit.thread.actions.setTab("thread"); });
}

afterEach(() => vi.clearAllMocks());

describe("#304 -- the box line", () => {
  it("★ 'last 8,000 of M — messages a-b of c · model X', every number a stamp", async () => {
    await mount(meta({
      summary_model_id: "anthropic:claude-haiku-4-5-20251001", summary_window_chars: 8000, summary_total_chars: 12345,
      summary_total_messages: 9, summary_window_first_message: 3, summary_window_last_message: 9,
    }));
    expect(screen.getByTestId("thread-summary-currency"))
      .toHaveTextContent("last 8,000 of 12,345 — messages 3-9 of 9 · model anthropic:claude-haiku-4-5-20251001");
  });
  it("an unstamped row reads dashes, never a number", () => {
    expect(summaryBoxLine({})).toBe("last — of — — messages — of — · model —");
    expect(summaryBoxLine(null)).toBe("last — of — — messages — of — · model —");
  });
});

describe("#304 -- the second press inside 10 minutes forces", () => {
  it("isSummaryRecent: younger than the window with a summary; not without one; not older", () => {
    const now = 1_000_000_000_000;
    expect(isSummaryRecent({ summary: "s", summary_ts_ms: now - 60_000 }, now)).toBe(true);
    expect(isSummaryRecent({ summary: "s", summary_ts_ms: now - SUMMARY_RECENT_WINDOW_MS }, now)).toBe(false);
    expect(isSummaryRecent({ summary: null, summary_ts_ms: now - 60_000 }, now)).toBe(false);
    expect(isSummaryRecent(null, now)).toBe(false);
  });

  it("★ a fresh summary: the button says RE-SUMMARISE NOW and the press sends force:true", async () => {
    const m = meta({ summary_ts_ms: Date.now() - 60_000 });
    await mount(m);
    vi.mocked(api.summarizeThread).mockResolvedValue({ ...m, summary: "again" } as never);
    const btn = screen.getByTestId("thread-summarize");
    expect(btn).toHaveTextContent("RE-SUMMARISE NOW");
    await act(async () => { fireEvent.click(btn); });
    expect(api.summarizeThread).toHaveBeenCalledWith(m.thread_id, true);
  });

  it("an older summary: SUMMARIZE, and the press sends no force", async () => {
    const m = meta({ summary_ts_ms: Date.now() - SUMMARY_RECENT_WINDOW_MS - 1 });
    await mount(m);
    vi.mocked(api.summarizeThread).mockResolvedValue({ ...m, summary: "again" } as never);
    const btn = screen.getByTestId("thread-summarize");
    expect(btn).toHaveTextContent("SUMMARIZE");
    await act(async () => { fireEvent.click(btn); });
    expect(api.summarizeThread).toHaveBeenCalledWith(m.thread_id, false);
  });

  it("the busy guard stays: a second press while one is in flight does nothing", async () => {
    const m = meta({ summary_ts_ms: Date.now() - 60_000 });
    await mount(m);
    let release: (v: unknown) => void = () => {};
    vi.mocked(api.summarizeThread).mockImplementation(
      () => new Promise((r) => { release = r as unknown as (v: unknown) => void; }),
    );
    await act(async () => { void cockpit.thread.actions.summarize(); });
    await act(async () => { void cockpit.thread.actions.summarize(); });
    expect(api.summarizeThread).toHaveBeenCalledTimes(1);
    await act(async () => { release({ ...m, summary: "again" }); });
  });
});
