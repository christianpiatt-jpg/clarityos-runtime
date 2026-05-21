// v66 / Unit 70 — RequireAuth tests.
//
// Covers:
//   * Unauth → inline CTA rendered (no redirect)
//   * Authed → outlet content rendered
//   * CTA Sign-in link targets /login and carries `from` state

import { describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

// Mock the auth module so tests can flip auth state without touching
// localStorage or the global memorySession state in api.ts.
vi.mock("../../lib/auth", () => {
  const snapshot: { session: string | null; user: string | null; profile: null } = {
    session: null,
    user: null,
    profile: null,
  };
  return {
    getAuthSnapshot: () => snapshot,
    subscribeAuth: (_fn: () => void) => () => {},
    __setMockSnapshot: (s: Partial<typeof snapshot>) => {
      snapshot.session = s.session ?? null;
      snapshot.user = s.user ?? null;
      snapshot.profile = null;
    },
  };
});

import * as authMock from "../../lib/auth";
import RequireAuth from "../RequireAuth";

// Test helper — sets the mocked snapshot before each render.
function setAuth(session: string | null, user: string | null = null) {
  (authMock as unknown as {
    __setMockSnapshot: (s: { session: string | null; user: string | null }) => void;
  }).__setMockSnapshot({ session, user });
}

function ProtectedChild() {
  return <div data-testid="protected-content">PROTECTED</div>;
}

function renderRoute(initialPath: string = "/session") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route element={<RequireAuth />}>
          <Route path="/session" element={<ProtectedChild />} />
        </Route>
        <Route path="/login" element={<div data-testid="login-route">LOGIN_PAGE</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("RequireAuth", () => {
  test("unauthenticated → renders inline CTA, not the outlet", () => {
    setAuth(null);
    renderRoute("/session");
    expect(screen.getByTestId("auth-cta")).toBeInTheDocument();
    expect(screen.getByText("Sign in required")).toBeInTheDocument();
    expect(screen.queryByTestId("protected-content")).not.toBeInTheDocument();
  });

  test("unauthenticated → CTA contains a SIGN IN link to /login", () => {
    setAuth(null);
    renderRoute("/session");
    const cta = screen.getByTestId("auth-cta-signin") as HTMLAnchorElement;
    expect(cta).toHaveAttribute("href", "/login");
    expect(cta).toHaveTextContent("SIGN IN");
  });

  test("unauthenticated → does NOT auto-redirect to /login", () => {
    // Pre-Unit-70 behavior was <Navigate to=\"/login\">; the new
    // behavior shows an inline CTA and lets the user choose.
    setAuth(null);
    renderRoute("/session");
    expect(screen.queryByTestId("login-route")).not.toBeInTheDocument();
  });

  test("authenticated → renders the protected outlet", () => {
    setAuth("sid-test-abc", "op_alice");
    renderRoute("/session");
    expect(screen.getByTestId("protected-content")).toBeInTheDocument();
    expect(screen.queryByTestId("auth-cta")).not.toBeInTheDocument();
  });

  test("CTA copy mentions session sign-in", () => {
    setAuth(null);
    renderRoute("/session");
    expect(
      screen.getByText(/sign in to start or resume sessions/i),
    ).toBeInTheDocument();
  });
});
