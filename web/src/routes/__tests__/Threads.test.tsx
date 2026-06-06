// v48 — Threads route tests. Mocks the API helpers from ../../lib/api
// at module scope so the component renders without hitting fetch /
// localStorage / the real backend. Vitest + @testing-library/react.

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import type {
  GroundingStatus,
  ThreadDetail,
  ThreadMessageResult,
  ThreadMeta,
} from "../../lib/api";
import Threads from "../Threads";

// ----------------------------------------------------------------------------
// API mocks. All calls return promises so the route's loading/idle states
// behave the same way they do against a real backend.
// ----------------------------------------------------------------------------
vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>(
    "../../lib/api",
  );
  return {
    ...actual,
    // ApiError stays real so `e instanceof ApiError` checks inside
    // Threads.tsx still work if a test wires an error case.
    listThreads: vi.fn(),
    createThread: vi.fn(),
    getThread: vi.fn(),
    postThreadMessage: vi.fn(),
    renameThread: vi.fn(),
    deleteThread: vi.fn(),
    summarizeThread: vi.fn(),
  };
});

// Pull the mocked references after the mock is registered.
import {
  createThread,
  deleteThread,
  getThread,
  listThreads,
  postThreadMessage,
  renameThread,
  summarizeThread,
} from "../../lib/api";

const mockListThreads = vi.mocked(listThreads);
const mockCreateThread = vi.mocked(createThread);
const mockGetThread = vi.mocked(getThread);
const mockPostThreadMessage = vi.mocked(postThreadMessage);
const mockRenameThread = vi.mocked(renameThread);
const mockDeleteThread = vi.mocked(deleteThread);
const mockSummarizeThread = vi.mocked(summarizeThread);

// ----------------------------------------------------------------------------
// Fixtures
// ----------------------------------------------------------------------------
function makeMeta(overrides: Partial<ThreadMeta> = {}): ThreadMeta {
  return {
    thread_id: "thr_a",
    title: "First thread",
    created_at: 1_700_000_000_000,
    updated_at: 1_700_000_000_000,
    message_count: 0,
    archived: false,
    // v50 — both null until a Summarize call lands.
    summary: null,
    summary_ts_ms: null,
    ...overrides,
  };
}

function makeDetail(
  meta: ThreadMeta,
  msgs: ThreadDetail["messages"] = [],
): ThreadDetail {
  return { meta, messages: msgs };
}

