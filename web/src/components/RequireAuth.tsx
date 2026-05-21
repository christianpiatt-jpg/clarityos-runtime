import { useSyncExternalStore } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { getAuthSnapshot, subscribeAuth } from "../lib/auth";

/** Gate authenticated-only routes.
 *
 *  v66 / Unit 70 — replaced silent <Navigate> redirect with an inline
 *  CTA so unauthed visitors see what surface they were trying to
 *  reach and can choose to sign in (vs. being silently teleported).
 *  The `from` state is still attached to the Sign-in link so the
 *  login flow can redirect back here on success.
 *
 *  This component is used on every authenticated route in App.tsx,
 *  so the CTA is the single source of truth for "you need to sign
 *  in" copy across the web client.
 */
export default function RequireAuth() {
  const auth = useSyncExternalStore(subscribeAuth, getAuthSnapshot, getAuthSnapshot);
  const location = useLocation();
  if (!auth.session) {
    return (
      <div className="panel" role="region" aria-label="Sign in required" data-testid="auth-cta">
        <h1>Sign in required</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          You need to sign in to start or resume sessions.
        </p>
        <div style={{ marginTop: 16 }}>
          <Link
            to="/login"
            state={{ from: location.pathname }}
            className="btn"
            data-testid="auth-cta-signin"
          >
            SIGN IN
          </Link>
        </div>
      </div>
    );
  }
  return <Outlet />;
}
