// RequireAdmin — UX guard for the V1 admin cockpit.
//
// ★★ THIS IS NOT A SECURITY BOUNDARY, and must not be mistaken for one.
// V1's panels call /operator/*, /el_ins/* and /founder/*, every one of which
// is cohort-gated server-side. A member who reaches /admin/cockpit without
// this guard sees a screen full of 403s -- not privileged data. The real
// boundary is the backend and stays there.
//
// What this buys is that a member never lands in a broken console by
// following a stale link. Nothing more. Anyone editing this file should
// assume the route is reachable anyway and rely on the server.
import { useSyncExternalStore } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { getAuthSnapshot, subscribeAuth } from "../lib/auth";

/** #124 / #157 -- the founder is /me.controller and NOTHING else: no cohort
 *  label, no legacy string (the server's #124 shim is deleted, #157; a
 *  string on a doc opens nothing there either). The server re-checks every
 *  call regardless. */
export function isController(profile: { controller?: boolean; cohort?: string | null } | null | undefined): boolean {
  return profile?.controller === true;  // the label is accepted in the type and read by nothing
}

/** #145 -- the one flag the rails and the dashboard doors read. Subscribed,
 *  so a sign-in or sign-out re-renders whoever reads it. A null profile --
 *  the load window, a signed-out visitor -- fails closed (false). */
export function useIsController(): boolean {
  const auth = useSyncExternalStore(subscribeAuth, getAuthSnapshot, getAuthSnapshot);
  return isController(auth.profile);
}

export default function RequireAdmin() {
  // Subscribed, not sampled: a bare getAuthSnapshot() call never re-renders
  // when auth changes, so a sign-out would leave the console on screen.
  // Same pattern RequireAuth uses.
  const auth = useSyncExternalStore(subscribeAuth, getAuthSnapshot, getAuthSnapshot);
  const location = useLocation();

  // `session` is the field RequireAuth gates on -- matched here so the two
  // guards cannot disagree about who is signed in.
  if (!auth.session) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }
  if (!isController(auth.profile)) {
    // Redirect rather than render a refusal page: the member product is
    // where they meant to be, and a dead-end error screen is the exact
    // outcome this guard exists to avoid.
    return <Navigate to="/cockpit" replace />;
  }
  return <Outlet />;
}
