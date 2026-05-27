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
import { isOperator, isVaultReady, roleLabel } from "../lib/role";

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
 * Pocket Me — v0.3.12 (Card 17, operator-mode).
 *
 * Reads ``me.operator`` and ``me.vault_ready`` DIRECTLY from /me
 * (Card 16 made these fields authoritative). No more cohort/tier
 * inference, no more isFoundingMember logic — the backend is the
 * single source of truth.
 *
 * Renders three cards:
 *   1. Identity   — user, tier, cohort, badge (operator | <tier>)
 *   2. Session    — signed-in age + expires-in countdown (v0.3.4)
 *   3. Vault      — Vault Ready / Vault Degraded indicator (Card 17)
 *   + optional Enabled-features chips card (v0.3.4)
 *   + Sign-out card
 *
 * The legacy "Upgrade to Founding Member" card is removed; per
 * Card 17 the user/operator split is the only one Pocket
 * recognises. A separate, future card will reintroduce a tier-based
 * upgrade surface if/when Founding Members get a distinct in-app UX.
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
  const op = isOperator(data);
  const ready = isVaultReady(data);

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
              op ? "pkt-badge--operator" : "pkt-badge--free"
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
          <dd>{op ? "yes" : "no"}</dd>

          <dt>Operator ID</dt>
          <dd>{data.operator_id ?? "(unset)"}</dd>

          <dt>Billing expires</dt>
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

      <SectionTitle>Vault</SectionTitle>
      <Card>
        <p className="pkt-status">
          <span
            className={`pkt-vault-dot ${
              ready ? "pkt-vault-dot--ready" : "pkt-vault-dot--degraded"
            }`}
          />
          {ready ? "Vault Ready" : "Vault Degraded"}
        </p>
        {!ready ? (
          <p className="pocket-faint" style={{ fontSize: 13 }}>
            Engine reports the v46 memory vault as not configured for
            this account. Some routes (intelligence kernel views) may
            return partial data until the operator restores the
            vault secret.
          </p>
        ) : null}
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
