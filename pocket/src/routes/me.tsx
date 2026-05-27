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
import { isFoundingMember, isOperator, roleLabel } from "../lib/role";

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
 * Pocket Me — v0.3.10 (role-aware).
 *
 * Same identity + session view as v0.3.4, plus:
 *   * a role badge derived from ``cohort`` + ``tier`` (Card 13
 *     contract; see ``src/lib/role.ts`` for the inference rules)
 *   * a "Become a Founding Member" upgrade CTA card for non-founding
 *     accounts (linking to /landing where the Stripe checkout lives)
 *
 * No backend changes; Pocket infers the role from the existing /me
 * response fields until the backend grows a real ``role`` field.
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
  const founding = isFoundingMember(data);
  const operator = isOperator(data);

  return (
    <>
      <Card>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
            marginBottom: 4,
          }}
        >
          <h1 style={{ margin: 0 }}>Me</h1>
          <span
            className={`pkt-badge ${
              operator
                ? "pkt-badge--operator"
                : founding
                  ? "pkt-badge--founding"
                  : "pkt-badge--free"
            }`}
          >
            {roleLabel(data)}
          </span>
        </div>

        <dl className="pkt-dl" style={{ marginTop: 16 }}>
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

      {!founding ? (
        <>
          <SectionTitle>Upgrade</SectionTitle>
          <Card>
            <p style={{ marginTop: 0 }}>
              You&rsquo;re signed in as <code>{roleLabel(data)}</code>. Become a
              Founding Member to unlock the full Pocket surface,
              early-access features, and direct operator support.
            </p>
            <Link
              to="/landing"
              className="pkt-btn pkt-btn--primary pkt-btn--md is-block"
            >
              View Founding Member offer
            </Link>
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
