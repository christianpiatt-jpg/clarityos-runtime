import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  runs as fetchRuns,
  AuthRequiredError,
  type RegressionRunRecord,
} from "../api/client";
import ErrorBlock from "../components/Error";
import Loading from "../components/Loading";

/**
 * Pocket Runs screen.
 *
 * Lists ``GET /elins/regression/runs`` (the backend's closest match
 * to the card's "/runs"). 401 → sign-in gate; non-empty array →
 * tabular list keyed by ``run_id``.
 *
 * Clicking a row is a v0.3.x-ish hook — the route exists at
 * ``GET /elins/regression/run/{id}`` (already wired in
 * ``api/client.ts``) but renders raw JSON for now. v0.3.x will own
 * the detail screen.
 */
export default function RunsRoute() {
  const [rows, setRows] = useState<RegressionRunRecord[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [needsAuth, setNeedsAuth] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    setNeedsAuth(false);
    try {
      const data = await fetchRuns();
      setRows(data);
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

  if (loading) {
    return (
      <section className="pocket-runs">
        <h1>Runs</h1>
        <Loading label="Loading runs…" />
      </section>
    );
  }

  if (needsAuth) {
    return (
      <section className="pocket-runs">
        <h1>Runs</h1>
        <p>Sign in required.</p>
        <p>
          <Link to="/login" state={{ from: "/runs" }} className="pocket-btn">
            Sign in
          </Link>
        </p>
      </section>
    );
  }

  if (error || !rows) {
    return (
      <section className="pocket-runs">
        <h1>Runs</h1>
        <ErrorBlock
          error={error}
          onRetry={load}
          title="Could not load /elins/regression/runs"
        />
      </section>
    );
  }

  if (rows.length === 0) {
    return (
      <section className="pocket-runs">
        <h1>Runs</h1>
        <p className="pocket-muted">No runs recorded yet.</p>
      </section>
    );
  }

  return (
    <section className="pocket-runs">
      <h1>Runs</h1>
      <p className="pocket-muted">
        Source: <code>/elins/regression/runs</code> &middot; {rows.length} record
        {rows.length === 1 ? "" : "s"}
      </p>

      <table className="pocket-runs-table">
        <thead>
          <tr>
            <th>run_id</th>
            <th>created_at</th>
            <th>source</th>
            <th>engine</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.run_id}>
              <td>
                <code>{r.run_id}</code>
              </td>
              <td>{r.created_at ?? "—"}</td>
              <td>{r.source ?? "—"}</td>
              <td>{r.engine_version ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
