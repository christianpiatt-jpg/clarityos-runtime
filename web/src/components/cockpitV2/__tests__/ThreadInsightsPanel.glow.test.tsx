/**
 * #190 / #176 -- the summary card glows by TURNS: green (fresh) at the turn
 * it was made, by the running code; yellow (aged) when one axis broke;
 * magenta (old) when both did or the row carries no stamp. The caption
 * reads "made turn a · now turn b · running <sha7>", then the model and the
 * window it read ("—" when the backend did not stamp them). No clock.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";

vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, listThreads: vi.fn(), createThread: vi.fn(), getThread: vi.fn(), postThreadMessage: vi.fn() };
});
vi.mock("../../../lib/elinsV2", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/elinsV2")>("../../../lib/elinsV2");
  return { ...actual, runElinsV2: vi.fn(() => new Promise(() => {})) };
});
vi.mock("../../../lib/emotionalPhysics", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/emotionalPhysics")>("../../../lib/emotionalPhysics");
  return { ...actual, analyzeEmotionalPhysics: vi.fn(() => new Promise(() => {})) };
});
const LIVE = vi.hoisted(() => ({ sha: "abc1234def5678" as string | null }));
vi.mock("../../../hooks/useLiveCommitSha", () => ({
  useLiveCommitSha: () => ({ sha: LIVE.sha, loading: false, error: null }),
}));

import * as api from "../../../lib/api";
import ThreadInsightsPanel from "../ThreadInsightsPanel";
import { cockpit } from "../../../state/cockpitStore";

const SHA = "abc1234def5678";
let n = 0;
function meta(over: Record<string, unknown>) {
  n += 1;
  return {
    thread_id: `g${n}`, title: "Glow", created_at: 1, updated_at: 2, message_count: 3, archived: false,
    summary: "a summary", summary_ts_ms: 1, summary_commit_sha: SHA, summary_turn: 3, project_id: null,
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

afterEach(() => { vi.clearAllMocks(); LIVE.sha = SHA; });

describe("ThreadInsightsPanel — the summary glow (#190) and its caption (#176)", () => {
  it("★ fresh: made at this turn by this code -> green, the caption in turns", async () => {
    await mount(meta({}));
    const card = screen.getByTestId("thread-summary-card");
    expect(card).toHaveAttribute("data-currency", "fresh");
    expect(card.className).toContain("is-fresh");
    expect(screen.getByTestId("thread-summary-currency"))
      .toHaveTextContent("fresh · made turn 3 · now turn 3 · running abc1234 · model — · last — of —");
  });

  it("★ aged: one more turn -> yellow; the same turn on other code -> yellow", async () => {
    await mount(meta({ message_count: 4 }));
    expect(screen.getByTestId("thread-summary-card")).toHaveAttribute("data-currency", "aged");
    expect(screen.getByTestId("thread-summary-currency")).toHaveTextContent("aged · made turn 3 · now turn 4");
  });

  it("aged on the sha axis: live code moved, same turn", async () => {
    LIVE.sha = "0000000ffff";
    await mount(meta({}));
    expect(screen.getByTestId("thread-summary-card")).toHaveAttribute("data-currency", "aged");
    expect(screen.getByTestId("thread-summary-currency")).toHaveTextContent("running 0000000");
  });

  it("★ old: no stamp on the row -> magenta, \"made turn —\"; and both axes broken -> magenta", async () => {
    await mount(meta({ summary_turn: undefined, summary_commit_sha: null }));
    const card = screen.getByTestId("thread-summary-card");
    expect(card).toHaveAttribute("data-currency", "old");
    expect(card.className).toContain("is-old");
    expect(screen.getByTestId("thread-summary-currency")).toHaveTextContent("old · made turn — · now turn 3 · running abc1234");
  });

  it("no clock: the timestamps do not move the verdict", async () => {
    await mount(meta({ summary_ts_ms: 1, updated_at: 9_999_999_999_999 }));
    expect(screen.getByTestId("thread-summary-card")).toHaveAttribute("data-currency", "fresh");
  });

  it("#176 -- a stamped model and window read into the caption", async () => {
    await mount(meta({ summary_model_id: "anthropic:claude-haiku-4-5-20251001", summary_window_chars: 4000, summary_total_chars: 9000 }));
    expect(screen.getByTestId("thread-summary-currency"))
      .toHaveTextContent("model anthropic:claude-haiku-4-5-20251001 · last 4000 of 9000");
  });
});
