import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  runs as fetchRuns,
  AuthRequiredError,
  type RegressionRunRecord,
} from "../api/client";
import Card from "../components/Card";
import ErrorBlock from "../components/Error";
import { List, ListItem } from "../components/List";
import Loading from "../components/Loading";

/**
 * Pocket Runs — v0.3.2.
 *
 * Lists ``GET /elins/regression/runs`` (the backend's closest
 * match to the card's "/runs"). Empty / 401 / error states each
 * render their own Card; the populated case is a tight, scannable
 * List.
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
      if (e instanceof AuthRequiredError) setNeedsAuth(true);
      else setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  if (loading) {
    return (
      <Card>
        <h1>Runs</h1>
        <Loading label="Loading runs…" />
      </Card>
    );
  }

  if (needsAuth) {
    return (
      <Card>
        <h1>Runs</h1>
        <p className="pocket-muted" style={{ marginBottom: 16 }}>
          Sign in required.
        </p>
        <Link
          to="/login"
          state={{ from: "/runs" }}
          className="pkt-btn pkt-btn--primary pkt-btn--md is-block"
        >
          Sign in
        </Link>
      </Card>
    );
  }

  if (error || !rows) {
    return (
      <Card>
        <h1>Runs</h1>
        <ErrorBlock
          error={error}
          onRetry={load}
          title="Could not load /elins/regression/runs"
        />
      </Card>
    );
  }

  if (rows.length === 0) {
    return (
      <Card>
        <h1>Runs</h1>
        <p className="pocket-muted">No runs recorded yet.</p>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <h1>Runs</h1>
        <p className="pocket-faint" style={{ fontSize: 13 }}>
          Source: <code>/elins/regression/runs</code> &middot;{" "}
          {rows.length} record{rows.length === 1 ? "" : "s"}
        </p>
      </Card>

      <Card padded={false}>
        <List>
          {rows.map((r) => (
            <ListItem
              key={r.run_id}
              trailing={
                <span className="src">{r.engine_version ?? "—"}</span>
              }
            >
              <div className="pkt-runs-row">
                <span className="id">{r.run_id}</span>
                <span className="ts">{r.created_at ?? "—"}</span>
              </div>
              <span className="pocket-faint" style={{ fontSize: 12 }}>
                {r.source ?? "—"}
              </span>
            </ListItem>
          ))}
        </List>
      </Card>
    </>
  );
}
