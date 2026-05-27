import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  me,
  logout,
  AuthRequiredError,
  type MeResponse,
} from "../api/client";
import ErrorBlock from "../components/Error";
import Loading from "../components/Loading";

/**
 * Pocket Me screen.
 *
 * GETs ``/me`` on mount. A 401 routes the user to ``/login`` via the
 * inline gate (rather than reflexively redirecting on render — that
 * would make sign-out feel jumpy).
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
      if (e instanceof AuthRequiredError) {
        setNeedsAuth(true);
      } else {
        setError(e instanceof Error ? e : new Error(String(e)));
      }
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
      <section className="pocket-me">
        <h1>Me</h1>
        <Loading label="Loading session…" />
      </section>
    );
  }

  if (needsAuth) {
    return (
      <section className="pocket-me">
        <h1>Me</h1>
        <p>Not signed in.</p>
        <p>
          <Link to="/login" state={{ from: "/me" }} className="pocket-btn">
            Sign in
          </Link>
        </p>
      </section>
    );
  }

  if (error || !data) {
    return (
      <section className="pocket-me">
        <h1>Me</h1>
        <ErrorBlock error={error} onRetry={load} title="Could not load /me" />
      </section>
    );
  }

  const enabledFeatures = Object.entries(data.features)
    .filter(([, v]) => v)
    .map(([k]) => k)
    .sort();

  return (
    <section className="pocket-me">
      <h1>Me</h1>

      <dl>
        <dt>User</dt>
        <dd>{data.user}</dd>

        <dt>Tier</dt>
        <dd>{data.tier}</dd>

        <dt>Cohort</dt>
        <dd>{data.cohort ?? "(none)"}</dd>

        <dt>Operator ID</dt>
        <dd>{data.operator_id ?? "(unset)"}</dd>

        <dt>Billing expires</dt>
        <dd>
          {data.billing_expires_at
            ? new Date(data.billing_expires_at * 1000).toISOString()
            : "(none)"}
        </dd>
      </dl>

      {enabledFeatures.length > 0 ? (
        <>
          <h2>Enabled features</h2>
          <ul className="pocket-features">
            {enabledFeatures.map((f) => (
              <li key={f}>
                <code>{f}</code>
              </li>
            ))}
          </ul>
        </>
      ) : null}

      <p>
        <button type="button" className="pocket-btn" onClick={onSignOut}>
          Sign out
        </button>
      </p>
    </section>
  );
}
