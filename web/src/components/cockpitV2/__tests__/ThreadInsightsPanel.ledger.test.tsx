/**
 * #180b (4) -- the thread tab renders what the thread routes carry: created
 * beside updated, the last model, grounding and directives ("—" when none),
 * thread_id / project_id / archived in the messages row's title; the list
 * row carries project_id / created_at / archived in its title.
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

import * as api from "../../../lib/api";
import ThreadInsightsPanel from "../ThreadInsightsPanel";
import SessionListPanel from "../SessionListPanel";
import { cockpit } from "../../../state/cockpitStore";

const DASH = "—";
const META = {
  thread_id: "t1", title: "Cockpit", created_at: 1_787_335_869_001, updated_at: 1_788_553_401_652,
  message_count: 2, archived: false, summary: null, summary_ts_ms: null, project_id: null,
};
const MESSAGES = [
  { role: "user", content: "hi", ts_ms: 1, model: null },
  { role: "assistant", content: "hello", ts_ms: 2, model: "openai:gpt-5.4" },
];

async function mount(meta = META, messages: unknown[] = MESSAGES) {
  vi.mocked(api.listThreads).mockResolvedValue([meta] as never);
  vi.mocked(api.getThread).mockResolvedValue({ meta, messages } as never);
  render(<><SessionListPanel /><ThreadInsightsPanel /></>);
  await act(async () => { await cockpit.thread.actions.init(); });
  await act(async () => { cockpit.thread.actions.setTab("thread"); });
}

afterEach(() => vi.clearAllMocks());

describe("ThreadInsightsPanel — the thread tab (#180b 4)", () => {
  it("★ created, last model, grounding and directives; the keys in titles", async () => {
    await mount();
    expect(screen.getByTestId("thread-created")).not.toHaveTextContent(DASH);
    expect(screen.getByTestId("thread-last-model")).toHaveTextContent("openai:gpt-5.4");
    expect(screen.getByTestId("thread-grounding")).toHaveTextContent(DASH);
    expect(screen.getByTestId("thread-directives")).toHaveTextContent(DASH);
    expect(screen.getByTestId("thread-messages-row")).toHaveAttribute(
      "title", `meta.message_count · meta.thread_id t1 · meta.project_id ${DASH} · meta.archived live`,
    );
    expect(screen.getByTitle("meta.created_at")).toBeInTheDocument();
    expect(screen.getByTestId("thread-title")).toHaveTextContent("Cockpit");
    expect(screen.getByTitle("meta.title")).toBeInTheDocument();
    expect(screen.getByTitle("messages[].model")).toBeInTheDocument();
  });
  it("★ a sent turn's grounding and directives show on the tab; the wire's meta replaces the thread's", async () => {
    await mount();
    vi.mocked(api.postThreadMessage).mockResolvedValue({
      meta: { ...META, message_count: 4, updated_at: 1_788_553_500_000, project_id: "relationships", archived: true },
      user_message: { role: "user", content: "cite this", ts_ms: 3, model: null },
      assistant_message: { role: "assistant", content: "cited", ts_ms: 4, model: "anthropic:claude-haiku-4-5-20251001" },
      model_id: "anthropic:claude-haiku-4-5-20251001",
      grounding_status: "grounded",
      directives: ["cite", "format"],
      directive_metadata: { cite: { status: "grounded" }, format: { status: "formatted" } },
    } as never);
    await act(async () => { await cockpit.thread.actions.send("cite this"); });
    expect(screen.getByTestId("thread-last-model")).toHaveTextContent("anthropic:claude-haiku-4-5-20251001");
    expect(screen.getByTestId("thread-grounding")).toHaveTextContent("grounded");
    expect(screen.getByTestId("thread-directives")).toHaveTextContent("cite grounded · format formatted");
    expect(screen.getByTestId("thread-messages-row")).toHaveAttribute(
      "title", "meta.message_count · meta.thread_id t1 · meta.project_id relationships · meta.archived archived",
    );
  });
  it("no assistant turn yet: the model, grounding and directives all read a dash", async () => {
    await mount({ ...META, message_count: 1 }, [MESSAGES[0]]);
    expect(screen.getByTestId("thread-last-model")).toHaveTextContent(DASH);
    expect(screen.getByTestId("thread-grounding")).toHaveTextContent(DASH);
    expect(screen.getByTestId("thread-directives")).toHaveTextContent(DASH);
  });
  it("the list row carries project_id · created_at · archived in its title", async () => {
    await mount();
    // the thread tab's title row reads "Cockpit" too; the list row is the button
    const row = screen.getAllByText("Cockpit").map((e) => e.closest("button")).find((b) => b !== null);
    expect(row).toHaveAttribute("title", `threads[].project_id ${DASH} · threads[].created_at 2026-08-21 18:11Z · threads[].archived live`);
  });
});
