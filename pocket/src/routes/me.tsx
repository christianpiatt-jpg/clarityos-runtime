import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";

import {
  me,
  logout,
  getSessionAge,
  AuthRequiredError,
  type MeResponse,
} from "../api/client";
import Button from "../components/Button";
import Card from "../components/Card";
import ErrorBlock from "../components/Error";
import Loading from "../components/Loading";
import SectionTitle from "../components/SectionTitle";

/** Coarse human-readable duration. We don't need second-level
 *  precision for a "signed in 5 min ago" indicator. */
function formatDuration(ms: number): string {
  if (ms < 0) return "expired";
  const totalSec = Math.floor(ms / 1000);
  const days = Math.floor(totalSec / 86400);
  const hours = Math.floor((totalSec % 86400) / 3600);
  const mins = Math.floor((totalSec % 3600) / 60);
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${mins}m`;
  if (mins > 0) return `${mins}m`;
  return "<1m";
}

/**
 * Pocket Me — v0.3.4.
 *
 * GETs ``/me`` on mount. Renders two states cleanly:
 *   * signed-in:  identity card + session-age card + features chips
 *                 + sign-out
 *   * signed-out: gate card with primary CTA to /login
 *
 * Session age (v0.3.4): if local metadata is present the page shows
 * how long ago the session was created + how long until it expires.
 * Updates once per minute via setInterval; no backend round-trip.
 *
 * Sign-out: clears local session AND navigates to /login so the
 * post-logout state is unambiguous (no "you're on /me but
 * unauthenticated" middle state).
 */
export default function MeRoute() {
  const navigate = useNavigate();
  const [data, setData] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [needsAuth, setNeedsAuth] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [, setTick] = useState(0);

  async function load() {
    setLoading(true);
    setError(null);
    setNeedsAuth(false);
    try {
      const d = await me();
      setData(d);
    } catch (e) {
      if (e instanceof AuthRequiredError) setNeedsAuth(true);
      else setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  // Tick the age indicator once a minute. No-ops when no session
  // metadata is available.
  useEffect(() => {
    if (!data) return;
    const id = window.setInterval(() => setTick((t) => t + 1), 60 * 1000);
    return () => window.clearInterval(id);
  }, [data]);

  function onSignOut() {
    logout();
    setData(null);
    setNeedsAuth(true);
    navigate("/login", { replace: true });
  }

  if (loading) {
    return (
      <Card>
        <h1>Me</h1>
        <Loading label="Loading session…" />
      </Card>
    );
  }

  if (needsAuth) {
    return (
      <Card>
        <h1>Me</h1>
        <p className="pocket-muted" style={{ marginBottom: 16 }}>
          Not signed in.
        </p>
        <Link
          to="/login"
          state={{ from: "/me" }}
          className="pkt-btn pkt-btn--primary pkt-btn--md is-block"
        >
          Sign in
        </Link>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card>
        <h1>Me</h1>
        <ErrorBlock error={error} onRetry={load} title="Could not load /me" />
      </Card>
    );
  }

  const enabledFeatures = Object.entries(data.features)
    .filter(([, v]) => v)
    .map(([k]) => k)
    .sort();

  const age = getSessionAge();

  return (
    <>
      <Card>
        <h1>Me</h1>
        <dl className="pkt-dl" style={{ marginTop: 12 }}>
          <dt>User</dt>
          <dd>{data.user}</dd>

          <dt>Tier</dt>
          <dd>{data.tier}</dd>

          <dt>Cohort</dt>
          <dd>{data.cohort ?? "(none)"}</dd>

          <dt>Operator</dt>
          <dd>{data.operator_id ?? "(unset)"}</dd>

          <dt>Expires</dt>
          <dd>
            {data.billing_expires_at
              ? new Date(data.billing_expires_at * 1000).toISOString()
              : "(none)"}
          </dd>
        </dl>
      </Card>

      {age ? (
        <>
          <SectionTitle>Session</SectionTitle>
          <Card>
            <dl className="pkt-dl">
              <dt>Signed in</dt>
              <dd>{formatDuration(age.ageMs)} ago</dd>

              <dt>Expires in</dt>
              <dd>
                {age.remainingMs > 0
                  ? formatDuration(age.remainingMs)
                  : "(expired — next request will redirect to /login)"}
              </dd>
            </dl>
          </Card>
        </>
      ) : null}

      {enabledFeatures.length > 0 ? (
        <>
          <SectionTitle>Enabled features</SectionTitle>
          <Card padded={false} style={{ padding: 16 }}>
            <ul className="pkt-feature-chips">
              {enabledFeatures.map((f) => (
                <li key={f}>
                  <code>{f}</code>
                </li>
              ))}
            </ul>
          </Card>
        </>
      ) : null}

      <Card>
        <Button variant="secondary" block onClick={onSignOut}>
          Sign out
        </Button>
      </Card>
    </>
  );
}
