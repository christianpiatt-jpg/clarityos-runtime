import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  me,
  runs as fetchRuns,
  AuthRequiredError,
  type MeResponse,
  type RegressionRunRecord,
} from "../api/client";
import Card from "../components/Card";
import ErrorBlock from "../components/Error";
import { List, ListItem } from "../components/List";
import Loading from "../components/Loading";
import { isOperator } from "../lib/role";

/**
 * Pocket Runs — v0.3.12 (Card 17, operator-mode).
 *
 * Now gated on the AUTHORITATIVE ``me.operator`` field (Card 16),
 * not on the v0.3.10 cohort/tier inference. ``/me`` is fetched
 * first; if the user isn't an operator, the runs API is skipped
 * entirely and the page renders an inline gate (request operator
 * access).
 *
 * Note: this remains a UX gate, not a security gate. The backend
 * does not check operator status on
 * ``/elins/regression/runs`` itself — a determined caller with a
 * session can still hit the API directly. The Card 17 contract is
 * to make Pocket the operator-only console; the backend authz is
 * a separate (future) concern.
 */
export default function RunsRoute() {
  const [meData, setMeData] = useState<MeResponse | null>(null);
  const [rows, setRows] = useState<RegressionRunRecord[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [needsAuth, setNeedsAuth] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    setNeedsAuth(false);
    try {
      const m = await me();
      setMeData(m);
      if (!isOperator(m)) {
        setRows(null);
        return;
      }
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

  if (meData && !isOperator(meData)) {
    return (
      <Card>
        <h1>Runs</h1>
        <p className="pocket-muted" style={{ marginBottom: 8 }}>
          Operator-only surface.
        </p>
        <p style={{ marginTop: 0 }}>
          The regression-runs table is part of the operator console.
          Your account does not currently have operator privileges
          on the engine.
        </p>
        <Link
          to="/operator/state"
          className="pkt-btn pkt-btn--primary pkt-btn--md is-block"
        >
          Open operator state &rarr;
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
