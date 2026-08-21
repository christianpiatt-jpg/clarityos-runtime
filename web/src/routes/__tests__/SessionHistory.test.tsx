// v63 / Unit 47 — SessionHistory route smoke tests.

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import type {
  SessionDetailResponse,
  SessionListResponse,
  SessionState,
} from "../../lib/api";
import SessionHistory from "../SessionHistory";

// C1: operator_id comes from the auth snapshot (hydrated profile);
// refresh() re-reads getProfile(). Tests assign SNAP.profile pre-render.
const SNAP = vi.hoisted(() => ({
  session: "sid-test",
  user: "u",
  profile: null as null | { user: string; operator_id?: string | null },
}));

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>(
    "../../lib/api",
  );
  return {
    ...actual,
    listOperatorSessions: vi.fn(),
    getSessionDetail:     vi.fn(),
    getProfile:           vi.fn(() => SNAP.profile),
  };
});

vi.mock("../../lib/auth", () => ({
  getAuthSnapshot: () => SNAP,
  subscribeAuth:   () => () => {},
}));

import {
  getSessionDetail,
  listOperatorSessions,
} from "../../lib/api";

const mockList   = vi.mocked(listOperatorSessions);
const mockDetail = vi.mocked(getSessionDetail);

// --------------------------------------------------------------------
// Fixtures
// --------------------------------------------------------------------
function makeListResponse(operatorId: string = "op_anon"): SessionListResponse {
  return {
    operator_id: operatorId,
    sessions: [
      {
        session_id:  "sess-001",
        operator_id: operatorId,
        history_len: 2,
        timestamp:   "2026-05-12T10:00:02+00:00",
      },
      {
        session_id:  "sess-000",
        operator_id: operatorId,
        history_len: 1,
        timestamp:   "2026-05-12T09:00:00+00:00",
      },
    ],
  };
}

function makeEmptyListResponse(operatorId: string = "op_anon"): SessionListResponse {
  return { operator_id: operatorId, sessions: [] };
}

function makeDetailResponse(sessionId: string = "sess-001"): SessionDetailResponse {
  const state: SessionState = {
    session_id:  sessionId,
    operator_id: "op_anon",
    vault_state: {},
    history: [
      {
        timestamp:        "2026-05-12T10:00:01+00:00",
        intent_type:      "query",
        text:             "first step",
        runtime_decision: "allow",
        engine:           "copilot",
      },
      {
        timestamp:        "2026-05-12T10:00:02+00:00",
        intent_type:      "plan",
        text:             "second step",
        runtime_decision: "warn",
        engine:           "claude",
      },
    ],
  };
  return { session_state: state };
}

function renderRoute() {
  return render(
    <MemoryRouter initialEntries={["/session/history"]}>
      <SessionHistory />
    </MemoryRouter>,
  );
}

// --------------------------------------------------------------------
// Setup / teardown
// --------------------------------------------------------------------
beforeEach(() => {
  mockList.mockReset();
  mockDetail.mockReset();
  SNAP.profile = { user: "u", operator_id: "op_alice" };
});

afterEach(() => {
  try { localStorage.clear(); } catch { /* noop */ }
});

// --------------------------------------------------------------------
// Tests
// --------------------------------------------------------------------
describe("SessionHistory route", () => {
  test("calls listOperatorSessions on mount (server uses authed id)", async () => {
    // v64 / Unit 66 — argument is now decorative; server uses authed
    // identity. Just confirm the call happens.
    mockList.mockResolvedValueOnce(makeEmptyListResponse());
    renderRoute();
    await waitFor(() => expect(mockList).toHaveBeenCalledTimes(1));
  });

  test("passes profile operator_id when hydrated", async () => {
    SNAP.profile = { user: "u", operator_id: "op_christian" };
    mockList.mockResolvedValueOnce(makeEmptyListResponse("op_christian"));
    renderRoute();
    await waitFor(() => expect(mockList).toHaveBeenCalledWith("op_christian"));
  });

  test("renders empty state when no sessions", async () => {
    mockList.mockResolvedValueOnce(makeEmptyListResponse());
    renderRoute();
    await screen.findByText(/No sessions for this operator/i);
  });

  test("renders sessions list newest-first from server", async () => {
    mockList.mockResolvedValueOnce(makeListResponse());
    mockDetail.mockResolvedValueOnce(makeDetailResponse("sess-001"));
    renderRoute();
    await screen.findByText("sess-001");
    expect(screen.getByText("sess-000")).toBeInTheDocument();
  });

  test("auto-selects first session and fetches detail", async () => {
    mockList.mockResolvedValueOnce(makeListResponse());
    mockDetail.mockResolvedValueOnce(makeDetailResponse("sess-001"));
    renderRoute();
    await waitFor(() =>
      expect(mockDetail).toHaveBeenCalledWith("sess-001"),
    );
  });

  test("renders history entries with intent + text after selection", async () => {
    mockList.mockResolvedValueOnce(makeListResponse());
    mockDetail.mockResolvedValueOnce(makeDetailResponse("sess-001"));
    renderRoute();
    await screen.findByText("first step");
    expect(screen.getByText("second step")).toBeInTheDocument();
  });

  test("clicking a session fetches its detail", async () => {
    const user = userEvent.setup();
    mockList.mockResolvedValueOnce(makeListResponse());
    mockDetail
      .mockResolvedValueOnce(makeDetailResponse("sess-001"))   // auto-selected
      .mockResolvedValueOnce(makeDetailResponse("sess-000"));  // user click
    renderRoute();
    await screen.findByText("sess-001");

    // Click sess-000 (the older one in the list).
    const olderBtn = screen.getByText("sess-000");
    await user.click(olderBtn);

    await waitFor(() =>
      expect(mockDetail).toHaveBeenCalledWith("sess-000"),
    );
  });

  test("REFRESH re-fetches the list", async () => {
    const user = userEvent.setup();
    mockList.mockResolvedValue(makeEmptyListResponse());
    renderRoute();
    await waitFor(() => expect(mockList).toHaveBeenCalledTimes(1));

    await user.click(screen.getByRole("button", { name: "REFRESH" }));
    await waitFor(() => expect(mockList).toHaveBeenCalledTimes(2));
  });

  test("error from list call surfaces in the banner", async () => {
    mockList.mockRejectedValueOnce(new Error("network down"));
    renderRoute();
    await screen.findByText(/network down/i);
  });

  test("history entry shows decision pill (uppercased)", async () => {
    mockList.mockResolvedValueOnce(makeListResponse());
    mockDetail.mockResolvedValueOnce(makeDetailResponse("sess-001"));
    renderRoute();
    await screen.findByText("ALLOW");
    expect(screen.getByText("WARN")).toBeInTheDocument();
  });
});
