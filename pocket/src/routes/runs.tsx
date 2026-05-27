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
import { isFoundingMember } from "../lib/role";

/**
 * Pocket Runs — v0.3.10 (Founding-Member-gated).
 *
 * Same list of ``GET /elins/regression/runs`` as v0.3.2, with a
 * Pocket-side gate in front: only Founding Members see the table.
 * Non-founding accounts see a "Become a Founding Member" CTA
 * pointing at /landing.
 *
 * Note: this is a UX gate, not a security gate. The backend doesn't
 * check tier on /elins/regression/runs — any authenticated session
 * can call it directly. Card 14 said "hide runs table for free
 * users"; that's what this does. Real authorization belongs in the
 * backend.
 *
 * /me is fetched first; if it shows the account is NOT a Founding
 * Member, the /runs API call is skipped entirely (saves a request +
 * keeps the upgrade CTA snappy).
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
      // Skip the runs fetch entirely if the user isn't a Founding
      // Member — the table won't render anyway.
      if (!isFoundingMember(m)) {
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

  // Founding-Member gate. /me succeeded but the account isn't a
  // Founding Member — show the upgrade CTA instead of the table.
  if (meData && !isFoundingMember(meData)) {
    return (
      <Card>
        <h1>Runs</h1>
        <p className="pocket-muted" style={{ marginBottom: 8 }}>
          Founding Members only.
        </p>
        <p style={{ marginTop: 0 }}>
          The regression-runs table is part of the Founding Member
          surface. Sign up to unlock it (and the rest of Pocket).
        </p>
        <Link
          to="/landing"
          className="pkt-btn pkt-btn--primary pkt-btn--md is-block"
        >
          View Founding Member offer
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
