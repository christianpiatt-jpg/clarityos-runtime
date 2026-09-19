// #366 A6 -- the sovereign seat on /session: a diagnostic step runs on the
// local engine (hard-pinned); when the local engine answered as the router's
// mock there is no daemon behind the seat, and the page names that. A mock
// is never rendered as a reading. Same harness as Session.test.tsx.
//
// Mutation: render the line on mock alone -> the copilot/mock case shows it;
// never render -> the local/mock case lacks it.

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import type { SessionState, SessionStepResult, StartSessionResponse, StepSessionResponse } from "../../lib/api";
import Session from "../Session";

const SNAP = vi.hoisted(() => ({
  session: "sid-test",
  user: "u",
  profile: null as null | { user: string; operator_id?: string | null },
}));

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    startSession: vi.fn(),
    stepSession:  vi.fn(),
    getProfile:   vi.fn(() => SNAP.profile),
  };
});

vi.mock("../../lib/auth", () => ({
  getAuthSnapshot: () => SNAP,
  subscribeAuth:   () => () => {},
}));

import { startSession, stepSession } from "../../lib/api";

const mockStartSession = vi.mocked(startSession);
const mockStepSession  = vi.mocked(stepSession);

function makeState(): SessionState {
  return { session_id: "sess-test-001", operator_id: "op_alice", vault_state: {}, history: [] };
}

function makeStart(): StartSessionResponse {
  return { session_state: makeState() };
}

function makeStep(engine: string, mock: boolean): SessionStepResult {
  const model_id = engine === "local" ? "local:llama3.1" : "xai:groq-llama";
  return {
    session_id:  "sess-test-001",
    operator_id: "op_alice",
    timestamp:   "2026-09-19T10:00:01+00:00",
    runtime: {
      session_id:       "sess-test-001",
      operator_id:      "op_alice",
      timestamp:        "2026-09-19T10:00:01+00:00",
      model_route:      { engine, reason: "test" },
      runtime: {
        session_id:       "sess-test-001",
        operator_id:      "op_alice",
        timestamp:        "2026-09-19T10:00:01+00:00",
        runtime_decision: "allow",
        runtime_events:   ["runtime_allow"],
        elins_block:      {},
        vault_update:     { elins: { fusion_history: [{}] } },
        operator_view:    { headline: "TEST_HEADLINE", details: {} },
      },
      ui_response: { headline: "TEST_HEADLINE", body: "body", severity: "info", tags: [] },
    },
    model: {
      engine,
      request:  { model_id, task: "(pinned)", prompt_preview: "[ClarityOS ep-up.v1] lane=role direction=diagnostic" },
      response: {
        ok: true, model_id, provider: engine === "local" ? "local" : "xai",
        text: mock && engine === "local"
          ? "sovereign seat not provisioned — no local model answered; 1 rows carried no reading"
          : "reading: undefined — 0 of 1 rows carried a value (1 lanes returned no reading)",
        mock, ts: 1700000000.0,
      },
      metadata: { provider: engine === "local" ? "local" : "xai", mock, ts: 1700000000.0, provisioned: !(engine === "local" && mock) },
    },
    vault_update: { elins: { fusion_history: [{}] } },
  };
}

function makeStepResponse(engine: string, mock: boolean): StepSessionResponse {
  return {
    session_state: { ...makeState(), history: [{ timestamp: "2026-09-19T10:00:01+00:00", intent_type: "diagnostic", text: "do it", runtime_decision: "allow", engine: engine as never }] },
    step_result: makeStep(engine, mock),
  };
}

function renderRoute() {
  return render(
    <MemoryRouter initialEntries={["/session"]}>
      <Session />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  mockStartSession.mockReset();
  mockStepSession.mockReset();
  SNAP.profile = { user: "u", operator_id: "op_alice" };
  try { localStorage.clear(); } catch { /* noop */ }
});

afterEach(() => {
  try { localStorage.clear(); } catch { /* noop */ }
});

async function stepWith(engine: string, mock: boolean) {
  mockStartSession.mockResolvedValueOnce(makeStart());
  mockStepSession.mockResolvedValueOnce(makeStepResponse(engine, mock));
  renderRoute();
  await waitFor(() => expect(mockStartSession).toHaveBeenCalled());
  const box = await screen.findByPlaceholderText("e.g. what should the operator do next?");
  await userEvent.type(box, "what is my state");
  await userEvent.click(screen.getByRole("button", { name: /send|step|run/i }));
  await waitFor(() => expect(mockStepSession).toHaveBeenCalled());
}

describe("Session route — the sovereign seat (#366 A6)", () => {
  test("a local engine answering as the mock names the seat un-provisioned", async () => {
    await stepWith("local", true);
    expect(await screen.findByTestId("session-sovereign")).toHaveTextContent("sovereign seat not provisioned");
  });

  test("a mock from a vendor engine is not the sovereign seat", async () => {
    await stepWith("copilot", true);
    await screen.findByText("MODEL RESPONSE");
    expect(screen.queryByTestId("session-sovereign")).toBeNull();
  });

  test("a local engine that really answered shows no line", async () => {
    await stepWith("local", false);
    await screen.findByText("MODEL RESPONSE");
    expect(screen.queryByTestId("session-sovereign")).toBeNull();
  });
});
