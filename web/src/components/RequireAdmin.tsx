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

/** Cohorts allowed to see the V1 console. Mirrors the server's founder-like
 *  cohorts (app.py COHORT_FOUNDER / COHORT_FOUNDER_EXCEPTION / admin); the
 *  server re-checks every call regardless. */
// #124 -- the founder is /me.controller; the derived label "controller"
// and the legacy strings are accepted for one deploy (the server's shim).
const ADMIN_COHORTS = new Set(["controller", "founder", "founder_exception", "admin"]);

export function isAdminCohort(cohort: string | null | undefined): boolean {
  return typeof cohort === "string" && ADMIN_COHORTS.has(cohort);
}

export function isController(profile: { controller?: boolean; cohort?: string | null } | null | undefined): boolean {
  return profile?.controller === true || isAdminCohort(profile?.cohort);
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