// ----------------------------------------------------------------------------
// Lifecycle
// ----------------------------------------------------------------------------
beforeEach(() => {
  vi.clearAllMocks();
  // Stub window.confirm so the delete flow proceeds without a prompt.
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ----------------------------------------------------------------------------
// Tests
// ----------------------------------------------------------------------------
describe("Threads route", () => {
  test("renders threads returned by API in updated_at-desc order", async () => {
    const older = makeMeta({
      thread_id: "thr_old",
      title: "Older",
      updated_at: 1_700_000_000_000,
    });
    const newer = makeMeta({
      thread_id: "thr_new",
      title: "Newer",
      updated_at: 1_700_000_500_000,
    });
    // Backend already returns newest-first; pass the order in here.
    mockListThreads.mockResolvedValue([newer, older]);

    render(<MemoryRouter><Threads /></MemoryRouter>);

    expect(await screen.findByText("Newer")).toBeInTheDocument();
    expect(screen.getByText("Older")).toBeInTheDocument();

    // Both list-item buttons are rendered; verify newer appears first
    // by reading the order from the DOM.
    const buttons = screen.getAllByRole("button", { name: /Open thread/i });
    expect(buttons[0]).toHaveTextContent("Newer");
    expect(buttons[1]).toHaveTextContent("Older");

    // Header count badge renders.
    expect(screen.getByText(/2 threads/)).toBeInTheDocument();
  });

  test("clicking a thread loads its messages", async () => {
    const meta = makeMeta({ thread_id: "thr_a", title: "Conversation" });
    mockListThreads.mockResolvedValue([meta]);
    mockGetThread.mockResolvedValue(
      makeDetail({ ...meta, message_count: 2 }, [
        { role: "user", content: "hello there", ts_ms: 1, model: null },
        {
          role: "assistant",
          content: "hi back",
          ts_ms: 2,
          model: "anthropic:claude-3.7",
        },
      ]),
    );

    const user = userEvent.setup();
    render(<MemoryRouter><Threads /></MemoryRouter>);

    await screen.findByText("Conversation");
    await user.click(
      screen.getByRole("button", { name: /Open thread Conversation/i }),
    );

    await waitFor(() => {
      expect(mockGetThread).toHaveBeenCalledWith("thr_a");
    });
    expect(await screen.findByText("hello there")).toBeInTheDocument();
    expect(screen.getByText("hi back")).toBeInTheDocument();
    // Assistant model line renders under the assistant bubble.
    expect(screen.getByTestId("assistant-model")).toHaveTextContent(
      "anthropic:claude-3.7",
    );
  });

  test("sending a message renders the assistant reply", async () => {
    const meta = makeMeta({ thread_id: "thr_a", title: "Chat", message_count: 0 });
    mockListThreads.mockResolvedValue([meta]);
    mockGetThread.mockResolvedValue(makeDetail(meta, []));

    const reply: ThreadMessageResult = {
      meta: { ...meta, message_count: 2, updated_at: 1_700_000_900_000 },
      user_message: { role: "user", content: "ping", ts_ms: 100, model: null },
      assistant_message: {
        role: "assistant",
        content: "pong from the kernel",
        ts_ms: 101,
        model: "anthropic:claude-3.7",
      },
      model_id: "anthropic:claude-3.7",
    };
    mockPostThreadMessage.mockResolvedValue(reply);

    const user = userEvent.setup();
    render(<MemoryRouter><Threads /></MemoryRouter>);

    await screen.findByText("Chat");
    await user.click(
      screen.getByRole("button", { name: /Open thread Chat/i }),
    );

    // Thread loads + composer is reachable.
    const composer = await screen.findByLabelText("Compose message");
    await user.type(composer, "ping");
    await user.click(screen.getByRole("button", { name: /^SEND$/ }));

    await waitFor(() => {
      expect(mockPostThreadMessage).toHaveBeenCalledWith("thr_a", "ping");
    });
    expect(await screen.findByText("ping")).toBeInTheDocument();
    expect(await screen.findByText("pong from the kernel")).toBeInTheDocument();
  });

  test("creating a new thread refreshes the list and selects it", async () => {
    mockListThreads.mockResolvedValueOnce([]);   // initial empty
    const fresh = makeMeta({
      thread_id: "thr_new",
      title: null,
      message_count: 0,
      updated_at: 1_700_001_000_000,
    });
    mockCreateThread.mockResolvedValue(fresh);
    mockListThreads.mockResolvedValueOnce([fresh]);
    mockGetThread.mockResolvedValue(makeDetail(fresh, []));

    const user = userEvent.setup();
    render(<MemoryRouter><Threads /></MemoryRouter>);

    await screen.findByText(/No threads yet/);
    await user.click(screen.getByRole("button", { name: /\+ NEW/ }));

    await waitFor(() => expect(mockCreateThread).toHaveBeenCalled());
    // The newly-created thread is auto-selected → getThread is fetched.
    await waitFor(() => expect(mockGetThread).toHaveBeenCalledWith("thr_new"));
    // Detail header renders the (null-title) thread as "Untitled Thread";
    // the list also shows the same label, so disambiguate by role.
    expect(
      await screen.findByRole("heading", { level: 2, name: "Untitled Thread" }),
    ).toBeInTheDocument();
  });

  test("rename updates the thread title", async () => {
    const meta = makeMeta({ thread_id: "thr_r", title: "Old name" });
    mockListThreads.mockResolvedValue([meta]);
    mockGetThread.mockResolvedValue(makeDetail(meta, []));
    mockRenameThread.mockResolvedValue({ ...meta, title: "New name" });

    const user = userEvent.setup();
    render(<MemoryRouter><Threads /></MemoryRouter>);

    await screen.findByText("Old name");
    await user.click(
      screen.getByRole("button", { name: /Open thread Old name/i }),
    );

    // Rename action surfaces the form.
    await user.click(await screen.findByRole("button", { name: /^RENAME$/ }));
    const titleInput = await screen.findByLabelText(/Thread title/);
    fireEvent.change(titleInput, { target: { value: "New name" } });
    await user.click(screen.getByRole("button", { name: /^SAVE$/ }));

    await waitFor(() => {
      expect(mockRenameThread).toHaveBeenCalledWith("thr_r", "New name");
    });
    // The detail header now shows the new title.
    expect(
      await screen.findByRole("heading", { level: 2, name: "New name" }),
    ).toBeInTheDocument();
  });

  test("delete removes the thread from the list", async () => {
    const a = makeMeta({ thread_id: "thr_a", title: "Doomed" });
    const b = makeMeta({ thread_id: "thr_b", title: "Survivor" });
    mockListThreads.mockResolvedValue([a, b]);
    mockGetThread.mockResolvedValue(makeDetail(a, []));
    mockDeleteThread.mockResolvedValue(undefined);

    const user = userEvent.setup();
    render(<MemoryRouter><Threads /></MemoryRouter>);

    // Pick the thread we'll delete.
    await user.click(
      await screen.findByRole("button", { name: /Open thread Doomed/i }),
    );
    await screen.findByRole("heading", { level: 2, name: "Doomed" });

    await user.click(screen.getByRole("button", { name: /^DELETE$/ }));

    await waitFor(() => {
      expect(mockDeleteThread).toHaveBeenCalledWith("thr_a");
    });

    // Doomed is gone from the list; Survivor remains.
    await waitFor(() => {
      expect(screen.queryByText("Doomed")).not.toBeInTheDocument();
    });
    expect(screen.getByText("Survivor")).toBeInTheDocument();
    // No active thread → placeholder copy returns.
    expect(
      screen.getByText(/Pick a thread on the left/),
    ).toBeInTheDocument();
  });

  test("send button is disabled while composer is empty", async () => {
    const meta = makeMeta({ thread_id: "thr_e", title: "Empty composer" });
    mockListThreads.mockResolvedValue([meta]);
    mockGetThread.mockResolvedValue(makeDetail(meta, []));

    const user = userEvent.setup();
    render(<MemoryRouter><Threads /></MemoryRouter>);

    await user.click(
      await screen.findByRole("button", { name: /Open thread Empty composer/i }),
    );
    const sendBtn = await screen.findByRole("button", { name: /^SEND$/ });
    expect(sendBtn).toBeDisabled();

    const composer = screen.getByLabelText("Compose message");
    await user.type(composer, "   ");
    expect(sendBtn).toBeDisabled(); // whitespace-only stays disabled

    await user.type(composer, "real content");
    expect(sendBtn).not.toBeDisabled();
  });

  test("empty state copy renders when no threads exist", async () => {
    mockListThreads.mockResolvedValue([]);
    render(<MemoryRouter><Threads /></MemoryRouter>);
    expect(
      await screen.findByText(/No threads yet/),
    ).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // v50 — Thread summaries
  // -------------------------------------------------------------------------
  test("v50: summary line appears in list when present", async () => {
    const meta = makeMeta({
      thread_id: "thr_s",
      title: "Has summary",
      summary: "the user is planning q4 kickoff",
      summary_ts_ms: 1_700_000_500_000,
    });
    mockListThreads.mockResolvedValue([meta]);
    render(<MemoryRouter><Threads /></MemoryRouter>);
    expect(
      await screen.findByTestId("thread-list-summary"),
    ).toHaveTextContent("the user is planning q4 kickoff");
  });

  test("v50: list row omits summary line when summary is null", async () => {
    const meta = makeMeta({ thread_id: "thr_n", title: "No summary" });
    mockListThreads.mockResolvedValue([meta]);
    render(<MemoryRouter><Threads /></MemoryRouter>);
    await screen.findByText("No summary");
    expect(screen.queryByTestId("thread-list-summary")).toBeNull();
  });

  test("v50: SUMMARIZE button calls API and updates UI", async () => {
    const meta = makeMeta({ thread_id: "thr_q", title: "To be summarized" });
    mockListThreads.mockResolvedValue([meta]);
    mockGetThread.mockResolvedValue(makeDetail(meta, [
      { role: "user", content: "kick it off", ts_ms: 1, model: null },
    ]));
    mockSummarizeThread.mockResolvedValue({
      ...meta,
      summary: "we kicked off the project",
      summary_ts_ms: 1_700_001_000_000,
    });

    const user = userEvent.setup();
    render(<MemoryRouter><Threads /></MemoryRouter>);

    await user.click(
      await screen.findByRole("button", { name: /Open thread To be summarized/i }),
    );
    await screen.findByRole("heading", { level: 2, name: "To be summarized" });

    // No summary card before the call.
    expect(screen.queryByTestId("thread-summary-card")).toBeNull();

    await user.click(screen.getByRole("button", { name: /^SUMMARIZE$/ }));

    await waitFor(() => {
      expect(mockSummarizeThread).toHaveBeenCalledWith("thr_q");
    });
    const card = await screen.findByTestId("thread-summary-card");
    expect(card).toHaveTextContent("we kicked off the project");
    // The list row also picks up the new summary (optimistic mirror).
    expect(
      await screen.findByTestId("thread-list-summary"),
    ).toHaveTextContent("we kicked off the project");
  });

  // -------------------------------------------------------------------------
  // A19 — #cite grounding badge (read-only, per-turn)
  // -------------------------------------------------------------------------
  async function sendCiteTurn(grounding_status: GroundingStatus | null) {
    const meta = makeMeta({
      thread_id: "thr_cite",
      title: "Cite chat",
      message_count: 0,
    });
    const reply: ThreadMessageResult = {
      meta: { ...meta, message_count: 2, updated_at: meta.updated_at + 1000 },
      user_message: { role: "user", content: "#cite who?", ts_ms: 100, model: null },
      assistant_message: {
        role: "assistant",
        content: "According to the report, the answer is given.",
        ts_ms: 101,
        model: "anthropic:claude-3.7",
      },
      model_id: "anthropic:claude-3.7",
      grounding_status,
    };
    mockListThreads.mockResolvedValue([meta]);
    mockGetThread.mockResolvedValue(makeDetail(meta, []));
    mockPostThreadMessage.mockResolvedValue(reply);

    const user = userEvent.setup();
    render(<MemoryRouter><Threads /></MemoryRouter>);
    await screen.findByText("Cite chat");
    await user.click(screen.getByRole("button", { name: /Open thread Cite chat/i }));
    const composer = await screen.findByLabelText("Compose message");
    await user.type(composer, "#cite who?");
    await user.click(screen.getByRole("button", { name: /^SEND$/ }));
  }

  test("A19: grounded reply shows a 'Grounding: OK' badge", async () => {
    await sendCiteTurn("grounded");
    const badge = await screen.findByTestId("grounding-badge");
    expect(badge).toHaveTextContent(/Grounding: OK/i);
    expect(badge).toHaveAttribute("data-grounding", "grounded");
  });

  test("A19: incomplete reply shows a 'Grounding: Incomplete' badge", async () => {
    await sendCiteTurn("incomplete");
    const badge = await screen.findByTestId("grounding-badge");
    expect(badge).toHaveTextContent(/Grounding: Incomplete/i);
    expect(badge).toHaveAttribute("data-grounding", "incomplete");
  });

  test("A19: non-#cite reply (null grounding_status) renders no badge", async () => {
    await sendCiteTurn(null);
    // The assistant reply itself renders…
    expect(
      await screen.findByText("According to the report, the answer is given."),
    ).toBeInTheDocument();
    // …but there is no grounding badge.
    expect(screen.queryByTestId("grounding-badge")).toBeNull();
  });

  test("A19: badge sits alongside the model footer, not replacing it", async () => {
    await sendCiteTurn("grounded");
    expect(await screen.findByTestId("assistant-model")).toHaveTextContent(
      "anthropic:claude-3.7",
    );
    expect(screen.getByTestId("grounding-badge")).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // A30 — unified directive badges (read-only, per-turn)
  // -------------------------------------------------------------------------
  async function sendDirectiveTurn(extra: Partial<ThreadMessageResult>) {
    const meta = makeMeta({ thread_id: "thr_dir", title: "Dir chat", message_count: 0 });
    const reply: ThreadMessageResult = {
      meta: { ...meta, message_count: 2, updated_at: meta.updated_at + 1000 },
      user_message: { role: "user", content: "#structure go", ts_ms: 100, model: null },
      assistant_message: {
        role: "assistant", content: "- a\n- b", ts_ms: 101, model: "anthropic:claude-3.7",
      },
      model_id: "anthropic:claude-3.7",
      ...extra,
    };
    mockListThreads.mockResolvedValue([meta]);
    mockGetThread.mockResolvedValue(makeDetail(meta, []));
    mockPostThreadMessage.mockResolvedValue(reply);

    const user = userEvent.setup();
    render(<MemoryRouter><Threads /></MemoryRouter>);
    await screen.findByText("Dir chat");
    await user.click(screen.getByRole("button", { name: /Open thread Dir chat/i }));
    const composer = await screen.findByLabelText("Compose message");
    await user.type(composer, "#structure go");
    await user.click(screen.getByRole("button", { name: /^SEND$/ }));
  }

  test("A30: a non-cite directive renders a directive badge", async () => {
    await sendDirectiveTurn({
      directives: ["structure"],
      directive_metadata: { structure: { status: "formatted", changed: true } },
    });
    const badge = await screen.findByTestId("directive-badge");
    expect(badge).toHaveTextContent(/Structure: formatted/i);
    expect(badge).toHaveAttribute("data-directive", "structure");
  });

  test("A30: cite keeps the grounding badge and is NOT double-rendered", async () => {
    await sendDirectiveTurn({
      grounding_status: "grounded",
      directives: ["cite"],
      directive_metadata: { cite: { status: "grounded", retry_used: false } },
    });
    expect(await screen.findByTestId("grounding-badge")).toBeInTheDocument();
    // cite is excluded from the generic directive badges (no duplicate).
    expect(screen.queryByTestId("directive-badge")).toBeNull();
  });

  test("A30: stacked cite + structure render both badge kinds", async () => {
    await sendDirectiveTurn({
      grounding_status: "grounded",
      directives: ["cite", "structure"],
      directive_metadata: {
        cite: { status: "grounded", retry_used: false },
        structure: { status: "formatted", changed: true },
      },
    });
    expect(await screen.findByTestId("grounding-badge")).toBeInTheDocument();
    expect(await screen.findByTestId("directive-badge")).toHaveAttribute(
      "data-directive", "structure",
    );
  });

  test("A30: no directives -> no directive badges (model footer still shows)", async () => {
    await sendDirectiveTurn({ directives: [], directive_metadata: {} });
    expect(await screen.findByTestId("assistant-model")).toBeInTheDocument();
    expect(screen.queryByTestId("directive-badge")).toBeNull();
    expect(screen.queryByTestId("grounding-badge")).toBeNull();
  });
});
