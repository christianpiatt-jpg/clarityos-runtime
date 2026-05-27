import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  me,
  logout,
  AuthRequiredError,
  type MeResponse,
} from "../api/client";
import Button from "../components/Button";
import Card from "../components/Card";
import ErrorBlock from "../components/Error";
import Loading from "../components/Loading";
import SectionTitle from "../components/SectionTitle";

/**
 * Pocket Me — v0.3.2.
 *
 * GETs ``/me`` on mount. Renders two states cleanly:
 *   * signed-in:  identity card + features chips + sign-out
 *   * signed-out: gate card with primary CTA to /login
 */
export default function MeRoute() {
  const [data, setData] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [needsAuth, setNeedsAuth] = useState(false);
  const [error, setError] = useState<Error | null>(null);

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

  function onSignOut() {
    logout();
    setData(null);
    setNeedsAuth(true);
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
