/**
 * A19/A30 acceptance for the CockpitV2 ChatPanel directive surface.
 *
 * The payloads below are the shapes the live backend returns today for
 * `POST /me/threads/{id}/message` — the "#primitives" case is the production
 * response quoted in the work order, verbatim, including its counts block.
 *
 * These are frontend acceptance tests: they prove the panel renders the badge
 * from a real payload. They do not exercise the model lane that produces it.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return {
    ...actual,
    listThreads: vi.fn(),
    createThread: vi.fn(),
    getThread: vi.fn(),
    postThreadMessage: vi.fn(),
    summarizeThread: vi.fn(),
    renameThread: vi.fn(),
    deleteThread: vi.fn(),
  };
});

import * as api from "../../../lib/api";
import ChatPanel from "../ChatPanel";
import { cockpit } from "../../../state/cockpitStore";

const META = {
  thread_id: "t1", title: "Cockpit", created_at: 1, updated_at: 2,
  message_count: 0, archived: false, summary: null, summary_ts_ms: null,
};

function reply(extra: Record<string, unknown>) {
  return {
    meta: { ...META, message_count: 2 },
    user_message: { role: "user", content: "msg", ts_ms: 10, model: null },
    assistant_message: { role: "assistant", content: "reply", ts_ms: 11, model: "openai:gpt-5.4" },
    ...extra,
  };
}

beforeEach(() => {
  vi.mocked(api.listThreads).mockResolvedValue([META] as never);
  vi.mocked(api.getThread).mockResolvedValue({ meta: META, messages: [] } as never);
});
afterEach(() => vi.clearAllMocks());

async function mountAndSend(text: string) {
  render(<ChatPanel />);
  // the store init normally runs from bootstrapCockpit() on auth
  await act(async () => { await cockpit.thread.actions.init(); });
  await waitFor(() => expect(screen.getByPlaceholderText("Message…")).toBeEnabled());
  await userEvent.type(screen.getByPlaceholderText("Message…"), text);
  await userEvent.click(screen.getByRole("button", { name: /send/i }));
}

describe("CockpitV2 ChatPanel — directive surface", () => {
  it("ACCEPTANCE: #primitives renders a directive badge reading 'Primitives: extracted'", async () => {
    vi.mocked(api.postThreadMessage).mockResolvedValue(
      reply({
        grounding_status: null,
        directives: ["primitives"],
        directive_metadata: {
          primitives: {
            status: "extracted",
            counts: { P1: 11, P2: 11, P3: 8, P4: 0, Ts: 0, Te: 0, M: 0, hydronic: 2 },
          },
        },
      }) as never,
    );
    await mountAndSend("#primitives break this down");

    const badge = await screen.findByTestId("directive-badge");
    expect(badge).toHaveAttribute("data-directive", "primitives");
    expect(badge).toHaveTextContent("Primitives: extracted");
  });

  it("ACCEPTANCE: a plain message renders no badge at all", async () => {
    vi.mocked(api.postThreadMessage).mockResolvedValue(
      reply({ grounding_status: null, directives: [], directive_metadata: {} }) as never,
    );
    await mountAndSend("just a plain message");

    await screen.findByText("reply");
    expect(screen.queryByTestId("directive-badge")).toBeNull();
    expect(screen.queryByTestId("grounding-badge")).toBeNull();
    // the model footer still shows — the row is not suppressed wholesale
    expect(screen.getByTestId("assistant-model")).toHaveTextContent("openai:gpt-5.4");
  });

  it("#cite renders the grounding badge, and cite is not double-rendered", async () => {
    vi.mocked(api.postThreadMessage).mockResolvedValue(
      reply({
        grounding_status: "grounded",
        directives: ["cite"],
        directive_metadata: { cite: { status: "grounded", retry_used: true } },
      }) as never,
    );
    await mountAndSend("#cite the source");

    expect(await screen.findByTestId("grounding-badge")).toHaveTextContent("Grounding: OK");
    expect(screen.queryByTestId("directive-badge")).toBeNull();
  });
});
