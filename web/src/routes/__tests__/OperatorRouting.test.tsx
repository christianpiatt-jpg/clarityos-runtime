/**
 * #145 -- two rails, one flag: the route table.
 *
 * CT-1 RULED 09-04: /founder is admin only. A member who types /founder --
 * or any operator path -- lands on /cockpit, never a refusal page; the
 * controller reaches the console. /plans and /account are /membership
 * (#141); /threads is /cockpit (#144). A signed-out visitor at an
 * operator path meets RequireAuth's sign-in CTA (the system page was
 * public before this; it is the admin's now, #143).
 *
 * ★★ The gate is UX, not security: the founder routes answer 403
 * admin_only server-side. This pins where a member is SENT.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const authState: {
  session: string | null;
  user: string | null;
  profile: { cohort: string | null; controller?: boolean } | null;
} = { session: null, user: null, profile: null };

vi.mock("../../lib/auth", async () => {
  const actual = await vi.importActual<typeof import("../../lib/auth")>("../../lib/auth");
  return {
    ...actual,
    getAuthSnapshot: () => authState,
    subscribeAuth: () => () => {},
  };
});

// The destinations are heavy; stand in for them so this exercises ROUTING.
vi.mock("../CockpitV2", () => ({ default: () => <div data-testid="cockpit-v2">V2 MEMBER COCKPIT</div> }));
vi.mock("../Founder", () => ({ default: () => <div data-testid="founder-console">FOUNDER</div> }));
vi.mock("../FounderWaitlist", () => ({ default: () => <div data-testid="founder-waitlist">WAITLIST</div> }));
vi.mock("../System", () => ({ default: () => <div data-testid="system-page">SYSTEM</div> }));
vi.mock("../Operator", () => ({ default: () => <div data-testid="operator-page">OPERATOR</div> }));
vi.mock("../MembershipPage", () => ({ default: () => <div data-testid="membership-page">MEMBERSHIP</div> }));
vi.mock("../Elins", () => ({ default: () => <div data-testid="elins-page">ELINS</div> }));
vi.mock("../Sessions", () => ({ default: () => <div data-testid="sessions-page">SESSIONS</div> }));

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
  authState.profile = { cohort: "founding", controller: false };
});

describe("operator paths are the admin's (#145)", () => {
  it("★ a member at /founder is sent to /cockpit, not shown the console", async () => {
    at("/founder");
    expect(await screen.findByTestId("cockpit-v2")).toBeTruthy();
    expect(screen.queryByTestId("founder-console")).toBeNull();
  });

  it.each(["/founder/waitlist", "/system", "/operator", "/elins", "/sessions"])(
    "a member at %s is sent to /cockpit",
    async (path) => {
      at(path);
      expect(await screen.findByTestId("cockpit-v2")).toBeTruthy();
    },
  );

  it("★ the controller reaches /founder", async () => {
    authState.profile = { cohort: "controller", controller: true };
    at("/founder");
    expect(await screen.findByTestId("founder-console")).toBeTruthy();
  });

  it("the controller reaches /system (#143: the override is the admin's)", async () => {
    authState.profile = { cohort: "controller", controller: true };
    at("/system");
    expect(await screen.findByTestId("system-page")).toBeTruthy();
  });

  it("a signed-out visitor at /system meets the sign-in CTA, not the page", async () => {
    authState.session = null;
    authState.user = null;
    authState.profile = null;
    at("/system");
    expect(await screen.findByTestId("auth-cta")).toBeTruthy();
    expect(screen.queryByTestId("system-page")).toBeNull();
  });
});

describe("the folds are redirects, not 404s (#141 #144)", () => {
  it("/plans lands on /membership", async () => {
    at("/plans");
    expect(await screen.findByTestId("membership-page")).toBeTruthy();
  });

  it("/account lands on /membership", async () => {
    at("/account");
    expect(await screen.findByTestId("membership-page")).toBeTruthy();
  });

  it("/threads lands on /cockpit", async () => {
    at("/threads");
    expect(await screen.findByTestId("cockpit-v2")).toBeTruthy();
    await waitFor(() => expect(screen.queryByText(/not found/i)).toBeNull());
  });

  it("the member's own stores stay the member's: /membership renders for a member", async () => {
    at("/membership");
    expect(await screen.findByTestId("membership-page")).toBeTruthy();
  });
});
