// v61 / Unit 44 — Session route smoke tests.
//
// Mocks the API helpers from ../../lib/api at module scope so the
// component renders without hitting fetch / the real backend.

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import type {
  SessionState,
  SessionStepResult,
  StartSessionResponse,
  StepSessionResponse,
} from "../../lib/api";
import Session from "../Session";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>(
    "../../lib/api",
  );
  return {
    ...actual,
    startSession: vi.fn(),
    stepSession:  vi.fn(),
    getUser:      vi.fn(() => null),
  };
});

import {
  getUser,
  startSession,
  stepSession,
} from "../../lib/api";

const mockStartSession = vi.mocked(startSession);
const mockStepSession  = vi.mocked(stepSession);
const mockGetUser      = vi.mocked(getUser);

// --------------------------------------------------------------------
// Fixtures
// --------------------------------------------------------------------
function makeState(overrides: Partial<SessionState> = {}): SessionState {
  return {
    session_id:  "sess-test-001",
    operator_id: "op_alice",
    vault_state: {},
    history:     [],
    ...overrides,
  };
}

function makeStartResponse(state?: SessionState): StartSessionResponse {
  return { session_state: state ?? makeState() };
}

function makeStepResult(): SessionStepResult {
  return {
    session_id:  "sess-test-001",
    operator_id: "op_alice",
    timestamp:   "2026-05-12T10:00:01+00:00",
    runtime: {
      session_id:  "sess-test-001",
      operator_id: "op_alice",
      timestamp:   "2026-05-12T10:00:01+00:00",
      model_route: { engine: "copilot", reason: "test" },
      runtime: {
        session_id:       "sess-test-001",
        operator_id:      "op_alice",
        timestamp:        "2026-05-12T10:00:01+00:00",
        runtime_decision: "allow",
        runtime_events:   ["runtime_allow"],
        elins_block:      {},
        vault_update:     { elins: { fusion_history: [{}] } },
        operator_view:    { headline: "TEST_HEADLINE", details: {} },
      },
      ui_response: {
        headline: "TEST_HEADLINE",
        body:     "test body sentence describing the step",
        severity: "info",
        tags:     ["alpha", "beta"],
      },
    },
    model: {
      engine:   "copilot",
      request:  {
        model_id: "xai:groq-llama",
        task:     "c",
        prompt_preview: "[ClarityOS operator step]",
      },
      response: {
        ok:       true,
        model_id: "xai:groq-llama",
        provider: "xai",
        text:     "[mock xai:groq-llama] preview…",
        mock:     true,
        ts:       1700000000.0,
      },
      metadata: { provider: "xai", mock: true, ts: 1700000000.0 },
    },
    vault_update: { elins: { fusion_history: [{}] } },
  };
}

function makeStepResponse(): StepSessionResponse {
  return {
    session_state: makeState({ history: [{
      timestamp:        "2026-05-12T10:00:01+00:00",
      intent_type:      "query",
      text:             "do it",
      runtime_decision: "allow",
      engine:           "copilot",
    }] }),
    step_result: makeStepResult(),
  };
}

function renderRoute() {
  return render(
    <MemoryRouter initialEntries={["/session"]}>
      <Session />
    </MemoryRouter>,
  );
}

// --------------------------------------------------------------------
// Setup / teardown
// --------------------------------------------------------------------
beforeEach(() => {
  mockStartSession.mockReset();
  mockStepSession.mockReset();
  mockGetUser.mockReset();
  mockGetUser.mockReturnValue(null);
  try { localStorage.clear(); } catch { /* noop */ }
});

afterEach(() => {
  try { localStorage.clear(); } catch { /* noop */ }
});

