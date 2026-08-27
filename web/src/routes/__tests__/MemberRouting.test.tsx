/**
 * /cockpit is the member product; V1 moves to /admin/cockpit.
 *
 * ★ THE SWAP, NOT A REWIRE. Every existing pointer already says /cockpit —
 * auth_magiclink DEFAULT_NEXT_PATH, the [My Account] link, the magic link
 * itself. Changing what is MOUNTED lands all of them on V2 with no other
 * edit, which is what gate 4 asks to be verified by generation rather than
 * by reading the route table.
 *
 * ★★ The admin gate is UX, not security. V1's panels call /operator/*,
 * /el_ins/* and /founder/*, all cohort-gated server-side. This only stops a
 * member wandering into a console full of 403s.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

// ★ ONE STABLE OBJECT, mutated between tests. useSyncExternalStore compares
// snapshots by IDENTITY, so returning a fresh `{...authState}` on every call
// re-renders forever ("Maximum update depth exceeded") -- a test artefact
// that presents exactly like a product bug.
// `session` is what RequireAuth actually gates on -- NOT `user`. Measured:
// mocking only user/profile renders the "Sign in required" CTA instead of
// the route under test.
const authState: {
  session: string | null;
  user: string | null;
  profile: { cohort: string | null } | null;
} = { session: null, user: null, profile: null };

vi.mock("../../lib/auth", async () => {
  const actual = await vi.importActual<typeof import("../../lib/auth")>("../../lib/auth");
  return {
    ...actual,
    getAuthSnapshot: () => authState,
    subscribeAuth: () => () => {},
  };
});

// The two cockpits are heavy; stand in for them so this exercises ROUTING.
vi.mock("../CockpitV2", () => ({
  default: () => <div data-testid="cockpit-v2">V2 MEMBER COCKPIT</div>,
}));
vi.mock("../Cockpit", () => ({
  default: () => <div data-testid="cockpit-v1">V1 ADMIN CONSOLE</div>,
}));

import App from "../../App";

function at(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  authState.session = "sess_test";
  authState.user = "member@example.com";
  authState.profile = { cohort: "member" };
});

describe("member routing", () => {
  it("★ GATE 4: /cockpit — where every existing pointer lands — renders V2", async () => {
    at("/cockpit");
    expect(await screen.findByTestId("cockpit-v2")).toBeTruthy();
    expect(screen.queryByTestId("cockpit-v1")).toBeNull();
  });

  it("/cockpit-v2 redirects to /cockpit rather than 404ing a bookmark", async () => {
    at("/cockpit-v2");
    expect(await screen.findByTestId("cockpit-v2")).toBeTruthy();
  });

  it("★ NEGATIVE CONTROL: a member at /admin/cockpit is redirected, NOT shown a broken console", async () => {
    at("/admin/cockpit");
    await waitFor(() => expect(screen.queryByTestId("cockpit-v1")).toBeNull());
    // Redirected to the member product — not a dead-end error screen.
    expect(await screen.findByTestId("cockpit-v2")).toBeTruthy();
  });

  it("an admin cohort DOES reach /admin/cockpit", async () => {
    authState.profile = { cohort: "founder" };
    at("/admin/cockpit");
    expect(await screen.findByTestId("cockpit-v1")).toBeTruthy();
  });

  it("a signed-out visitor at /admin/cockpit goes to login, not the console", async () => {
    authState.session = null;
    authState.user = null;
    authState.profile = null;
    at("/admin/cockpit");
    await waitFor(() => expect(screen.queryByTestId("cockpit-v1")).toBeNull());
  });
});
