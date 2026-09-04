/**
 * #145 -- two rails, one flag.
 *
 * CT-1 RULED 09-04: the MEMBER rail is Cockpit · Library · Vault · Timeline
 * · Membership · Sign out -- six links and nothing else. Everything else is
 * the OPERATOR rail, one group, rendered only when the profile is the
 * controller (RequireAdmin.isController). A null profile -- the load
 * window, a signed-out visitor -- fails closed to the member rail.
 *
 * ★ ONE STABLE OBJECT for the auth snapshot (useSyncExternalStore compares
 * by identity; a fresh object per call loops forever). Same pattern as
 * routes/__tests__/MemberRouting.test.tsx.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { fireEvent, render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const authState: {
  session: string | null;
  user: string | null;
  profile: { cohort?: string | null; controller?: boolean; member_number?: number | null } | null;
} = { session: null, user: null, profile: null };

vi.mock("../../lib/auth", async () => {
  const actual = await vi.importActual<typeof import("../../lib/auth")>("../../lib/auth");
  return {
    ...actual,
    getAuthSnapshot: () => authState,
    subscribeAuth: () => () => {},
    signOut: vi.fn(),
  };
});
vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    probeBackend: vi.fn(async () => ({ reachable: false, apiBase: "/api" })),
  };
});

import * as auth from "../../lib/auth";
import Layout from "../Layout";

const MEMBER_RAIL = ["Cockpit", "Library", "Vault", "Timeline", "Membership", "Sign out"];

function railTexts(): string[] {
  const { container } = render(
    <MemoryRouter initialEntries={["/library"]}>
      <Layout />
    </MemoryRouter>,
  );
  return Array.from(container.querySelectorAll("nav.rail a")).map((a) => a.textContent ?? "");
}

beforeEach(() => {
  vi.clearAllMocks();
  authState.session = "sess_test";
  authState.user = "u";
  authState.profile = { cohort: "founding", controller: false, member_number: 17 };
});

describe("Layout — the two rails (#145)", () => {
  it("★ a member sees six links and nothing else", () => {
    expect(railTexts()).toEqual(MEMBER_RAIL);
  });

  it("a null profile (the load window) fails closed to the member rail", () => {
    authState.profile = null;
    expect(railTexts()).toEqual(MEMBER_RAIL);
  });

  it("★ the controller sees the member rail first, then the operator rail as one group", () => {
    authState.profile = { cohort: "controller", controller: true, member_number: 1 };
    const texts = railTexts();
    expect(texts.slice(0, 6)).toEqual(MEMBER_RAIL);
    const operator = texts.slice(6);
    expect(operator.length).toBeGreaterThan(20);
    expect(operator).toContain("Founder console");
    expect(operator).toContain("System");
    expect(operator).toContain("Dashboard");
    // #34 -- one thing is called Vault; the runtime inspector is Runtime Vault.
    expect(operator).toContain("Runtime Vault");
    expect(texts).not.toContain("Operator Vault");
    // #141 / #144 -- redirects, not links.
    expect(texts).not.toContain("Plans");
    expect(texts).not.toContain("Account");
    expect(texts).not.toContain("Threads");
  });

  it("the legacy admin strings still read as the controller for one deploy (#157)", () => {
    authState.profile = { cohort: "founder", controller: false };
    expect(railTexts().length).toBeGreaterThan(6);
  });

  it("a signed-out visitor sees the five member links and no Sign out", () => {
    authState.session = null;
    authState.user = null;
    authState.profile = null;
    expect(railTexts()).toEqual(MEMBER_RAIL.slice(0, 5));
  });

  it("Sign out on the rail makes the same call the topbar makes", () => {
    const { getByTestId } = render(
      <MemoryRouter initialEntries={["/library"]}>
        <Layout />
      </MemoryRouter>,
    );
    fireEvent.click(getByTestId("rail-signout"));
    expect(vi.mocked(auth.signOut)).toHaveBeenCalledTimes(1);
  });
});