// --------------------------------------------------------------------
// Tests
// --------------------------------------------------------------------
describe("Session route", () => {
  test("calls startSession on mount with op_anon default", async () => {
    mockStartSession.mockResolvedValueOnce(makeStartResponse());
    renderRoute();
    await waitFor(() => expect(mockStartSession).toHaveBeenCalledTimes(1));
    expect(mockStartSession).toHaveBeenCalledWith("op_anon");
  });

  test("uses authed user as operator_id when available", async () => {
    mockGetUser.mockReturnValue("op_christian");
    mockStartSession.mockResolvedValueOnce(
      makeStartResponse(makeState({ operator_id: "op_christian" })),
    );
    renderRoute();
    await waitFor(() => expect(mockStartSession).toHaveBeenCalled());
    expect(mockStartSession).toHaveBeenCalledWith("op_christian");
  });

  test("renders the session_id once started", async () => {
    mockStartSession.mockResolvedValueOnce(makeStartResponse());
    renderRoute();
    await waitFor(() =>
      expect(screen.getByText("sess-test-001")).toBeInTheDocument(),
    );
  });

  test("send button disabled until both state ready and text typed", async () => {
    const user = userEvent.setup();
    mockStartSession.mockResolvedValueOnce(makeStartResponse());
    renderRoute();
    const send = await screen.findByRole("button", { name: "SEND" });
    expect(send).toBeDisabled();   // no text yet
    const textarea = screen.getByLabelText("Text") as HTMLTextAreaElement;
    await user.type(textarea, "do it");
    expect(send).not.toBeDisabled();
  });

  test("SEND calls stepSession with text + intent_type", async () => {
    const user = userEvent.setup();
    mockStartSession.mockResolvedValueOnce(makeStartResponse());
    mockStepSession.mockResolvedValueOnce(makeStepResponse());
    renderRoute();
    await screen.findByText("sess-test-001");

    const textarea = screen.getByLabelText("Text") as HTMLTextAreaElement;
    await user.type(textarea, "do it");
    await user.selectOptions(
      screen.getByLabelText("Intent") as HTMLSelectElement,
      "plan",
    );
    await user.click(screen.getByRole("button", { name: "SEND" }));

    await waitFor(() => expect(mockStepSession).toHaveBeenCalledTimes(1));
    const callArgs = mockStepSession.mock.calls[0];
    expect(callArgs[1]).toBe("do it");
    expect(callArgs[2]).toBe("plan");
  });

  test("renders headline + body after step", async () => {
    const user = userEvent.setup();
    mockStartSession.mockResolvedValueOnce(makeStartResponse());
    mockStepSession.mockResolvedValueOnce(makeStepResponse());
    renderRoute();
    await screen.findByText("sess-test-001");

    await user.type(screen.getByLabelText("Text"), "do it");
    await user.click(screen.getByRole("button", { name: "SEND" }));

    await screen.findByText("TEST_HEADLINE");
    expect(
      screen.getByText("test body sentence describing the step"),
    ).toBeInTheDocument();
  });

  test("renders model response text", async () => {
    const user = userEvent.setup();
    mockStartSession.mockResolvedValueOnce(makeStartResponse());
    mockStepSession.mockResolvedValueOnce(makeStepResponse());
    renderRoute();
    await screen.findByText("sess-test-001");

    await user.type(screen.getByLabelText("Text"), "do it");
    await user.click(screen.getByRole("button", { name: "SEND" }));

    await screen.findByText("[mock xai:groq-llama] preview…");
  });

  test("renders tags after step", async () => {
    const user = userEvent.setup();
    mockStartSession.mockResolvedValueOnce(makeStartResponse());
    mockStepSession.mockResolvedValueOnce(makeStepResponse());
    renderRoute();
    await screen.findByText("sess-test-001");

    await user.type(screen.getByLabelText("Text"), "do it");
    await user.click(screen.getByRole("button", { name: "SEND" }));

    await screen.findByText("alpha");
    expect(screen.getByText("beta")).toBeInTheDocument();
  });

  test("error surface renders when startSession rejects", async () => {
    mockStartSession.mockRejectedValueOnce(new Error("boom"));
    renderRoute();
    await screen.findByText(/boom/);
  });

  test("NEW SESSION clears persisted resume id + remints", async () => {
    const user = userEvent.setup();
    mockStartSession
      .mockResolvedValueOnce(makeStartResponse())  // initial
      .mockResolvedValueOnce(makeStartResponse(
        makeState({ session_id: "sess-test-002" }),
      ));
    renderRoute();
    await screen.findByText("sess-test-001");

    await user.click(screen.getByRole("button", { name: "NEW SESSION" }));
    await screen.findByText("sess-test-002");
    expect(mockStartSession).toHaveBeenCalledTimes(2);
  });

  test("resume id loaded from localStorage on mount", async () => {
    try {
      localStorage.setItem("clarityos_session_resume_id", "sess-from-storage");
    } catch { /* noop */ }
    mockStartSession.mockResolvedValueOnce(makeStartResponse());
    renderRoute();
    await waitFor(() => expect(mockStartSession).toHaveBeenCalled());
    const [opId, opts] = mockStartSession.mock.calls[0];
    expect(opId).toBe("op_anon");
    expect(opts).toEqual({ resume: true, sessionId: "sess-from-storage" });
  });

  test("session_id persisted after start", async () => {
    mockStartSession.mockResolvedValueOnce(makeStartResponse());
    renderRoute();
    await screen.findByText("sess-test-001");
    const persisted = localStorage.getItem("clarityos_session_resume_id");
    expect(persisted).toBe("sess-test-001");
  });

  test("history count increments after step", async () => {
    const user = userEvent.setup();
    mockStartSession.mockResolvedValueOnce(makeStartResponse());
    mockStepSession.mockResolvedValueOnce(makeStepResponse());
    renderRoute();
    await screen.findByText("sess-test-001");
    expect(screen.getByText("0 step(s)")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Text"), "do it");
    await user.click(screen.getByRole("button", { name: "SEND" }));

    await screen.findByText("1 step(s)");
  });
});
